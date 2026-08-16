from __future__ import annotations

import re
from uuid import UUID

from app.entity.speech import SpeechAct, TurnParse

_CN = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_UNITS = "件个箱斤袋份只条"


def parse_cn_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    if token in _CN:
        return _CN[token]
    if token.endswith("十") and len(token) == 2 and token[0] in _CN:
        return _CN[token[0]] * 10
    if "十" in token and len(token) == 3:
        left, _, right = token.partition("十")
        if left in _CN and right in _CN:
            return _CN[left] * 10 + _CN[right]
    return None


class RuleTurnParser:
    """规则抽取 SpeechAct[]。不访问数据库，不决定业务规则。"""

    def parse(self, text: str, product_aliases: list[tuple[str, UUID]] | None = None) -> TurnParse:
        aliases = product_aliases or []
        raw = re.sub(r"\s+", "", text.strip())
        acts: list[SpeechAct] = []
        rest = raw

        start = re.match(r"开(.+?)的?单", rest)
        if start:
            mention = start.group(1)
            acts.append(SpeechAct(type="start_order", slots={"customer_mention": mention}, span=start.group(0)))
            rest = rest[start.end() :]

        while rest:
            rest = rest.lstrip("，,。；;")
            if not rest:
                break
            if rest.startswith("好了") or rest.startswith("就这些"):
                acts.append(SpeechAct(type="confirm_order", span="好了"))
                rest = rest[2:] if rest.startswith("好了") else rest[3:]
                continue
            if rest.startswith("这单作废") or rest.startswith("作废"):
                acts.append(SpeechAct(type="cancel_order"))
                break

            correction = False
            if rest.startswith("不对"):
                correction = True
                rest = rest[2:]

            op = "set"
            if rest.startswith("再加") or rest.startswith("再来"):
                op = "add"
                rest = rest[2:]
            elif rest.startswith("加"):
                op = "add"
                rest = rest[1:]
            elif rest.startswith("不要") or rest.startswith("去掉"):
                op = "remove"
                rest = rest[2:]

            if rest.startswith("改成") or rest.startswith("改到"):
                rest = rest[2:]
                op = "set"
            elif rest.startswith("改"):
                rest = rest[1:]
                op = "set"

            qty, uom, rest = self._consume_qty(rest)
            product, rest = self._consume_product(rest, aliases)
            if rest.startswith("改成") or rest.startswith("改到"):
                rest = rest[2:]
            elif rest.startswith("改"):
                rest = rest[1:]
            if qty is None:
                qty, uom, rest = self._consume_qty(rest)

            if rest.startswith("不要了"):
                acts.append(
                    SpeechAct(
                        type="remove_line",
                        slots={"product_mention": product} if product else {},
                        span=product,
                    )
                )
                rest = rest[3:]
                continue

            if op == "remove":
                acts.append(SpeechAct(type="remove_line", slots={"product_mention": product} if product else {}))
                continue

            if qty is None and product is None:
                acts.append(SpeechAct(type="unknown", slots={"text": rest}))
                break

            slots: dict = {}
            if product:
                slots["product_mention"] = product
            if qty is not None:
                slots["qty"] = qty
            if uom:
                slots["uom"] = uom
            slots["mode"] = op

            if correction:
                act_type = "set_qty"
                slots["mode"] = "set"
            elif op == "add" and product:
                act_type = "add_line"
            elif op == "add" and not product:
                act_type = "set_qty"
                slots["mode"] = "add"
            elif product and qty is not None:
                act_type = "set_line"
            else:
                act_type = "set_qty"
                slots["mode"] = "set"

            acts.append(SpeechAct(type=act_type, slots=slots, span=product))

        if not acts:
            acts.append(SpeechAct(type="clarify", slots={"mention": raw}, span=raw))

        return TurnParse(raw_text=text, acts=acts, is_final=True)

    def _consume_product(self, rest: str, aliases: list[tuple[str, UUID]]) -> tuple[str | None, str]:
        for alias, _node_id in aliases:
            if rest.startswith(alias):
                return alias, rest[len(alias) :]
        return None, rest

    def _consume_qty(self, rest: str) -> tuple[int | None, str | None, str]:
        match = re.match(rf"^(\d+|[一二两三四五六七八九十]+)([{_UNITS}])?", rest)
        if not match:
            return None, None, rest
        qty = parse_cn_number(match.group(1))
        uom = match.group(2)
        return qty, uom, rest[match.end() :]
