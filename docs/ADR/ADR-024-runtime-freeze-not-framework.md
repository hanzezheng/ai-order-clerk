# ADR-024

标题：冻结现网员工流水线；不引入通用 Agent 框架；不提前抽象平台

- 状态：accepted
- 日期：2026-08-17

## 背景

Runtime 已具备 Parser → Understanding → Resolver → Policy → OrderService → Memory / Outbox，以及 Voice 与 ERPNext Write。Read Adapter 已设计未实现。此时容易走三条错路：用 LangGraph/CrewAI 替换内核、抽一层「通用 Employee Runtime」平台、或把库存/收款塞进销售确认。

评审全文：[RUNTIME_FREEZE_REVIEW.md](../RUNTIME_FREEZE_REVIEW.md)。

## 问题

现网是否已经是可复用的 AI Employee 基础？下一阶段应增强销售、抽象平台，还是深入 ERP？要不要换成通用 Agent 框架？

## 决策

1. 现网冻结的是 **员工流水线**（语言 → 理解 → 裁决 → 执行 → 事件 → 适配器），不是已经成型的多员工平台。
2. **不**用 LangGraph、CrewAI、AutoGen、OpenAI Agents SDK 替换 `SalesSessionRunner`。LLM 不得拥有 tool 循环、不得直连业务库、不得替代 Policy。
3. **不**在第二个员工立项前抽象 Employee Runtime 框架。`SalesSession` / `OrderService` / 销售 SpeechAct 闭包保持销售专属。
4. **不**深入 ERPNext 业务能力（submit、库存、发票、收款、科目）。ERP 只经 Adapter；禁止 ERP 驱动 AI。
5. 下一阶段优先：按 ADR-023 落地 Read Adapter 投影；加层进口岸测试；销售加固不得破坏 `Parser → Resolver → Policy → Service`。

## 原因

可复用的是角色（Session 一张任务、Policy 不可被 LLM 绕过、Outbox 按 consumer 投递）。可复制的代码带着销售类型。框架默认把控制权交给模型，与 ADR-001/004/021 相反。深入 ERP 业务会把闸门绑到账本上。

## 影响

- 好处：平台化与框架替换被明确拒绝，Sprint 有否决权。
- 限制：采购/财务/仓仍只存在于路线图；`session_type` 不得当成已实现的多态。
