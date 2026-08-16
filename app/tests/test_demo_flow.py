from __future__ import annotations

from fastapi.testclient import TestClient

from app.bootstrap import build_app_world
from app.main import create_app
from app.tests.test_api_turns import FORBIDDEN_TIMELINE_KEYS, _open_session, _turn


def _client() -> TestClient:
    return TestClient(create_app(build_app_world()))


def test_demo_page_first_run_is_obvious_in_ten_seconds():
    html = _client().get("/").text
    assert "AI开单员" in html
    assert "还没有开始开单" in html
    assert "按住说话" in html
    assert "先说开谁的单" in html
    assert 'data-example="开李老板的单"' in html
    assert 'data-example="苹果60件"' in html
    assert 'data-example="好了"' in html
    assert "下一句" not in html
    assert "开发模式" not in html
    assert "加一行" not in html
    assert "name=\"qty\"" not in html
    assert "库存" not in html
    assert "收款" not in html
    assert "登录" not in html


def test_demo_page_has_one_mouth_from_backend_reply_text():
    html = _client().get("/").text
    assert "reply_text" in html
    assert "bossSpeak" not in html
    assert "friendlyBoss" not in html
    assert "friendlyProduct" not in html
    assert "价格还没定" not in html
    assert "李老板，单好了" not in html
    assert "按李老板常拿" not in html
    assert "没报规格" not in html
    assert "URLSearchParams" in html
    assert "get(\"dev\")" in html


def test_demo_flow_li_boss_confirms_with_price_tbd():
    client = _client()
    session_id = _open_session(client)
    start = _turn(client, session_id, "开李老板的单", seq=1, utterance_id="demo-1")
    apple = _turn(client, session_id, "苹果60件", seq=2, utterance_id="demo-2")
    done = _turn(client, session_id, "好了", seq=3, utterance_id="demo-3")
    assert start.status_code == 200
    assert apple.status_code == 200
    assert done.status_code == 200, done.text
    apple_body = apple.json()
    assert "红富士" in apple_body["reply_text"]
    assert "按档案" in apple_body["reply_text"]
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
