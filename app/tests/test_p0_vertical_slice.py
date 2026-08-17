from __future__ import annotations

from fastapi.testclient import TestClient

from app.bootstrap import build_app_world
from app.main import create_app
from app.tests.test_api_turns import _open_session, _turn


def _client() -> TestClient:
    return TestClient(create_app(build_app_world()))


def test_p0_demo_page_is_todays_order_book():
    html = _client().get("/").text
    assert "今日开单" in html
    assert "当前订单" in html
    assert "待确认" in html
    assert "已确认" in html
    assert "还没有开始开单" in html
    assert 'data-example="李老板苹果八十果二十箱"' in html
    assert 'data-example="刚才苹果改30箱"' in html
    assert 'data-example="好了"' in html
    assert "mapDemoUtterance" in html
    assert "/v1/workbench" in html
    assert "库存" not in html
    assert "收款" not in html
    assert "item_code" not in html
    assert "Parser" not in html
    assert "加一行" not in html


def test_p0_golden_path_open_change_confirm_updates_workbench():
    client = _client()
    session_id = _open_session(client)
    opened = _turn(client, session_id, "开李老板的单苹果二十箱", seq=1, utterance_id="p0-1")
    assert opened.status_code == 200, opened.text
    draft = opened.json()["draft"]
    assert draft["status"] == "draft"
    assert "李老板" in (draft["customer"]["aliases"] or [])
    assert len(draft["lines"]) == 1
    line = draft["lines"][0]
    assert line["qty"] in {"20", "20.0"}
    assert line["uom"] == "箱"
    assert "80果" in line["label"]
    assert line["price_status"] == "tbd"
    board = client.get("/v1/workbench").json()
    current = next(task for task in board["tasks"] if task["session_id"] == session_id)
    assert current["status"] == "drafting"
    assert current["customer_label"] == "李老板"
    assert current["posting"] is None

    changed = _turn(client, session_id, "苹果改30箱", seq=2, utterance_id="p0-2")
    assert changed.status_code == 200, changed.text
    changed_line = changed.json()["draft"]["lines"][0]
    assert changed_line["qty"] in {"30", "30.0"}
    assert changed_line["uom"] == "箱"
    assert changed.json()["draft"]["status"] == "draft"

    done = _turn(client, session_id, "好了", seq=3, utterance_id="p0-3")
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["verdict"]["confirm_ok"] is True
    assert body["draft"]["status"] == "confirmed"
    assert body["draft"]["lines"][0]["qty"] in {"30", "30.0"}
    assert "价未定" in body["reply_text"]
    assert body["enterprise"]["posting"] == "posted"

    after = client.get("/v1/workbench").json()
    confirmed = [task for task in after["tasks"] if task["status"] == "confirmed"]
    assert len(confirmed) == 1
    assert confirmed[0]["session_id"] == session_id
    assert confirmed[0]["customer_label"] == "李老板"
    assert confirmed[0]["posting"] == "posted"
    assert confirmed[0]["line_count"] == 1

    blocked = _turn(client, session_id, "苹果改40箱", seq=4, utterance_id="p0-4")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "task_completed"
    still = client.get(f"/v1/sessions/{session_id}").json()
    assert still["draft"]["status"] == "confirmed"
    assert still["draft"]["lines"][0]["qty"] in {"30", "30.0"}
