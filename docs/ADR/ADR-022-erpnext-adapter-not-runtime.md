# ADR-022

标题：ERPNext 只经 Outbox Adapter 接收已确认销售事实；不进 Runtime 裁决

- 状态：proposed
- 日期：2026-08-16

## 背景

Runtime 已能确认开单，Outbox 已是可靠事实出口。战略上 ERPNext 是企业事实系统，AI 是自然语言执行层。若 OrderService 直调 ERP API，或用库存/金额反写 `confirm_gate`，会把员工层做成 ERP 插件，并污染 Catalog / Memory。

## 问题

确认后的客户、SKU、数量、TBD 价如何进入 ERPNext，同时不改 Parser / Policy / OrderService / Memory，且不把 `item_code` 写进领域模型？

## 决策

1. V0.5 只增加 **ERPNext Adapter**：Outbox consumer `erpnext_adapter`，订阅 `order.confirmed`。
2. 路径固定：`Domain Event → Outbox → Adapter → ERPNext`。禁止 Domain Service 调 ERP。
3. Adapter 读已确认 `SalesSession` 快照做翻译；**不扩大** `OrderService.confirm` 的 payload（冻结）。
4. 映射：Runtime 客户 → Customer；叶 SKU → Item；一确认单 → 一张 **Draft** Sales Order。TBD 价用 `prices_incomplete` + 占位 rate。禁止 submit、禁止 `update_stock`、禁止发票与收款。
5. `item_code` / DocType / naming_series 只存在 Adapter 与 correlation 表。禁止写入 `OrderLine` / `ProductNode` / SpeechAct。
6. ERP 失败只重试 Adapter，不回滚 Runtime 确认，不改口播，不让 LLM 参与。
7. 当前不做库存、支付、财务、以 ERP 为 Catalog 真相、反向同步。

细则：[V05_ERPNEXT_ADAPTER.md](../V05_ERPNEXT_ADAPTER.md)。

## 原因

确认闸门是档口产品语义（可 TBD）。ERP 是入账。分开才能既接事实系统，又不让表结构驱动开单员。

## 影响

- 好处：Runtime 测试与 G1–G4 不变；ERP 可 Fake；换 ERP 供应商只换 Gateway。
- 限制：确认与入账最终一致靠重试，不是同一事务；V0.5 SO 保持 Draft，不是已过账销售。
