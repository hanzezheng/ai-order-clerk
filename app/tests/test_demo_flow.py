from __future__ import annotations

from fastapi.testclient import TestClient

from app.bootstrap import build_app_world
from app.main import create_app
from app.tests.test_api_turns import FORBIDDEN_TIMELINE_KEYS, _open_session, _turn


def _client() -> TestClient:
    return TestClient(create_app(build_app_world()))


def test_demo_page_is_voice_shell_not_erp_form():
    client = _client()
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "开单" in html
    assert "/v1/sessions" in html
    assert "加一行" not in html
    assert "name=\"qty\"" not in html
    assert "库存" not in html
    assert "收款" not in html
    assert "登录" not in html


def test_demo_flow_li_boss_confirms_with_price_tbd():
    client = _client()
    session_id = _open_session(client)
    start = _turn(client, session_id, "开李老板的单", seq=1, utterance_id="demo-1")
    apple = _turn(client, session_id, "苹果60件", seq=2, utterance_id="demo-2")
    done = _turn(client, session_id, "好了", seq=3, utterance_id="demo-3")
    assert start.status_code == 200
    assert apple.status_code == 200
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["verdict"]["confirm_ok"] is True
    assert body["draft"]["status"] == "confirmed"
    assert "价未定" in body["reply_text"]
    types = [event["event_type"] for event in body["timeline"]]
    assert "order.started" in types
    assert "order.line_upserted" in types
    assert "order.confirmed" in types

    def walk(node: object) -> None:
        if isinstance(node, dict):
            assert not ({str(key).lower() for key in node} & FORBIDDEN_TIMELINE_KEYS), node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(body["timeline"])
