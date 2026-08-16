"""G1–G4 金脚本步骤与断言。只读 Runtime 结果，不改闸门。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from uuid import UUID, uuid5, NAMESPACE_DNS

from app.entity.speech import SpeechAct, TurnParse
from app.services.product_understanding import ProductUnderstanding


def _uid(key: str) -> UUID:
    return uuid5(NAMESPACE_DNS, f"ai-order-clerk:{key}")


APPLE = _uid("node:apple")
FUJI80 = _uid("node:fuji80")
GOLDEN_SKU = _uid("node:golden-sku")
PEAR_SKU = _uid("node:pear-sku")
WANG_QIANG = _uid("customer:wang-qiang")
WANG_JI = _uid("customer:wang-ji")
LI_BOSS = _uid("customer:li")


@dataclass
class StepFailure:
    taxonomy: str
    message: str


@dataclass
class StepContext:
    session: Any
    result: Any
    parsed: TurnParse
    catalog: Any
    nodes_before: set[Any]
    aliases_before: list[Any]
    markers: dict[str, Any]


CheckFn = Callable[[StepContext], list[StepFailure]]


@dataclass
class StepSpec:
    text: str
    fake_acts: list[dict[str, Any]]
    checks: list[CheckFn] = field(default_factory=list)
    expect_more: bool = False


@dataclass
class ScriptSpec:
    script_id: str
    title: str
    steps: list[StepSpec]


def queries_from_acts(acts: list[SpeechAct]) -> list[dict[str, Any]]:
    understanding = ProductUnderstanding()
    out: list[dict[str, Any]] = []
    for act in acts:
        if act.type not in {"set_line", "add_line", "refine_spec"}:
            continue
        spec = act.slots.get("spec_mention")
        query = understanding.interpret(
            product_mention=str(act.slots.get("product_mention") or ""),
            spec_mention=str(spec) if spec else None,
        )
        dumped = query.model_dump(mode="json")
        dumped.pop("focus_node_id", None)
        out.append(dumped)
    return out


def issues_of(result: Any) -> list[str]:
    return [item.code for item in result.verdict.issues]


def line_named(session: Any, needle: str) -> Any | None:
    for line in session.draft.lines:
        blob = (line.mention.raw or "") + (
            line.mention.matched_node.name if line.mention.matched_node else ""
        )
        if needle in blob:
            return line
    return None


def fail_l0(ctx: StepContext) -> list[StepFailure]:
    for act in ctx.parsed.acts:
        blob = json.dumps(act.slots, ensure_ascii=False)
        if any(key in act.slots for key in ("sku_id", "product_id", "customer_id")):
            return [StepFailure("guessed_sku", "Parser 槽位出现业务 id")]
        if "王强水果店" in blob:
            return [StepFailure("guessed_customer", "Parser 写出店名全称")]
        if "红富士80果一级烟台箱装" in blob:
            return [StepFailure("guessed_sku", "Parser 写出 SKU 全称")]
    return []


def fail_fallback(ctx: StepContext) -> list[StepFailure]:
    if ctx.parsed.fallback and ctx.parsed.parser_name == "rule":
        return [StepFailure("fallback", ctx.parsed.fallback_reason or "fallback_to_rule")]
    return []


def _g1_open(ctx: StepContext) -> list[StepFailure]:
    fails: list[StepFailure] = []
    if "customer_ambiguous" not in issues_of(ctx.result):
        fails.append(StepFailure("wrong_act", f"应询问消歧，issues={issues_of(ctx.result)}"))
    if ctx.session.draft.customer is not None:
        fails.append(StepFailure("guessed_customer", "未消歧就绑定了客户"))
    if ctx.session.draft.customer and ctx.session.draft.customer.id == WANG_QIANG:
        fails.append(StepFailure("guessed_customer", "选成了王强水果店"))
    return fails


def _g1_bind(ctx: StepContext) -> list[StepFailure]:
    customer = ctx.session.draft.customer
    if customer is None or customer.id != WANG_JI:
        return [StepFailure("wrong_act", f"未绑定王记，得到 {customer}")]
    return []


def _g1_apple(ctx: StepContext) -> list[StepFailure]:
    apple = line_named(ctx.session, "苹果")
    if apple is None:
        return [StepFailure("wrong_act", "没有苹果行")]
    ctx.markers["apple_line_id"] = apple.line_id
    if apple.product_sku_id is not None:
        return [StepFailure("guessed_sku", "无规格苹果不应落到 SKU")]
    return []


def _g1_pear(ctx: StepContext) -> list[StepFailure]:
    pear = line_named(ctx.session, "梨")
    if pear is None:
        return [StepFailure("wrong_act", "没有梨行")]
    if pear.product_sku_id not in {PEAR_SKU, None}:
        return [StepFailure("guessed_sku", f"梨落到意外 SKU {pear.product_sku_id}")]
    return []


def _g1_durian(ctx: StepContext) -> list[StepFailure]:
    durian = line_named(ctx.session, "金边") or line_named(ctx.session, "榴莲")
    if durian is None:
        return [StepFailure("wrong_act", "没有榴莲行")]
    ctx.markers["durian_line_id"] = durian.line_id
    if str(durian.qty.value) != "2":
        return [StepFailure("wrong_act", f"榴莲数量应为 2，得到 {durian.qty.value}")]
    return []


def _g1_spec(ctx: StepContext) -> list[StepFailure]:
    apple = line_named(ctx.session, "苹果")
    if apple is None:
        return [StepFailure("wrong_act", "规格步丢失苹果行")]
    fails: list[StepFailure] = []
    if ctx.markers.get("apple_line_id") and apple.line_id != ctx.markers["apple_line_id"]:
        fails.append(StepFailure("lost_focus", "苹果 refine 裂行"))
    if apple.product_sku_id != FUJI80:
        fails.append(StepFailure("spec_lost", f"苹果未提升 FUJI80，得到 {apple.product_sku_id}"))
    if len(ctx.session.draft.lines) != 3:
        fails.append(StepFailure("wrong_act", f"行数应变 3，得到 {len(ctx.session.draft.lines)}"))
    attrs: dict[str, str] = {}
    for query in queries_from_acts(list(ctx.parsed.acts)):
        attrs.update(query.get("attributes") or {})
        if "sku_id" in query:
            fails.append(StepFailure("guessed_sku", "ProductQuery 含 sku_id"))
    if "size" not in attrs and "origin" not in attrs:
        fails.append(StepFailure("spec_lost", f"ProductQuery 未抽出规格 {attrs}"))
    return fails


def _g1_qty(ctx: StepContext) -> list[StepFailure]:
    durian = line_named(ctx.session, "金边") or line_named(ctx.session, "榴莲")
    if durian is None:
        return [StepFailure("wrong_act", "改口后没有榴莲行")]
    fails: list[StepFailure] = []
    if ctx.markers.get("durian_line_id") and durian.line_id != ctx.markers["durian_line_id"]:
        fails.append(StepFailure("lost_focus", "榴莲改口裂行"))
    if str(durian.qty.value) != "3":
        fails.append(StepFailure("wrong_act", f"榴莲数量应为 3，得到 {durian.qty.value}"))
    if len(ctx.session.draft.lines) != 3:
        fails.append(StepFailure("wrong_act", "改口后行数变化"))
    return fails


def _g1_confirm(ctx: StepContext) -> list[StepFailure]:
    if not ctx.result.verdict.confirm_ok:
        return [StepFailure("wrong_act", f"G1 未能确认，issues={issues_of(ctx.result)}")]
    if {node.id for node in ctx.catalog.list_nodes()} != ctx.nodes_before:
        return [StepFailure("guessed_sku", "确认后 Catalog 节点变化")]
    apple = line_named(ctx.session, "苹果")
    if apple is None or apple.product_sku_id != FUJI80:
        return [StepFailure("spec_lost", "确认时苹果不是 FUJI80")]
    return []


def _g2_bind(ctx: StepContext) -> list[StepFailure]:
    customer = ctx.session.draft.customer
    if customer is None or customer.id != LI_BOSS:
        return [StepFailure("wrong_act", f"未绑定李老板，得到 {customer}")]
    return []


def _g2_apple(ctx: StepContext) -> list[StepFailure]:
    if not ctx.session.draft.lines:
        return [StepFailure("wrong_act", "没有苹果行")]
    line = ctx.session.draft.lines[0]
    ctx.markers["apple_line_id"] = line.line_id
    if line.product_sku_id != FUJI80:
        return [StepFailure("wrong_act", f"档案默认应为 FUJI80，得到 {line.product_sku_id}")]
    return []


def _g2_tonghuo(ctx: StepContext) -> list[StepFailure]:
    if not ctx.session.draft.lines:
        return [StepFailure("wrong_act", "统货后丢行")]
    line = ctx.session.draft.lines[0]
    fails: list[StepFailure] = []
    if ctx.markers.get("apple_line_id") and line.line_id != ctx.markers["apple_line_id"]:
        fails.append(StepFailure("lost_focus", "统货裂行"))
    profile = ctx.catalog.get_profile(LI_BOSS)
    if profile is None or profile.product_defaults.get(str(APPLE)) != FUJI80:
        fails.append(StepFailure("wrong_act", "统货改口写了 product_default"))
    if {node.id for node in ctx.catalog.list_nodes()} != ctx.nodes_before:
        fails.append(StepFailure("guessed_sku", "统货改口新建了节点"))
    return fails


def _g2_add(ctx: StepContext) -> list[StepFailure]:
    if not ctx.session.draft.lines:
        return [StepFailure("wrong_act", "加量后丢行")]
    line = ctx.session.draft.lines[0]
    if str(line.qty.value) != "80":
        return [StepFailure("wrong_act", f"再加20 后应为 80，得到 {line.qty.value}")]
    if len(ctx.session.draft.lines) != 1:
        return [StepFailure("wrong_act", "加量不应新开苹果行")]
    return []


def _g2_confirm(ctx: StepContext) -> list[StepFailure]:
    if not ctx.result.verdict.confirm_ok:
        return [StepFailure("wrong_act", f"G2 未能确认，issues={issues_of(ctx.result)}")]
    profile = ctx.catalog.get_profile(LI_BOSS)
    if profile is None or profile.product_defaults.get(str(APPLE)) != FUJI80:
        return [StepFailure("wrong_act", "确认后档案默认被改写")]
    return []


def _g3_burst(ctx: StepContext) -> list[StepFailure]:
    apple = line_named(ctx.session, "苹果")
    pear = line_named(ctx.session, "梨")
    if apple is None or pear is None:
        return [StepFailure("wrong_act", "连报丢了苹果或梨")]
    fails: list[StepFailure] = []
    if apple.product_sku_id is not None:
        fails.append(StepFailure("guessed_sku", "连报苹果被猜成 SKU"))
    if pear.product_sku_id is None:
        fails.append(StepFailure("wrong_act", "梨未写入可履约行"))
    if "product_ambiguous" not in issues_of(ctx.result):
        fails.append(StepFailure("wrong_act", "苹果歧义未保持 line_hold"))
    if ctx.result.verdict.reply_mode != "ack":
        fails.append(StepFailure("wrong_act", f"expect_more 应为 ack，得到 {ctx.result.verdict.reply_mode}"))
    return fails


def _g3_confirm(ctx: StepContext) -> list[StepFailure]:
    if ctx.result.verdict.confirm_ok:
        return [StepFailure("confirm_violation", "苹果无 SKU 时不得确认")]
    if line_named(ctx.session, "梨") is None:
        return [StepFailure("wrong_act", "确认失败时梨行被丢掉")]
    return []


def _g4_unknown_product(ctx: StepContext) -> list[StepFailure]:
    fails: list[StepFailure] = []
    kept = any(m.raw and "紫麒麟" in m.raw for m in ctx.session.product_mention_candidates) or any(
        "紫麒麟" in (line.mention.raw or "") for line in ctx.session.draft.lines
    )
    if not kept:
        fails.append(StepFailure("wrong_act", "未知商品未留下 mention/candidate"))
    if any(line.product_sku_id is not None for line in ctx.session.draft.lines):
        fails.append(StepFailure("guessed_sku", "紫麒麟被落到已有 SKU"))
    if {node.id for node in ctx.catalog.list_nodes()} != ctx.nodes_before:
        fails.append(StepFailure("guessed_sku", "紫麒麟创建了节点"))
    if ctx.catalog.aliases.snapshot() != ctx.aliases_before:
        fails.append(StepFailure("guessed_sku", "紫麒麟写了 Alias"))
    return fails


def _g4_no_sub(ctx: StepContext) -> list[StepFailure]:
    fails: list[StepFailure] = []
    if any(line.product_sku_id == GOLDEN_SKU for line in ctx.session.draft.lines):
        fails.append(StepFailure("guessed_sku", "金枕被替成金边"))
    if {node.id for node in ctx.catalog.list_nodes()} != ctx.nodes_before:
        fails.append(StepFailure("guessed_sku", "金枕创建了节点"))
    return fails


def _g4_old_price(ctx: StepContext) -> list[StepFailure]:
    types = [act.type for act in ctx.parsed.acts]
    if "use_old_price" not in types:
        return [StepFailure("wrong_act", f"应为 use_old_price，得到 {types}")]
    if any(act.slots.get("unit_price") is not None for act in ctx.parsed.acts):
        return [StepFailure("wrong_act", "老价格编造了单价")]
    return []


def admission_scripts() -> list[ScriptSpec]:
    return [
        ScriptSpec(
            "G1",
            "王记规格闭环",
            [
                StepSpec("开王老板的单", [{"type": "start_order", "slots": {"customer_mention": "王老板"}}], [_g1_open]),
                StepSpec("王记水果店", [{"type": "clarify", "slots": {"mention": "王记水果店"}}], [_g1_bind]),
                StepSpec("苹果60件", [{"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}}], [_g1_apple]),
                StepSpec("梨60件", [{"type": "set_line", "slots": {"product_mention": "梨", "qty": 60, "uom": "件"}}], [_g1_pear]),
                StepSpec("加两个金边榴莲", [{"type": "add_line", "slots": {"product_mention": "金边榴莲", "qty": 2, "uom": "个"}}], [_g1_durian]),
                StepSpec(
                    "苹果要烟台八零果",
                    [{"type": "refine_spec", "slots": {"product_mention": "苹果", "spec_mention": "烟台八零果"}}],
                    [_g1_spec],
                ),
                StepSpec("金边榴莲改三个", [{"type": "set_qty", "slots": {"product_mention": "金边榴莲", "qty": 3}}], [_g1_qty]),
                StepSpec("好了", [{"type": "confirm_order", "slots": {}}], [_g1_confirm]),
            ],
        ),
        ScriptSpec(
            "G2",
            "李老板熟客闭环",
            [
                StepSpec("开李老板的单", [{"type": "start_order", "slots": {"customer_mention": "李老板"}}], [_g2_bind]),
                StepSpec("苹果60件", [{"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}}], [_g2_apple]),
                StepSpec("统货", [{"type": "refine_spec", "slots": {"spec_mention": "统货"}}], [_g2_tonghuo]),
                StepSpec("再加20", [{"type": "set_qty", "slots": {"qty": 20, "mode": "add"}}], [_g2_add]),
                StepSpec("好了", [{"type": "confirm_order", "slots": {}}], [_g2_confirm]),
            ],
        ),
        ScriptSpec(
            "G3",
            "连报不中断",
            [
                StepSpec("开王老板的单", [{"type": "start_order", "slots": {"customer_mention": "王老板"}}], [_g1_open]),
                StepSpec("王记水果店", [{"type": "clarify", "slots": {"mention": "王记水果店"}}], [_g1_bind]),
                StepSpec(
                    "苹果60件梨60件",
                    [
                        {"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}},
                        {"type": "set_line", "slots": {"product_mention": "梨", "qty": 60, "uom": "件"}},
                    ],
                    [_g3_burst],
                    expect_more=True,
                ),
                StepSpec("好了", [{"type": "confirm_order", "slots": {}}], [_g3_confirm]),
            ],
        ),
        ScriptSpec(
            "G4.1",
            "失败保持：未消歧客户",
            [StepSpec("开王老板的单", [{"type": "start_order", "slots": {"customer_mention": "王老板"}}], [_g1_open])],
        ),
        ScriptSpec(
            "G4.2",
            "失败保持：未知商品",
            [
                StepSpec("开李老板的单", [{"type": "start_order", "slots": {"customer_mention": "李老板"}}], [_g2_bind]),
                StepSpec("紫麒麟60件", [{"type": "set_line", "slots": {"product_mention": "紫麒麟", "qty": 60, "uom": "件"}}], [_g4_unknown_product]),
            ],
        ),
        ScriptSpec(
            "G4.3",
            "失败保持：替品",
            [
                StepSpec("开王老板的单", [{"type": "start_order", "slots": {"customer_mention": "王老板"}}], [_g1_open]),
                StepSpec("王记水果店", [{"type": "clarify", "slots": {"mention": "王记水果店"}}], [_g1_bind]),
                StepSpec("金枕60个", [{"type": "set_line", "slots": {"product_mention": "金枕", "qty": 60, "uom": "个"}}], [_g4_no_sub]),
            ],
        ),
        ScriptSpec(
            "G4.4",
            "失败保持：老价格",
            [
                StepSpec("开李老板的单", [{"type": "start_order", "slots": {"customer_mention": "李老板"}}], [_g2_bind]),
                StepSpec("苹果60件", [{"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}}], [_g2_apple]),
                StepSpec("还是以前那个价", [{"type": "use_old_price", "slots": {}}], [_g4_old_price]),
            ],
        ),
    ]


def fake_responses() -> dict[str, Any]:
    responses: dict[str, Any] = {}
    for script in admission_scripts():
        for step in script.steps:
            responses[step.text] = {"acts": step.fake_acts}
    return responses
