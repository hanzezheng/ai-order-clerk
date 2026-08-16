from __future__ import annotations

CLOSING_WORDS: frozenset[str] = frozenset({"好了", "就这样", "可以了", "定了"})


def trim_transcript(text: str) -> str:
    """The only allowed rewrite: strip surrounding whitespace."""
    return text.strip()


def has_speech_content(text: str) -> bool:
    stripped = trim_transcript(text)
    if not stripped:
        return False
    for char in stripped:
        if char.isalnum() or "\u4e00" <= char <= "\u9fff":
            return True
    return False


def expect_more_for(text: str) -> bool:
    """Shell-only closer table. Not a business judgment, not VAD, not LLM."""
    stripped = trim_transcript(text)
    if stripped in CLOSING_WORDS:
        return False
    return not any(word in stripped for word in CLOSING_WORDS)
