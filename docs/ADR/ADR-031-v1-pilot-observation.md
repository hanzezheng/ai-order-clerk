# ADR-031

标题：V1 Pilot 用观察表收反馈；结束时只选 V1.1 或调整流程

- 状态：proposed
- 日期：2026-08-17

## 背景

检查清单已允许有监督进档口。若试班不记账，容易事后只修 bug，或把「功能多」当成成功。

观察表：[V1_SALES_CLERK_PILOT_OBSERVATION.md](../V1_SALES_CLERK_PILOT_OBSERVATION.md)。进摊条件：[V1_SALES_CLERK_PILOT_CHECKLIST.md](../V1_SALES_CLERK_PILOT_CHECKLIST.md)。数据边界：[V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md](../V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md)、[ADR-032](ADR-032-v1-pilot-data-boundary.md)。服从 [RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)。

## 问题

真实档口试用记什么？怎样判断继续 V1.1 还是改产品流程？

## 决策

1. 本阶段 **不开发新功能**。不改 Runtime / Confirm Gate，不新增 Agent，不引入库存/支付/财务。
2. 只验证少手写、少重复确认、少翻聊天。不验证替代老板、无人值守。
3. 每日记：订单数、使用次数、成功开单、失败、人工介入；效率、信任、错误四类。
4. 每个失败单独记：老板说什么、AI 理解什么、正确结果、主因（数据不足 / 产品设计 / Runtime）。原话沉淀为语言资产，不进 Memory。
5. 结束只选：**继续 V1.1**（冻结外侧打磨）或 **调整产品流程**（先改旅程/工作台，不加功能）。
6. 成功标准：老板感觉「确实帮我少记单」，不是「AI 功能很多」。

## 原因

没有观察表，试班会变成加功能。有表才能把失败收成农批口语资产，并决定要不要动流程。

## 影响

- 好处：反馈可执行；结束判断只有两条路。
- 限制：要有观察人；不自动采集埋点。
