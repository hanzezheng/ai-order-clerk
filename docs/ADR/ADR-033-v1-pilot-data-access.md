# ADR-033

标题：V1 Pilot 企业事实只经 Read Adapter 投影进 Catalog；回合中 Runtime 不查 ERP

- 状态：proposed
- 日期：2026-08-17

## 背景

数据边界已规定认人认货要哪些字段。若 Resolver / Policy 直查 ERP Customer / Item，会把 Runtime 做成 ERP 插件：模糊搜点选客户、库存挡确认、DocType 进领域。

访问：[V1_SALES_CLERK_PILOT_DATA_ACCESS.md](../V1_SALES_CLERK_PILOT_DATA_ACCESS.md)。服从 [V06_ERPNEXT_READ_ADAPTER.md](../V06_ERPNEXT_READ_ADAPTER.md)、[ADR-023](ADR-023-erpnext-read-adapter.md)、[ADR-032](ADR-032-v1-pilot-data-boundary.md)、[RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)。

## 问题

真实 Pilot 中，Customer / Product 企业事实如何进入 Runtime，同时不让 ERP 控制 Resolver / Confirm / Policy？

## 决策

1. 本阶段 **不是 CRM、不是 ERP 替代、不加业务能力**。不改 Runtime 核心 / Confirm Gate，不新增 Agent，不引入库存/支付/财务。
2. Customer 来源：ERP Customer / 现有档案。Product 来源：ERP Item / 商品目录。
3. **ERP 提供事实。Read Adapter 读取和投影。Runtime 只消费投影。**
4. 投影时刻是上线/开门初始化，写入 Catalog 工作目录。喊单回合 Resolver 只查投影，不按名称搜 ERP。
5. 候选 1 个 → 继续；多个 → 询问；没有 → 询问/挂起。读取失败 **不能猜**。
6. 新档口只需导入客户切片、商品切片。不导入库存、欠款、财务。
7. 禁止 ERP 直接控制 Resolver、Confirm、Policy。V0.6 投递读取与主数据投影同属 Adapter，都不得进闸门。

## 原因

看见企业事实与听从企业系统是两件事。切片进 Catalog 才能认人口语；ERP 留在 Adapter 里，闸门才保持冻结。

## 影响

- 好处：进摊有导入清单；认人不唯一时有行为；与 V0.6 读边界一致。
- 限制：不同步全量 ERP；投影失败要问人，不靠回合中直查 ERP 救场。
