# ADR-021

标题：AI Employee Runtime 为最高架构约束；ERPNext 只经 Outbox Adapter 连接

- 状态：accepted
- 日期：2026-08-16

## 背景

仓库已具备 Parser → Understanding → Resolver → Policy → OrderService → Memory / Outbox，以及 Voice Adapter。若后续按「再做一个功能」推进，容易把 ERP 逻辑、聊天记录、LLM 裁决塞进 Runtime，把开单员做成 ERP 聊天框。

## 问题

什么文件约束分层与权限？Sprint 如何防止架构漂移？ERP 将来接在哪？

## 决策

1. `docs/AI_EMPLOYEE_ARCHITECTURE.md` 是后续开发的**最高架构约束**。Cursor 规则（`.cursorrules`、`.cursor/rules/ai-employee-architecture.mdc`）必须引用它。
2. [DESIGN.md](../DESIGN.md) 仍是农批开单员的产品设计细则；与本架构冲突时，先守分层与 LLM/Policy/Memory 权限，再改 DESIGN。
3. ERPNext 是事实系统；连接路径固定为 `Domain Event → Outbox → ERPNext Adapter`。禁止 Domain Service 直调 ERP API。V0.5 设计见 [V05_ERPNEXT_ADAPTER.md](../V05_ERPNEXT_ADAPTER.md)；实现不得进入 Runtime 裁决层。
4. 每个 Sprint / PR 必须声明：遵守本架构、只允许修改哪一层、冻结哪些层。禁止只写「做 Sprint X」。
5. 设计评审必须回答架构文 §7 六问。不确定则冻结 Runtime。

## 原因

员工层与 ERP 层分离，才能换行业 Agent 而不推翻开单图，也才能接 ERP 而不把表结构泄漏进 Parser / Policy。

## 影响

- 好处：分层权限可检查；Sprint 范围可审计；ERP 有唯一入口。
- 限制：当前不做多 Agent、不做平台、不做 ERP 实现；局部「方便」的跨层调用一律拒绝。
