from __future__ import annotations

import re

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
_QTY = rf"(?:\d+|[一二两三四五六七八九十]+)[{_UNITS}]?"
_PRICE = r"按(?:\d+|[一二两三四五六七八九十]+)(?:块|元)"
_MARKERS = [
    "好了",
    "就这些",
    "不对",
    "再加",
    "再来",
    "不要了",
    "不要",
    "去掉",
    "改成",
    "改到",
    "加",
    "改",
    _PRICE,
    _QTY,
]


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
    """文本 → SpeechAct。禁止访问本体、客户、价格记忆。"""

    def parse(self, text: str) -> TurnParse:
        raw = re.sub(r"\s+", "", text.strip())
        acts: list[SpeechAct] = []
        rest = raw
        start = re.match(r"开(.+?)的?单", rest)
        if start:
            acts.append(
                SpeechAct(type="start_order", slots={"customer_mention": start.group(1)}, span=start.group(0))
            )
            rest = rest[start.end() :]
        tokens = self._tokenize(rest)
        acts.extend(self._fold(tokens))
        if not acts:
            acts.append(SpeechAct(type="clarify", slots={"mention": raw}, span=raw))
        return TurnParse(raw_text=text, acts=acts, is_final=True)

    def _tokenize(self, text: str) -> list[tuple[str, str]]:
        if not text:
            return []
        pattern = "(" + "|".join(_MARKERS) + ")"
        bits = [bit for bit in re.split(pattern, text) if bit]
        out: list[tuple[str, str]] = []
        for bit in bits:
            if bit in {"好了", "就这些"}:
                out.append(("confirm", bit))
            elif bit == "不对":
                out.append(("correction", bit))
            elif bit in {"再加", "再来"}:
                out.append(("add", bit))
            elif bit == "加":
                out.append(("add", bit))
            elif bit in {"不要了", "不要", "去掉"}:
                out.append(("remove", bit))
            elif bit in {"改成", "改到", "改"}:
                out.append(("revise", bit))
            elif re.fullmatch(_PRICE, bit):
                out.append(("price", bit))
            elif re.fullmatch(_QTY, bit):
                out.append(("qty", bit))
            else:
                out.append(("text", bit))
        return out

    def _fold(self, tokens: list[tuple[str, str]]) -> list[SpeechAct]:
        acts: list[SpeechAct] = []
        correction = False
        op = "set"
        product: str | None = None
        qty: int | None = None
        uom: str | None = None
        price: int | None = None
        price_uom: str | None = None

        def emit() -> None:
            nonlocal correction, op, product, qty, uom, price, price_uom
            if price is not None:
                slots = {"unit_price": price, "price_uom": price_uom or "块", "mode": "set"}
                if product:
                    slots["product_mention"] = product
                acts.append(SpeechAct(type="set_price", slots=slots, span=product))
            elif op == "remove":
                acts.append(SpeechAct(type="remove_line", slots={"product_mention": product} if product else {}))
            elif correction or (qty is not None and not product and op == "set"):
                slots = {"mode": "set"}
                if product:
                    slots["product_mention"] = product
                if qty is not None:
                    slots["qty"] = qty
                if uom:
                    slots["uom"] = uom
                if product and qty is None:
                    acts.append(SpeechAct(type="refine_spec", slots={"product_mention": product}, span=product))
                else:
                    acts.append(SpeechAct(type="set_qty", slots=slots, span=product))
            elif op == "add" and product:
                slots = {"product_mention": product, "mode": "add"}
                if qty is not None:
                    slots["qty"] = qty
                if uom:
                    slots["uom"] = uom
                acts.append(SpeechAct(type="add_line", slots=slots, span=product))
            elif op == "add" and qty is not None:
                slots = {"qty": qty, "mode": "add"}
                if uom:
                    slots["uom"] = uom
                acts.append(SpeechAct(type="set_qty", slots=slots))
            elif product and qty is not None:
                slots = {"product_mention": product, "qty": qty, "mode": "set"}
                if uom:
                    slots["uom"] = uom
                acts.append(SpeechAct(type="set_line", slots=slots, span=product))
            elif product and op == "set" and qty is None:
                acts.append(SpeechAct(type="refine_spec", slots={"product_mention": product}, span=product))
            correction = False
            op = "set"
            product = None
            qty = None
            uom = None
            price = None
            price_uom = None

        def has_pending() -> bool:
            return bool(product or qty is not None or price is not None or correction or op != "set")

        for i, (kind, val) in enumerate(tokens):
            nxt = tokens[i + 1][0] if i + 1 < len(tokens) else None
            if kind == "confirm":
                if has_pending() and (product or qty is not None or price is not None):
                    emit()
                acts.append(SpeechAct(type="confirm_order", span="好了"))
                continue
            if kind == "correction":
                if product or qty is not None:
                    emit()
                correction = True
                continue
            if kind == "add":
                if product or qty is not None:
                    emit()
                op = "add"
                continue
            if kind == "remove":
                if product or qty is not None:
                    emit()
                op = "remove"
                continue
            if kind == "revise":
                continue
            if kind == "price":
                number = re.search(r"(\d+|[一二两三四五六七八九十]+)", val)
                price = parse_cn_number(number.group(1)) if number else None
                price_uom = "块"
                if product or nxt != "text":
                    emit()
                continue
            if kind == "qty":
                qmatch = re.match(rf"^(\d+|[一二两三四五六七八九十]+)([{_UNITS}])?$", val)
                qty = parse_cn_number(qmatch.group(1)) if qmatch else None
                uom = qmatch.group(2) if qmatch else None
                if product:
                    emit()
                elif correction and nxt != "text":
                    emit()
                elif op == "add" and nxt != "text":
                    emit()
                continue
            if kind == "text":
                product = val
                if qty is not None or price is not None or op == "remove":
                    emit()
                elif correction and nxt not in {"qty", "revise"}:
                    emit()
                elif nxt in {None, "confirm", "correction", "add", "remove"}:
                    emit()
        if product or qty is not None or price is not None:
            emit()
        return acts
