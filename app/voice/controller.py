from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from app.voice.policy import expect_more_for, has_speech_content, trim_transcript
from app.voice.ports import AsrPort, AsrRequest, AsrResult, TtsPort, TtsRequest, TurnsTransport, VoicePhase


@dataclass
class ControllerResult:
    posted: bool
    phase: VoicePhase
    reason: str = ""
    status_code: int | None = None
    payload: dict[str, Any] | None = None
    outbound: dict[str, Any] | None = None


@dataclass
class VoiceController:
    """PTT 状态机 + turns 字段策略。不调 Runner，不改 reply_text。"""

    transport: TurnsTransport
    asr: AsrPort
    tts: TtsPort
    source: Literal["voice", "text"] = "voice"
    phase: VoicePhase = "IDLE"
    session_id: str | None = None
    seq: int = 0
    utterance_id: str | None = None
    overlay: str = ""
    reply_text: str = ""
    hint: str = ""
    last_payload: dict[str, Any] | None = None
    outbound: list[dict[str, Any]] = field(default_factory=list)
    play_id: str | None = None
    _holding: bool = False
    _last_command: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        maybe = getattr(self.tts, "on_event", None)
        if callable(maybe):
            maybe(self._on_tts_event)

    def ensure_session(self) -> dict[str, Any]:
        if self.session_id is None:
            return self.start_new_session()
        return self.last_payload or {}

    def start_new_session(self) -> dict[str, Any]:
        snapshot = self.transport.create_session()
        self.session_id = str(snapshot["session_id"])
        self.seq = 0
        self.utterance_id = None
        self.overlay = ""
        self._holding = False
        self._last_command = None
        self.last_payload = snapshot
        self.phase = "IDLE"
        self.hint = ""
        return snapshot

    def press(self) -> ControllerResult:
        if self.phase == "PROCESSING":
            return ControllerResult(posted=False, phase=self.phase, reason="busy")
        if self.phase == "DONE":
            self.start_new_session()
            return ControllerResult(posted=False, phase=self.phase, reason="new_session")
        if self.phase == "SPEAKING":
            self.tts.interrupt()
        if self.phase == "LISTENING":
            return ControllerResult(posted=False, phase=self.phase, reason="already_listening")
        self.utterance_id = str(uuid4())
        self.overlay = ""
        self._holding = True
        self.hint = ""
        self.phase = "LISTENING"
        return ControllerResult(posted=False, phase=self.phase, reason="listening")

    def note_partial(self, text: str) -> None:
        if self.phase != "LISTENING":
            return
        self.overlay = text
        note = getattr(self.asr, "note_partial", None)
        if callable(note):
            note(text)

    def release(self, audio: bytes = b"") -> ControllerResult:
        if self.phase != "LISTENING" or not self._holding:
            return ControllerResult(posted=False, phase=self.phase, reason="not_listening")
        self._holding = False
        utterance_id = self.utterance_id or str(uuid4())
        result = self.asr.transcribe(AsrRequest(audio=audio, utterance_id=utterance_id))
        return self._accept_asr(result, utterance_id)

    def submit_asr_result(self, result: AsrResult) -> ControllerResult:
        """Inject a finished ASR result (chips / Fake). Same path as PTT release."""
        if self.phase == "PROCESSING":
            return ControllerResult(posted=False, phase=self.phase, reason="busy")
        if self.phase == "DONE":
            self.start_new_session()
            return ControllerResult(posted=False, phase=self.phase, reason="new_session")
        if self.phase == "SPEAKING":
            self.tts.interrupt()
        if self.phase == "LISTENING":
            self._holding = False
        utterance_id = str(uuid4())
        self.utterance_id = utterance_id
        return self._accept_asr(result, utterance_id)

    def submit_fake_final(self, text: str) -> ControllerResult:
        return self.submit_asr_result(AsrResult(kind="final", text=text))

    def confirm_done(self) -> ControllerResult:
        if self.phase in {"PROCESSING", "DONE"}:
            return ControllerResult(posted=False, phase=self.phase, reason="busy")
        if self.phase == "LISTENING":
            return self.release()
        if self.phase == "SPEAKING":
            self.tts.interrupt()
        return self.submit_fake_final("好了")

    def retry_last(self) -> ControllerResult:
        if self._last_command is None or self.session_id is None:
            return ControllerResult(posted=False, phase=self.phase, reason="nothing_to_retry")
        status, body = self.transport.post_turn(self.session_id, self._last_command)
        return ControllerResult(
            posted=True,
            phase=self.phase,
            reason="retry",
            status_code=status,
            payload=body,
            outbound=dict(self._last_command),
        )

    def _accept_asr(self, result: AsrResult, utterance_id: str) -> ControllerResult:
        self.overlay = ""
        if result.kind != "final":
            self.utterance_id = None
            self.phase = "IDLE"
            self.hint = "再说一遍" if result.kind == "error" else ""
            return ControllerResult(posted=False, phase=self.phase, reason=result.kind)
        text = trim_transcript(result.text or "")
        if not has_speech_content(text):
            self.utterance_id = None
            self.phase = "IDLE"
            return ControllerResult(posted=False, phase=self.phase, reason="empty")
        return self._post_final(text, utterance_id)

    def _post_final(self, text: str, utterance_id: str) -> ControllerResult:
        self.ensure_session()
        assert self.session_id is not None
        self.phase = "PROCESSING"
        self.seq += 1
        command = {
            "text": text,
            "source": self.source,
            "utterance_id": utterance_id,
            "seq": self.seq,
            "is_final": True,
            "expect_more": expect_more_for(text),
        }
        self.outbound.append(dict(command))
        self._last_command = dict(command)
        self.utterance_id = None
        status, body = self.transport.post_turn(self.session_id, command)
        if status == 409 and str(body.get("detail")) == "task_completed":
            old = self.session_id
            self.start_new_session()
            return ControllerResult(
                posted=False,
                phase=self.phase,
                reason="task_completed",
                status_code=status,
                payload={"detail": "task_completed", "old_session_id": old},
                outbound=command,
            )
        if status != 200:
            self.seq -= 1
            self.phase = "IDLE"
            self.hint = "这句没接上，请再说一遍。"
            return ControllerResult(
                posted=True,
                phase=self.phase,
                reason=str(body.get("detail") or "http_error"),
                status_code=status,
                payload=body,
                outbound=command,
            )
        self.last_payload = body
        self.reply_text = str(body.get("reply_text") or "")
        self.hint = ""
        ignored = bool(body.get("ignored"))
        draft = body.get("draft") or {}
        confirmed = draft.get("status") == "confirmed"
        if ignored or not self.reply_text:
            self.phase = "DONE" if confirmed else "IDLE"
            return ControllerResult(
                posted=True,
                phase=self.phase,
                reason="accepted_silent",
                status_code=status,
                payload=body,
                outbound=command,
            )
        self.play_id = str(uuid4())
        if confirmed:
            self.phase = "DONE"
        else:
            self.phase = "SPEAKING"
        self.tts.speak(TtsRequest(text=self.reply_text, play_id=self.play_id))
        return ControllerResult(
            posted=True,
            phase=self.phase,
            reason="accepted",
            status_code=status,
            payload=body,
            outbound=command,
        )

    def _on_tts_event(self, kind: str, play_id: str) -> None:
        if play_id != self.play_id:
            return
        if kind == "interrupted":
            if self.phase == "SPEAKING":
                self.phase = "LISTENING" if self._holding else "IDLE"
            return
        if kind in {"ended", "failed"}:
            if self.phase == "SPEAKING":
                self.phase = "IDLE"
            if kind == "failed":
                self.hint = ""
