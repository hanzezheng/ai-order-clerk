from __future__ import annotations

from pydantic import BaseModel

from app.entity.reply import ReplyPlan

FILLERS = (
    "记下了：",
    "记下了",
    "当前草稿：",
    "单已确认：",
    "有多家都叫这个，请问是哪一家？",
    "还没有货",
    "价未定",
    "按档案",
    "（",
    "）",
    "，",
    "；",
    "、",
    "：",
    " ",
    "块",
    "元",
)


class GroundingResult(BaseModel):
    ok: bool
    leftover: str = ""


class ReplyGrounder:
    """白名单：删去 source_refs 与固定虚词后不得有剩余。不做 NLP。"""

    def check(self, text: str, plan: ReplyPlan) -> GroundingResult:
        remaining = text
        tokens = [ref.text for ref in plan.source_refs if ref.text]
        tokens.extend(FILLERS)
        for token in sorted(set(tokens), key=len, reverse=True):
            if token:
                remaining = remaining.replace(token, "")
        leftover = remaining.strip()
        return GroundingResult(ok=leftover == "", leftover=leftover)
