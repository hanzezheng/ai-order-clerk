# ADR-003

标题：业务 Session 设计

- 状态：accepted
- 日期：2026-08-16

## 背景

Voice-first 开单需要在一次任务里维护客户、草稿行、focus 行、分级 Issue。若把 Session 做成 IM 聊天室，后续采购、付款、库存会全部塞进同一张图。

## 问题

如何让当前销售开单可实现，同时不堵死其它业务任务？

## 决策

当前实现：

- `SalesSession`：一次给某客户开销售草稿的任务上下文（结构化 working_state，不是聊天全文）。

未来支持统一的 `BusinessSession`：

- `SalesSession`
- `PurchaseSession`
- `PaymentSession`
- `InventorySession`

共享（不复制进各图）：

- SpeechAct
- Memory
- Policy
- Entity Resolver（客户 / 商品本体）

销售确认只发 outbox 事件。禁止在 `SalesSession.confirm` 里扣库存、收款、生成采购单。

## 原因

档口对话是「任务」不是「聊天」。销售、采购、付款的确认闸门不同，必须分会话类型，内核复用。

## 影响

- 好处：阶段 2 加采购/库存时不必推翻开单图。
- 限制：第一阶段只落地 SalesSession；会话类型字段必须预留，禁止写死「全局只有一种 session」。
