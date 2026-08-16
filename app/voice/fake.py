from __future__ import annotations

from collections import deque

from app.voice.policy import has_speech_content, trim_transcript
from app.voice.ports import AsrRequest, AsrResult, TtsRequest


class FakeAsrPort:
    """CI / Demo 夹具。只交出 final / empty / error；partial 仅作 UI 记录。"""

    def __init__(self) -> None:
        self._queue: deque[AsrResult] = deque()
        self.calls: list[AsrRequest] = []
        self.partials: list[str] = []

    def queue_final(self, text: str) -> None:
        self._queue.append(AsrResult(kind="final", text=text))

    def queue_empty(self) -> None:
        self._queue.append(AsrResult(kind="empty"))

    def queue_error(self) -> None:
        self._queue.append(AsrResult(kind="error"))

    def note_partial(self, text: str) -> str:
        self.partials.append(text)
        return text

    def transcribe(self, request: AsrRequest) -> AsrResult:
        self.calls.append(request)
        if not self._queue:
            return AsrResult(kind="empty")
        result = self._queue.popleft()
        if result.kind != "final":
            return AsrResult(kind=result.kind)
        text = trim_transcript(result.text or "")
        if not has_speech_content(text):
            return AsrResult(kind="empty")
        return AsrResult(kind="final", text=text)


class FakeTtsPort:
    """记录被念的字符串。禁止改写。"""

    def __init__(self, *, auto_complete: bool = True) -> None:
        self.auto_complete = auto_complete
        self.spoken: list[str] = []
        self.events: list[tuple[str, str]] = []
        self.current_play_id: str | None = None
        self.fail_next = False
        self._on_event: list = []

    def on_event(self, callback) -> None:
        self._on_event.append(callback)

    def speak(self, request: TtsRequest) -> None:
        if self.fail_next:
            self.fail_next = False
            self.current_play_id = None
            self.events.append(("failed", request.play_id))
            self._emit("failed", request.play_id)
            return
        self.spoken.append(request.text)
        self.current_play_id = request.play_id
        self.events.append(("started", request.play_id))
        self._emit("started", request.play_id)
        if self.auto_complete:
            self.complete()

    def interrupt(self) -> None:
        if self.current_play_id is None:
            return
        play_id = self.current_play_id
        self.current_play_id = None
        self.events.append(("interrupted", play_id))
        self._emit("interrupted", play_id)

    def complete(self) -> None:
        if self.current_play_id is None:
            return
        play_id = self.current_play_id
        self.current_play_id = None
        self.events.append(("ended", play_id))
        self._emit("ended", play_id)

    def _emit(self, kind: str, play_id: str) -> None:
        for callback in list(self._on_event):
            callback(kind, play_id)
