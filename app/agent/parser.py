from __future__ import annotations

from typing import Protocol

from app.entity.speech import TurnParse


class TurnParser(Protocol):
    """文本 → TurnParse。禁止访问本体、客户、价格记忆。"""

    def parse(self, text: str) -> TurnParse: ...
