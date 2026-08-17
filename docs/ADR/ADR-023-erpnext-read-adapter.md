# ADR-023

标题：ERPNext 读取只经 Read Adapter 的领域查询；禁止 SQL/DocType 进 Runtime，禁止用账本指挥 Policy

- 状态：accepted
- 日期：2026-08-17

## 背景

V0.5 已能把 `order.confirmed` 写成 ERPNext Draft Sales Order。员工层要「读取企业事实」，若 OrderService / Policy / Parser 直查 DocType，会把 Runtime 做成 ERP 插件：库存挡确认、同名客户被覆盖、`item_code` 泄漏进领域模型。

Write 路径是 Outbox 推送，不能兼做查询：触发时机、失败域、调用者都不同。

## 问题

AI 员工如何看见公司账上已确认的销售事实，同时不改 Parser / Policy / Confirm Gate / OrderService / Memory，且不把 SQL、DocType、库存送进裁决？

## 决策

1. V0.6 增加 **ERPNext Read Adapter**（与 Write 同属 Adapter 层，独立端口）。禁止 Write Consumer 兼读。
2. Runtime 内核不查 ERP。装配层经 `EnterpriseFactPort` 使用 **领域键**（`runtime_order_id` / `runtime_customer_id`）查询；Adapter 在内部做 correlation 与 GET。
3. 写仍是 `Domain Event → Outbox → Write Adapter`。读是同步领域查询，不用第二套 Outbox。
4. 白名单：只读 V0.5 已写的 Draft Sales Order 投递状态（及可选的客户未过账计数）。黑名单：库存、支付、财务、Item 搜索、Customer 模糊搜、submit 单据。
5. 领域事实进入 **Workbench / Session 投影**（`EnterpriseFacts`）。**不**进入 `BusinessContext`、`OrderLine`、Catalog、Memory。`query_draft` 语义不变。
6. Policy / Confirm Gate 不得读取这些事实。ERP 失败 → `unavailable`，不改 `confirm_ok`、不改口播。
7. 本阶段不新增 SpeechAct，不改 `reply_text`。口播账本须另批，且只能走 Policy **notice**，不得动闸门。

细则：[V06_ERPNEXT_READ_ADAPTER.md](../V06_ERPNEXT_READ_ADAPTER.md)。

本决策扩展 [ADR-021](ADR-021-ai-employee-runtime.md) / [ADR-022](ADR-022-erpnext-adapter-not-runtime.md)：ERP 仍只经 Adapter；连接方式按方向拆成写（Outbox）与读（Query Port）。

## 原因

看见账本与听从账本是两件事。员工要对账（这张确认单进草稿了没有），但不能让可用量、信用、定价单改开单闸门。领域端口把 DocType 留在 Adapter，Policy 输入才能保持冻结。

## 影响

- 好处：V0.5 确认契约不变；CI 仍 Fake；换 ERP 供应商只换 Read 实现。
- 限制：V0.6 员工用投影看见账本，不用嘴说；「查李老板的账」要等 Parser 解冻；读与写短暂不一致（`pending`）是允许的。
