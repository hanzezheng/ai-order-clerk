# ADR-004

标题：业务规则不能交给 LLM

- 状态：accepted
- 日期：2026-08-16

## 背景

连报、同名客户、层级歧义、缺价不打断，都是确定性规则。若写进 prompt，模型会在「看起来可以」时确认或选错王老板。

## 问题

语言理解与业务裁决如何分工？

## 决策

LLM 负责：

- 理解语言
- 将一段话抽取为有序 `SpeechAct[]`（品名、数量、价的**提及**）

Policy 负责判断：

- 是否询问（`session_block` / `line_hold` / `notice`，以及 `ask_when`）
- 是否自动执行（档案默认、唯一子 SKU、可执行 act 先落地）
- 是否确认（`confirm_gate`；`expect_more` 时不得打断追问）

`DecisionVerdict` 模型不得否决。`OrderService.confirm_draft` 必须再跑同一闸门。

## 原因

农批错 SKU、错客户、把 TBD 说成成交，代价是真金白银。规则必须单测，不能靠 prompt 漂移。

## 影响

- 好处：连报部分成功、缺价可确认、同名必须问，行为可回归。
- 限制：新规则先改 DESIGN + Policy 表，禁止只改提示词。
