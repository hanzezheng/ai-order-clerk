from __future__ import annotations

from fastapi.testclient import TestClient

from app.bootstrap import build_app_world
from app.entity.session import SalesSession
from app.main import create_app

FORBIDDEN = {"user_text", "raw_text", "text", "utterance", "chat", "message", "reply_text"}


def _client() -> TestClient:
    return TestClient(create_app(build_app_world()))


def _turn(client: TestClient, session_id: str, text: str, *, seq: int, utterance_id: str):
    return client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "text": text,
            "source": "text",
            "utterance_id": utterance_id,
            "seq": seq,
            "is_final": True,
            "expect_more": False,
        },
    )


def _assert_no_chat(node: object) -> None:
    if isinstance(node, dict):
        lowered = {str(key).lower() for key in node}
        assert not (lowered & FORBIDDEN), node
        for value in node.values():
            _assert_no_chat(value)
    elif isinstance(node, list):
        for item in node:
            _assert_no_chat(item)


def _confirm_li_apple(client: TestClient, session_id: str) -> None:
    assert _turn(client, session_id, "开李老板的单", seq=1, utterance_id="w-start").status_code == 200
    assert _turn(client, session_id, "苹果60件", seq=2, utterance_id="w-apple").status_code == 200
    done = _turn(client, session_id, "好了", seq=3, utterance_id="w-ok")
    assert done.status_code == 200
    assert done.json()["verdict"]["confirm_ok"] is True


def test_sales_session_has_no_cross_order_fields():
    fields = set(SalesSession.model_fields)
    assert "previous_order_ids" not in fields
    assert "day_orders" not in fields
    assert "messages" not in fields
    assert "workbench_tasks" not in fields


def test_workbench_create_task_is_a_new_sales_session():
    client = _client()
    created = client.post("/v1/workbench/tasks")
    assert created.status_code == 201, created.text
    body = created.json()
    session_id = body["current_session_id"]
    assert session_id
    assert body["tasks"][0]["session_id"] == session_id
    assert body["tasks"][0]["status"] == "drafting"
    snap = client.get(f"/v1/sessions/{session_id}").json()
    assert snap["draft"]["lines"] == []
    assert snap["draft"]["customer"] is None
    _assert_no_chat(body)


def test_second_task_is_another_session_after_confirm():
    client = _client()
    first = client.post("/v1/workbench/tasks").json()
    session_a = first["current_session_id"]
    _confirm_li_apple(client, session_a)
    board = client.get("/v1/workbench").json()
    assert board["current_session_id"] == session_a
    confirmed = next(t for t in board["tasks"] if t["session_id"] == session_a)
    assert confirmed["status"] == "confirmed"
    assert confirmed["customer_label"]
    assert confirmed["line_count"] == 1
    assert confirmed["confirmed_at"]
    _assert_no_chat(board)

    second = client.post("/v1/workbench/tasks")
    assert second.status_code == 201
    session_b = second.json()["current_session_id"]
    assert session_b != session_a
    empty = client.get(f"/v1/sessions/{session_b}").json()
    assert empty["draft"]["lines"] == []
    assert empty["draft"]["status"] == "draft"
    board2 = client.get("/v1/workbench").json()
    assert board2["current_session_id"] == session_b
    assert {t["session_id"] for t in board2["tasks"]} == {session_a, session_b}


def test_confirmed_task_rejects_further_turns():
    client = _client()
    session_id = client.post("/v1/workbench/tasks").json()["current_session_id"]
    _confirm_li_apple(client, session_id)
    blocked = _turn(client, session_id, "苹果60件", seq=4, utterance_id="w-again")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "task_completed"
    snap = client.get(f"/v1/sessions/{session_id}").json()
    assert len(snap["draft"]["lines"]) == 1


def test_switch_current_task():
    client = _client()
    a = client.post("/v1/workbench/tasks").json()["current_session_id"]
    b = client.post("/v1/workbench/tasks").json()["current_session_id"]
    switched = client.post("/v1/workbench/current", json={"session_id": a})
    assert switched.status_code == 200
    assert switched.json()["current_session_id"] == a
    assert b != a


def test_workbench_does_not_write_memory_on_task_create():
    world = build_app_world()
    client = TestClient(create_app(world))
    before = list(world.catalog.prices.snapshot())
    client.post("/v1/workbench/tasks")
    client.post("/v1/workbench/tasks")
    assert world.catalog.prices.snapshot() == before
    assert world.catalog.aliases.snapshot() == []
