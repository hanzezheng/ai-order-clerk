# ADR-034

标题：V1 Pilot 接入是空本开张 + 切片投影；缺数据询问挂起，不实施 CRM/ERP

- 状态：proposed
- 日期：2026-08-17

## 背景

数据与访问边界已规定要哪些事实、怎么进 Catalog。若没有接入顺序，空白档口会做成：先上 CRM、先实施 ERP、或空目录让模型猜第一单。

闭环：[V1_SALES_CLERK_PILOT_FEEDBACK_LOOP.md](../V1_SALES_CLERK_PILOT_FEEDBACK_LOOP.md)、[ADR-035](ADR-035-v1-pilot-feedback-loop.md)。服从 [ADR-032](ADR-032-v1-pilot-data-boundary.md)、[ADR-033](ADR-033-v1-pilot-data-access.md)、[ADR-031](ADR-031-v1-pilot-observation.md)、[RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)。

## 问题

真实农批档口从接入到第一次使用，人要按什么流程？何时扩大、何时暂停？

## 决策

1. 本阶段 **不是 CRM、不是 ERP 实施工具、不加业务能力**。不改 Runtime / Confirm Gate，不新增 Agent，不引入库存/支付/财务。
2. 第一次使用前：能打开今日本、客户切片、商品切片、有人盯着。老板不需要学 ERP。
3. 初始化只要 Customer（id/name/alias/消歧）和 Product（id/name/spec/alias）。不要库存、欠款、财务。
4. 第一次开门：空本 + 按住说话。第一单喊切片里已有的客和货，好了后看今日本。
5. 没有张老板 → 询问；没有苹果 SKU → 挂起；等人补投影后再喊。不自动建档。
6. 第一周记：每天订单数、AI 参与比例、人工纠正、失败案例。
7. 结束只选 **扩大使用** 或 **暂停**。扩大仍有监督、只补切片；暂停不靠猜、不加功能。

## 原因

空白档口能用，靠的是空本可喊 + 最小事实已投影，不是新系统。接入流程把「从零到第一单」从开发清单里拆出来。

## 影响

- 好处：观察人有顺序；老板第一眼就是开单本；缺数据有等待补充，不靠实施工具。
- 限制：无切片不能假装已接入；第一周必须有人记。
