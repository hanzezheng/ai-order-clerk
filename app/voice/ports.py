from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


AsrKind = Literal["final", "empty", "error"]
TtsEventKind = Literal["started", "ended", "interrupted", "failed"]
VoicePhase = Literal["IDLE", "LISTENING", "PROCESSING", "SPEAKING", "DONE"]
TurnSource = Literal["voice", "text"]


@dataclass(frozen=True)
class AsrRequest:
    audio: bytes
    utterance_id: str


@dataclass(frozen=True)
class AsrResult:
    kind: AsrKind
    text: str | None = None


@dataclass(frozen=True)
class TtsRequest:
    text: str
    play_id: str


class AsrPort(Protocol):
    def transcribe(self, request: AsrRequest) -> AsrResult:
        """Return at most one final. Never a partial."""


class TtsPort(Protocol):
    def speak(self, request: TtsRequest) -> None:
        """Play reply_text unchanged."""

    def interrupt(self) -> None:
        """Stop current playback immediately."""


class TurnsTransport(Protocol):
    def create_session(self) -> dict:
        """POST /v1/sessions."""

    def post_turn(self, session_id: str, payload: dict) -> tuple[int, dict]:
        """POST /v1/sessions/{id}/turns. Return status and JSON body."""
