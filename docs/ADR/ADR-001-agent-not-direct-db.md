# ADR-001

标题：AI Agent 不能直接访问数据库

- 状态：accepted
- 日期：2026-08-16

## 背景

本项目由 AI 辅助长期开发。Agent / LLM 若直接写 SQL 或操作 ORM，会出现幻觉语句、绕过 Policy、污染订单与价格事实。`docs/DESIGN.md` 规定 Agent 只发 `ServiceCommand`。

## 问题

如何保证自然语言开单链路可审计、可测试，且业务规则不被模型改写？

## 决策

所有数据库操作必须走：

```
Agent → Tool → Service → Repository → Database
```

- Agent 禁止 import `app.models`、`app.database`，禁止拼 SQL。
- Tool 只接受已解析的结构化入参（ID、数量、单位），禁止 `raw_text` 入库存。
- Service 执行业务并调用 Policy 闸门（如 `confirm_draft` 再跑 confirm_gate）。
- Repository 是唯一持久化端口；Agent 不可见。

## 原因

避免：

- 幻觉 SQL
- 数据污染
- 业务绕过（未消歧客户、TBD 价当成交、未到 SKU 就确认）

## 影响

- 好处：落库路径单一，单测可绕过 LLM 打 Service。
- 限制：多一层工具封装；禁止「图节点里图省事直接 commit」。
