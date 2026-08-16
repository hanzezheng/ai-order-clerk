# ADR-006

标题：ResponseGenerator 不得修改 Policy 决策

- 状态：accepted
- 日期：2026-08-16

## 背景

开单员要对老板说话。若把中文回复写在 Runner 或 Policy 里，话术和裁决会缠在一起。若让生成模型自己决定问不问、补不补价，会绕过 `DecisionVerdict`。

## 问题

谁决定「说什么」，谁决定「怎么说」？

## 决策

Policy 负责：

- `reply_mode`（`ack` / `recap` / `ask`）
- Issue 分级与 `ask_when`
- `confirm_ok`

ReplyPlanner 负责：把已聚合的 verdict + 会话快照 + 本回合变更行压成 `ReplyPlan`（含 `reply_scope`、`source_refs`）。不改裁决。

ResponseGenerator 负责：只读 `ReplyPlan`，拼出口播。禁止：

- 修改 `DecisionVerdict` / `confirm_ok` / `reply_mode`
- 访问 Catalog、Profile、PriceMemory、Session
- 写入 Memory 或草稿

ReplyGrounder 负责：白名单核对，回复中的数字、价格、SKU、客户名必须来自 `source_refs`。

Sprint 4A 仅实现 `TemplateResponseGenerator`。未来 LLM 润色必须吃同一 `ReplyPlan`，失败回模板。

## 原因

档口说错客户、说错 SKU、把 TBD 说成成交，是真金白银。话术可以换，闸门不能换。这是 ADR-004 在表达层的对偶。

## 影响

- 好处：连报 ack 可缩短；未消歧不会泄露档案默认；回复可单测。
- 限制：Generator 不能「多说一句关心」；新话术先改 Plan/虚词表，禁止在模板里写死业务数字。
