from __future__ import annotations

from fastapi.testclient import TestClient

from app.bootstrap import build_app_world
from app.main import create_app

FORBIDDEN_TIMELINE_KEYS = {"user_text", "raw_text", "text", "utterance", "chat", "message"}


def _client() -> TestClient:
    return TestClient(create_app(build_app_world()))


def _open_session(client: TestClient) -> str:
    res = client.post("/v1/sessions")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "drafting"
    assert body["timeline"] == []
    assert body["draft"]["lines"] == []
    assert body["draft"]["customer"] is None
    return body["session_id"]


def _turn(
    client: TestClient,
    session_id: str,
    text: str,
    *,
    seq: int,
    utterance_id: str,
    is_final: bool = True,
    expect_more: bool = False,
    source: str = "text",
):
    return client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "text": text,
            "source": source,
            "utterance_id": utterance_id,
            "seq": seq,
            "is_final": is_final,
            "expect_more": expect_more,
        },
    )


def _assert_timeline_has_no_chat(timeline: list[dict]) -> None:
    def walk(node: object) -> None:
        if isinstance(node, dict):
            lowered = {str(key).lower() for key in node}
            assert not (lowered & FORBIDDEN_TIMELINE_KEYS), node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(timeline)


def test_create_session_starts_empty_task():
    client = _client()
    session_id = _open_session(client)
    res = client.get(f"/v1/sessions/{session_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["session_id"] == session_id
    assert body["draft"]["status"] == "draft"
    _assert_timeline_has_no_chat(body["timeline"])


def test_li_boss_apple_writes_business_timeline_without_chat():
    client = _client()
    session_id = _open_session(client)
    started = _turn(client, session_id, "开李老板的单", seq=1, utterance_id="utt-start")
    assert started.status_code == 200, started.text
    lined = _turn(client, session_id, "苹果60件", seq=2, utterance_id="utt-apple")
    assert lined.status_code == 200, lined.text
    body = lined.json()
    assert body["ignored"] is False
    assert body["draft"]["customer"]["name"]
    assert len(body["draft"]["lines"]) == 1
    assert body["draft"]["lines"][0]["qty"] == "60"
    types = [event["event_type"] for event in body["timeline"]]
    assert "order.started" in types
    assert "order.line_upserted" in types
    _assert_timeline_has_no_chat(body["timeline"])
    snapshot = client.get(f"/v1/sessions/{session_id}").json()
    _assert_timeline_has_no_chat(snapshot["timeline"])


def test_expect_more_acks_without_asking_price():
    client = _client()
    session_id = _open_session(client)
    _turn(client, session_id, "开李老板的单", seq=1, utterance_id="utt-start")
    res = _turn(
        client,
        session_id,
        "苹果60件",
        seq=2,
        utterance_id="utt-burst",
        expect_more=True,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reply_mode"] == "ack"
    assert body["verdict"]["reply_mode"] == "ack"
    assert "多少钱" not in body["reply_text"]


def test_partial_is_final_false_is_ignored():
    client = _client()
    session_id = _open_session(client)
    _turn(client, session_id, "开李老板的单", seq=1, utterance_id="utt-start")
    ignored = _turn(
        client,
        session_id,
        "苹果",
        seq=2,
        utterance_id="utt-partial",
        is_final=False,
    )
    assert ignored.status_code == 200, ignored.text
    body = ignored.json()
    assert body["ignored"] is True
    assert body["draft"]["lines"] == []
    before = [event["event_type"] for event in body["timeline"]]
    assert "order.line_upserted" not in before
    final = _turn(
        client,
        session_id,
        "苹果60件",
        seq=2,
        utterance_id="utt-apple",
        is_final=True,
    )
    assert final.status_code == 200, final.text
    assert final.json()["ignored"] is False
    assert len(final.json()["draft"]["lines"]) == 1


def test_duplicate_utterance_id_is_idempotent():
    client = _client()
    session_id = _open_session(client)
    _turn(client, session_id, "开李老板的单", seq=1, utterance_id="utt-start")
    first = _turn(client, session_id, "苹果60件", seq=2, utterance_id="utt-apple")
    second = _turn(client, session_id, "苹果60件", seq=2, utterance_id="utt-apple")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["reply_text"] == second.json()["reply_text"]
    lines = client.get(f"/v1/sessions/{session_id}").json()["draft"]["lines"]
    assert len(lines) == 1
    assert lines[0]["qty"] == "60"


def test_out_of_order_seq_conflicts():
    client = _client()
    session_id = _open_session(client)
    first = _turn(client, session_id, "开李老板的单", seq=1, utterance_id="utt-start")
    assert first.status_code == 200
    conflict = _turn(client, session_id, "苹果60件", seq=1, utterance_id="utt-gap")
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "seq_out_of_order"
    skipped = _turn(client, session_id, "苹果60件", seq=3, utterance_id="utt-skip")
    assert skipped.status_code == 409
    assert skipped.json()["detail"] == "seq_out_of_order"


def test_homonym_asks_and_records_business_block():
    client = _client()
    session_id = _open_session(client)
    res = _turn(client, session_id, "开王老板的单", seq=1, utterance_id="utt-wang")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reply_mode"] == "ask"
    assert body["draft"]["customer"] is None
    assert any(issue["code"] == "customer_ambiguous" for issue in body["verdict"]["issues"])
    types = [event["event_type"] for event in body["timeline"]]
    assert "customer_ambiguous" in types
    assert "order.started" not in types
    _assert_timeline_has_no_chat(body["timeline"])


def test_missing_session_is_not_found():
    client = _client()
    missing = "00000000-0000-0000-0000-000000000001"
    assert client.get(f"/v1/sessions/{missing}").status_code == 404
    res = _turn(client, missing, "开李老板的单", seq=1, utterance_id="utt-missing")
    assert res.status_code == 404
    assert res.json()["detail"] == "session_not_found"
