from __future__ import annotations

from app.entity.reply import ReplyLineFact, ReplyPlan

_GLUE_ACK = "记下了："
_GLUE_ACK_EMPTY = "记下了"
_GLUE_RECAP = "当前草稿："
_GLUE_EMPTY = "还没有货"
_GLUE_CONFIRM = "单已确认："
_GLUE_ASK = "有多家都叫这个，请问是哪一家？"
_GLUE_TBD = "价未定"
_GLUE_PROFILE = "按档案"
_NOTICE_GLUE = {
    "last_deal_available_not_applied": "未采用成交价",
    "price_memory_expired": "成交价已过期",
    "market_hint_not_applied": "今日行情未写入",
}


class TemplateResponseGenerator:
    """只拼接 ReplyPlan 字段与固定虚词。禁止读 Session / Catalog。"""

    def generate(self, plan: ReplyPlan) -> str:
        if plan.question and plan.question.code == "customer_unknown":
            who = plan.question.option_labels[0] if plan.question.option_labels else ""
            return f"还没有{who}的信息，档口是哪一个？"
        if plan.question and plan.question.code == "customer_ambiguous":
            names = "、".join(plan.question.option_labels)
            return f"{_GLUE_ASK}{names}"
        if plan.confirmed:
            parts = [self._line(item, recap=True) for item in plan.lines]
            who = plan.customer_label or ""
            prefix = f"{who} {_GLUE_CONFIRM}" if who else _GLUE_CONFIRM
            return prefix + "，".join(parts) + self._notices(plan)
        if plan.mode == "ack" or plan.reply_scope == "changed_only":
            if not plan.lines:
                return _GLUE_ACK_EMPTY
            return _GLUE_ACK + "，".join(self._line(item, recap=False) for item in plan.lines)
        if not plan.lines:
            return _GLUE_EMPTY
        return _GLUE_RECAP + "；".join(self._line(item, recap=True) for item in plan.lines) + self._notices(plan)

    def _notices(self, plan: ReplyPlan) -> str:
        chunks: list[str] = []
        for notice in plan.notices:
            glue = _NOTICE_GLUE.get(notice.code)
            if not glue:
                continue
            extras = "".join(ref.text for ref in notice.source_refs if ref.kind in {"price", "uom"})
            chunks.append(f"{glue}{extras}")
        if not chunks:
            return ""
        return "。" + "；".join(chunks)

    def _line(self, item: ReplyLineFact, *, recap: bool) -> str:
        if not recap:
            return f"{item.label}{item.qty_text}{item.uom}"
        name = item.sku_text or item.label
        extra = f"（{_GLUE_PROFILE}{item.sku_text}）" if item.from_profile and item.sku_text else ""
        if item.price_text:
            price = f"，{item.price_text}{item.price_uom or '块'}"
        elif item.price_tbd:
            price = f"，{_GLUE_TBD}"
        else:
            price = ""
        return f"{name} {item.qty_text}{item.uom}{extra}{price}"
