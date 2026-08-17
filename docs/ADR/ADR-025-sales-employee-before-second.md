# ADR-025

标题：第一个商业员工是农批开单员；在开单岗可雇之前不启动第二个 Employee

- 状态：proposed
- 日期：2026-08-17

## 背景

Runtime Foundation（语言、裁决、记忆、持久化、语音、ERP 读写）已收口并冻结。下一步容易做成：抽象平台、上第二 Agent、或把催款/库存塞进 `SalesSession`。

产品评审：[SALES_EMPLOYEE_CAPABILITY.md](../SALES_EMPLOYEE_CAPABILITY.md)。可雇规格：[V1_SALES_CLERK.md](../V1_SALES_CLERK.md)、[ADR-026](ADR-026-v1-sales-clerk-product.md)。服从 [RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)。

## 问题

技术 Runtime 完成之后，第一个商业岗位是什么？下一阶段增强销售员工还是启动采购/财务/仓员工？

## 决策

1. 第一个商业员工岗位 = **农批档口开单员**（接单、改未确认单、确认、账上 Draft SO）。不是档口经理。
2. **继续增强 Sales Employee**。只使用冻结允许的扩展点：Input（真机语音）、Workbench 今日开单本、Read 投影可见、可选 `order.cancelled` 的 Write consumer。
3. **不**启动第二个 Employee，直到开单岗在档口被使用。
4. 若将来启动第二岗：优先 **收款员（PaymentSession）**，复制流水线，不继承 `OrderService`。禁止用框架编排多员工。
5. 禁止用「查询客户 / 跟进 / 对账收款」当借口改 Parser、Policy 或让 ERP 驱动 `confirm_gate`。

## 原因

老板雇得动的是「会开单的伙计」。查询、催欠、核销是相邻岗位，现网既无 Session 类型也无闸门。先做第二员工会把未验证的销售类型当成平台内核。

## 影响

- 好处：产品故事单一；Freeze 可执行。
- 限制：收摊对账只看到「开了/进草稿了」，看不到已收款；跟客不做。
