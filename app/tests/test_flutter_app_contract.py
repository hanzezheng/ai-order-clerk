from __future__ import annotations

from fastapi.testclient import TestClient

from app.bootstrap import build_app_world
from app.main import create_app
from app.tests.test_api_turns import _open_session, _turn


def _client() -> TestClient:
    return TestClient(create_app(build_app_world()))


def test_flutter_app_contract_open_change_confirm_workbench():
    """Flutter 壳依赖的 JSON 形状。不改 Runtime，只锁现有 API。"""
    client = _client()
    opened = client.post("/v1/workbench/tasks")
    assert opened.status_code == 201
    book = opened.json()
    assert "business_date" in book
    assert book["current_session_id"]
    session_id = book["current_session_id"]

    turn = _turn(
        client,
        session_id,
        "开李老板的单苹果二十箱",
        seq=1,
        utterance_id="app-1",
        source="voice",
        expect_more=True,
    )
    assert turn.status_code == 200, turn.text
    body = turn.json()
    assert "reply_text" in body
    draft = body["draft"]
    assert draft["customer"]["aliases"]
    assert draft["lines"][0]["label"]
    assert draft["lines"][0]["qty"]
    assert draft["lines"][0]["uom"]
    assert "item_code" not in turn.text

    changed = _turn(
        client,
        session_id,
        "苹果改30箱",
        seq=2,
        utterance_id="app-2",
        source="voice",
        expect_more=True,
    )
    assert changed.json()["draft"]["lines"][0]["qty"] in {"30", "30.0"}
    assert changed.json()["draft"]["status"] == "draft"

    done = _turn(client, session_id, "好了", seq=3, utterance_id="app-3", expect_more=False)
    assert done.status_code == 200, done.text
    assert done.json()["verdict"]["confirm_ok"] is True
    assert done.json()["draft"]["status"] == "confirmed"
    assert done.json()["enterprise"]["posting"] in {"pending", "posted", "unavailable"}

    after = client.get("/v1/workbench").json()
    confirmed = [task for task in after["tasks"] if task["status"] == "confirmed"]
    assert confirmed
    assert confirmed[0]["posting"] in {"pending", "posted", "unavailable"}
    assert confirmed[0]["customer_label"] == "李老板"


def test_flutter_app_contract_session_snapshot_has_draft():
    client = _client()
    session_id = _open_session(client)
    res = client.get(f"/v1/sessions/{session_id}")
    assert res.status_code == 200
    assert res.json()["draft"]["status"] == "draft"
    assert "timeline" in res.json()
