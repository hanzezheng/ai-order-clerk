from __future__ import annotations

import json
from os import environ
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.voice.policy import has_speech_content, trim_transcript
from app.voice.ports import AsrRequest, AsrResult, TtsRequest


class HttpAsrPort:
    """Optional cloud ASR. CI must not set ASR_URL. Partial responses are dropped."""

    def __init__(self, url: str, *, timeout: float = 8.0) -> None:
        self.url = url
        self.timeout = timeout

    def transcribe(self, request: AsrRequest) -> AsrResult:
        payload = json.dumps({"utterance_id": request.utterance_id}).encode("utf-8")
        http_request = Request(
            self.url,
            data=request.audio or payload,
            headers={"Content-Type": "application/octet-stream", "X-Utterance-Id": request.utterance_id},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self.timeout) as response:
                raw = response.read()
        except (URLError, TimeoutError, OSError):
            return AsrResult(kind="error")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return AsrResult(kind="error")
        if not isinstance(body, dict):
            return AsrResult(kind="error")
        if body.get("is_final") is False:
            return AsrResult(kind="empty")
        text = trim_transcript(str(body.get("text") or ""))
        if not has_speech_content(text):
            return AsrResult(kind="empty")
        return AsrResult(kind="final", text=text)


class HttpTtsPort:
    """Optional cloud TTS. Speaks the given text bytes as-is; does not rewrite."""

    def __init__(self, url: str, *, timeout: float = 8.0) -> None:
        self.url = url
        self.timeout = timeout
        self.sent: list[str] = []

    def speak(self, request: TtsRequest) -> None:
        body = json.dumps({"text": request.text, "play_id": request.play_id}, ensure_ascii=False).encode("utf-8")
        self.sent.append(request.text)
        http_request = Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self.timeout) as response:
                response.read()
        except (URLError, TimeoutError, OSError):
            return

    def interrupt(self) -> None:
        return


def live_ports_from_env() -> tuple[HttpAsrPort | None, HttpTtsPort | None]:
    asr_url = environ.get("ASR_URL", "").strip()
    tts_url = environ.get("TTS_URL", "").strip()
    asr = HttpAsrPort(asr_url) if asr_url else None
    tts = HttpTtsPort(tts_url) if tts_url else None
    return asr, tts
