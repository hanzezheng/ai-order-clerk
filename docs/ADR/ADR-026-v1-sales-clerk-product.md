# ADR-026

标题：农批 AI 销售开单员 V1 = 喊单进账 + 今日开单本；不做收款 / 库存 / 第二员工

- 状态：proposed
- 日期：2026-08-17

## 背景

Runtime、Voice、ERPNext 读写、Memory、Workbench 已收口。岗位评审 [ADR-025](ADR-025-sales-employee-before-second.md) 已决定：第一个商业员工是开单员，不启动第二 Employee。

下一步若没有产品规格，容易把「V1」理解成再加功能：查账口令、确认后改单、库存挡确认、或开始做收款员。

产品规格：[V1_SALES_CLERK.md](../V1_SALES_CLERK.md)。用户旅程：[V1_SALES_CLERK_USER_JOURNEY.md](../V1_SALES_CLERK_USER_JOURNEY.md)、[ADR-027](ADR-027-v1-user-journey-current-order.md)。服从 [RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)。

## 问题

农批 AI 销售开单员 V1 覆盖老板一天的哪些步骤？哪些必须产品化？哪些明确不做？

## 决策

1. V1 岗位 = **农批 AI 销售开单员**。老板一天六步中，AI 主责是 **接单、改未确认单、确认**；**查看今日订单** 用眼睛看今日本 + 入账状态；开门 / 收摊的货与钱继续人工。
2. V1 **必须产品化**：喊着开单、未确认改口、同名消歧、价未定可确认、显式下一单、今日开单本、入账可见、确认留 Draft SO。实现只走 Input / Workbench 投影 / Adapter 投影。
3. V1 **明确不做**：收款、库存、财务、submit SO、查账口令、确认后改单、第二员工、ERP 驱动 `confirm_gate`、新 SpeechAct、改 Runtime Freeze。
4. 本文 V1 取代「下一步做什么」的模糊性；不废止 DESIGN §14 的 POC 开单壳，也不修改 Freeze 正文。

## 原因

档口一天的价值在「连着开完、改得动、定得了、收摊能对上开了哪些」。货和钱是相邻岗位。把那些做进 V1，会把 ERP 或财务变成决策层，并提前启动第二员工。

## 影响

- 好处：可雇故事与一天六步对齐；Freeze 可执行。
- 限制：收摊看不到已收款；已确认单不能喊着改；不能用嘴查 ERP。
