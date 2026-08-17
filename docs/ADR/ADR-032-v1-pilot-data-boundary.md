# ADR-032

标题：V1 Pilot 只用最小企业事实切片；缺数据问老板，不建 CRM

- 状态：proposed
- 日期：2026-08-17

## 背景

观察表已规定失败可记「数据不足」。若不划清目录边界，试班容易做成客户管理、自动建档、或让模型猜人猜货。

边界：[V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md](../V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md)。服从 [RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)、[ADR-009](ADR-009-memory-from-confirm-events.md)。

## 问题

真实 Pilot 需要准备哪些企业事实？缺了是猜、是建 CRM，还是问老板？

## 决策

1. 本阶段 **不开发 CRM / 客户管理，不扩展 ERP**。不改 Runtime / Confirm Gate，不新增 Agent，不引入库存/支付/财务。
2. AI 不创造企业事实。ERP/纸本提供事实。Runtime 用事实理解和确认。
3. 客户允许：`customer_id`、name、alias、phone、address、tags（tags 只承载档口等消歧，须能投影 `stall_no`）。禁止自动生成画像、自动创建客户、自动改资料。
4. 商品允许：`item_id`、product name、spec、alias。禁止 AI 创建或修改 SKU。
5. Memory 只来自 `order.confirmed`。禁止聊天、LLM 猜测、未确认订单。
6. 一档口下限：客户 ≥ 5（含 1 组同名）、叶 SKU ≥ 5、历史订单 0 即可、默认习惯按需人标。
7. 没有数据：询问老板，人补目录。不是猜。

## 原因

开单员认人认货靠目录切片，不靠客户系统。划清边界才能把「数据不足」从「再做一个功能」里拆出来。

## 影响

- 好处：进摊前知道抄哪些字段；缺了有行为，不靠猜。
- 限制：地址/标签不新增 Runtime 字段；冷启动不作为 Pilot 数据策略。
