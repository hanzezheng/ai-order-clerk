from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from urllib.request import Request

from app.agent.admission_scripts import admission_scripts
from app.bootstrap import build_app_world
from app.main import create_app
from app.tests.test_api_turns import FORBIDDEN_TIMELINE_KEYS, _turn
from app.voice.controller import VoiceController
from app.voice.fake import FakeAsrPort, FakeTtsPort
from app.voice.http_ports import HttpAsrPort, HttpTtsPort
from app.voice.policy import CLOSING_WORDS, expect_more_for
from app.voice.ports import AsrRequest, AsrResult, TtsRequest
from app.voice.transport import HttpTurnsTransport

JS_PATH = Path(__file__).resolve().parents[1] / "api" / "static" / "voice-controller.js"


def _client() -> TestClient:
    return TestClient(create_app(build_app_world()))


def _controller(
    client: TestClient,
    *,
    source: str = "voice",
    auto_complete: bool = True,
) -> tuple[VoiceController, FakeAsrPort, FakeTtsPort, HttpTurnsTransport]:
    transport = HttpTurnsTransport(client)
    asr = FakeAsrPort()
    tts = FakeTtsPort(auto_complete=auto_complete)
    controller = VoiceController(transport=transport, asr=asr, tts=tts, source=source)  # type: ignore[arg-type]
    return controller, asr, tts, transport


def _business(body: dict) -> dict:
    draft = body.get("draft") or {}
    customer = draft.get("customer")
    verdict = body.get("verdict") or {}
    return {
        "draft_status": draft.get("status"),
        "customer": None
        if not customer
        else {"name": customer.get("name"), "stall_no": customer.get("stall_no")},
        "lines": [
            {
                "label": line.get("label"),
                "qty": line.get("qty"),
                "uom": line.get("uom"),
                "price_status": line.get("price_status"),
                "unit_price": line.get("unit_price"),
                "line_status": line.get("line_status"),
            }
            for line in draft.get("lines") or []
        ],
        "confirm_ok": verdict.get("confirm_ok"),
        "reply_mode": body.get("reply_mode") or verdict.get("reply_mode"),
        "issues": sorted(issue.get("code") for issue in verdict.get("issues") or []),
        "commands_executed": list(body.get("commands_executed") or []),
        "reply_text": body.get("reply_text"),
        "timeline": [event.get("event_type") for event in body.get("timeline") or []],
        "ignored": body.get("ignored"),
    }


def _assert_no_chat(timeline: list) -> None:
    def walk(node: object) -> None:
        if isinstance(node, dict):
            assert not ({str(key).lower() for key in node} & FORBIDDEN_TIMELINE_KEYS), node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(timeline)


def _speak_voice(controller: VoiceController, asr: FakeAsrPort, text: str) -> dict:
    asr.queue_final(text)
    controller.press()
    result = controller.release(b"wav")
    assert result.posted, result
    assert result.payload is not None
    return result.payload


def _type_text(controller: VoiceController, text: str) -> dict:
    result = controller.submit_fake_final(text)
    assert result.posted, result
    assert result.payload is not None
    return result.payload


def test_expect_more_uses_closed_word_table_not_business():
    assert expect_more_for("苹果60件") is True
    assert expect_more_for("开李老板的单") is True
    assert expect_more_for("不对") is True
    assert expect_more_for("统货") is True
    assert expect_more_for("好了") is False
    assert expect_more_for("就这样") is False
    assert expect_more_for("可以了") is False
    assert expect_more_for("定了") is False
    assert expect_more_for("苹果60件好了") is False
    assert expect_more_for("  好了  ") is False


def test_e1_g1_g4_text_and_voice_are_equivalent():
    for script in admission_scripts():
        texts = [step.text for step in script.steps]
        text_ctl, _, _, _ = _controller(_client(), source="text")
        voice_ctl, asr, tts, _ = _controller(_client(), source="voice")
        replies = []
        for text in texts:
            left = _business(_type_text(text_ctl, text))
            body = _speak_voice(voice_ctl, asr, text)
            replies.append(body["reply_text"])
            assert left == _business(body), (script.script_id, text, left, _business(body))
            _assert_no_chat((text_ctl.last_payload or {}).get("timeline") or [])
            _assert_no_chat((voice_ctl.last_payload or {}).get("timeline") or [])
        burst = next((item for item in voice_ctl.outbound if item["text"] == "苹果60件梨60件"), None)
        if burst is not None:
            assert burst["expect_more"] is True
            assert burst["source"] == "voice"
            assert burst["is_final"] is True
        done = next((item for item in voice_ctl.outbound if item["text"] == "好了"), None)
        if done is not None:
            assert done["expect_more"] is False
        assert all(item["is_final"] is True for item in voice_ctl.outbound)
        assert all(item["source"] == "voice" for item in voice_ctl.outbound)
        assert tts.spoken == replies


def test_e2_partial_never_reaches_runtime():
    controller, asr, tts, transport = _controller(_client())
    _speak_voice(controller, asr, "开李老板的单")
    posts_before = list(transport.posts)
    lines_before = list((controller.last_payload or {}).get("draft", {}).get("lines") or [])
    controller.press()
    controller.note_partial("苹果")
    controller.note_partial("苹果60")
    assert controller.overlay == "苹果60"
    assert transport.posts == posts_before
    assert ((controller.last_payload or {}).get("draft") or {}).get("lines") == lines_before
    asr.queue_final("苹果60件")
    body = controller.release(b"wav").payload
    assert body is not None
    assert body["ignored"] is False
    assert len(body["draft"]["lines"]) == 1
    assert body["draft"]["lines"][0]["qty"] == "60"
    assert asr.partials == ["苹果", "苹果60"]
    assert all(post.get("text") != "苹果" for post in transport.posts)
    assert tts.spoken[-1] == body["reply_text"]


def test_e3_utterance_id_retry_is_idempotent():
    controller, asr, _, _ = _controller(_client())
    _speak_voice(controller, asr, "开李老板的单")
    first = _speak_voice(controller, asr, "苹果60件")
    retry = controller.retry_last()
    assert retry.status_code == 200
    assert retry.payload is not None
    assert retry.payload["reply_text"] == first["reply_text"]
    assert len(retry.payload["draft"]["lines"]) == 1
    assert retry.payload["draft"]["lines"][0]["qty"] == "60"
    assert retry.outbound == controller.outbound[-1]


def test_e4_empty_listen_does_not_consume_seq():
    controller, asr, tts, transport = _controller(_client())
    asr.queue_empty()
    controller.press()
    empty = controller.release(b"")
    assert empty.posted is False
    assert controller.seq == 0
    assert controller.phase == "IDLE"
    assert transport.posts == []
    assert tts.spoken == []
    body = _speak_voice(controller, asr, "开李老板的单")
    assert controller.outbound[-1]["seq"] == 1
    assert body["ignored"] is False


def test_e4_seq_conflict_does_not_mutate_draft():
    controller, asr, _, transport = _controller(_client())
    _speak_voice(controller, asr, "开李老板的单")
    before = json.loads(json.dumps(controller.last_payload))

    def boom(session_id: str, payload: dict) -> tuple[int, dict]:
        transport.posts.append({"session_id": session_id, **payload})
        return 409, {"detail": "seq_out_of_order"}

    transport.post_turn = boom  # type: ignore[method-assign]
    asr.queue_final("苹果60件")
    controller.press()
    result = controller.release(b"wav")
    assert result.status_code == 409
    assert controller.seq == 1
    assert controller.last_payload == before
    assert before["draft"]["lines"] == []


def test_e5_tts_input_equals_reply_text_and_skips_empty():
    controller, asr, tts, _ = _controller(_client())
    asr.queue_empty()
    controller.press()
    controller.release(b"")
    assert tts.spoken == []
    body = _speak_voice(controller, asr, "开李老板的单")
    assert tts.spoken == [body["reply_text"]]
    tts.fail_next = True
    asr.queue_final("苹果60件")
    controller.press()
    failed = controller.release(b"wav")
    assert failed.payload is not None
    assert controller.reply_text == failed.payload["reply_text"]
    assert tts.spoken == [body["reply_text"]]
    assert tts.events[-1][0] == "failed"


def test_e6_barge_in_does_not_rollback():
    controller, asr, tts, _ = _controller(_client(), auto_complete=False)
    _speak_voice(controller, asr, "开李老板的单")
    tts.complete()
    apple = _speak_voice(controller, asr, "苹果60件")
    assert controller.phase == "SPEAKING"
    assert apple["draft"]["lines"][0]["qty"] == "60"
    asr.queue_final("再加20")
    controller.press()
    assert tts.events[-1][0] == "interrupted"
    assert controller.phase == "LISTENING"
    result = controller.release(b"wav")
    assert result.payload is not None
    assert result.payload["draft"]["lines"][0]["qty"] == "80"
    assert len(result.payload["draft"]["lines"]) == 1


def test_e7_confirmed_session_cannot_write_old_order():
    client = _client()
    controller, asr, _, _ = _controller(client)
    for text in ["开李老板的单", "苹果60件", "好了"]:
        _speak_voice(controller, asr, text)
    assert controller.phase == "DONE"
    old_id = controller.session_id
    assert old_id is not None
    old_draft = client.get(f"/v1/sessions/{old_id}").json()["draft"]
    assert old_draft["status"] == "confirmed"
    refused = controller.submit_fake_final("梨60件")
    assert refused.posted is False
    assert refused.reason == "new_session"
    assert controller.session_id != old_id
    assert controller.seq == 0
    new_draft = client.get(f"/v1/sessions/{controller.session_id}").json()["draft"]
    assert new_draft["status"] == "draft"
    assert new_draft["lines"] == []
    assert new_draft["customer"] is None
    blocked = _turn(client, old_id, "梨60件", seq=4, utterance_id="after-done")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "task_completed"
    still = client.get(f"/v1/sessions/{old_id}").json()["draft"]
    assert still["status"] == "confirmed"
    assert len(still["lines"]) == 1


def test_e8_demo_keeps_one_mouth_and_same_controller():
    html = _client().get("/").text
    assert "voice-controller.js" in html
    assert "reply_text" in html
    assert "bossSpeak" not in html
    assert "friendlyBoss" not in html
    assert "李老板，单好了" not in html
    assert "价格还没定" not in html
    js = _client().get("/static/voice-controller.js").text
    assert "expectMoreFor" in js
    assert "createVoiceController" in js
    assert 'source: "voice"' in js
    assert "is_final: true" in js
    for word in CLOSING_WORDS:
        assert f'"{word}"' in js
    assert "SpeechSynthesisUtterance" in js
    assert "isFinal" in js


def test_e9_asr_errors_are_not_repaired_by_voice_layer():
    controller, asr, _, transport = _controller(_client())
    _speak_voice(controller, asr, "开李老板的单")
    heard = "六十五个苹果"
    asr.queue_final(heard)
    controller.press()
    result = controller.release(b"wav")
    assert result.outbound is not None
    assert result.outbound["text"] == heard
    assert "65" not in result.outbound["text"]
    assert "sku_id" not in result.outbound
    assert "product_mention" not in result.outbound
    assert result.outbound["expect_more"] is True
    assert transport.posts[-1]["text"] == heard

    voice, asr2, _, _ = _controller(_client())
    _speak_voice(voice, asr2, "开王老板的单")
    _speak_voice(voice, asr2, "王记水果店")
    asr2.queue_final("金枕60个")
    voice.press()
    durian = voice.release(b"wav")
    assert durian.outbound is not None
    assert durian.outbound["text"] == "金枕60个"
    assert "金边" not in durian.outbound["text"]
    labels = [line["label"] for line in (durian.payload or {})["draft"]["lines"]]
    assert all("金边" not in label for label in labels)


def test_e9_http_asr_drops_partial_and_tts_sends_exact_text(monkeypatch):
    responses: list[bytes] = [
        json.dumps({"text": "苹果", "is_final": False}).encode(),
        json.dumps({"text": "苹果60件", "is_final": True}).encode(),
    ]

    def fake_urlopen(request: Request, timeout: float = 0):
        class Reply:
            def read(self) -> bytes:
                return responses.pop(0)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        return Reply()

    monkeypatch.setattr("app.voice.http_ports.urlopen", fake_urlopen)
    asr = HttpAsrPort("http://asr.example/transcribe")
    dropped = asr.transcribe(AsrRequest(audio=b"pcm", utterance_id="u-partial"))
    assert dropped.kind == "empty"
    assert dropped.text is None
    final = asr.transcribe(AsrRequest(audio=b"pcm", utterance_id="u-final"))
    assert final == AsrResult(kind="final", text="苹果60件")

    sent: list[bytes] = []

    def tts_urlopen(request: Request, timeout: float = 0):
        sent.append(request.data or b"")

        class Reply:
            def read(self) -> bytes:
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        return Reply()

    monkeypatch.setattr("app.voice.http_ports.urlopen", tts_urlopen)
    tts = HttpTtsPort("http://tts.example/speak")
    tts.speak(TtsRequest(text="李老板，按档案红富士", play_id="p1"))
    assert json.loads(sent[0].decode("utf-8"))["text"] == "李老板，按档案红富士"
    assert tts.sent == ["李老板，按档案红富士"]


def test_controller_never_sends_partial_flag():
    controller, asr, _, transport = _controller(_client())
    _speak_voice(controller, asr, "开李老板的单")
    assert all(post["is_final"] is True for post in transport.posts)
    required = {"text", "source", "utterance_id", "seq", "is_final", "expect_more"}
    assert all(required <= set(post) for post in transport.posts)


def test_js_closing_words_match_python():
    source = JS_PATH.read_text(encoding="utf-8")
    for word in CLOSING_WORDS:
        assert f'"{word}"' in source
    assert "expectMoreFor" in source
