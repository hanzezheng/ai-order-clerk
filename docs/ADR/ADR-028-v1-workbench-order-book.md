# ADR-028

标题：今日开单本是 V1 工作台原型；当前单五态是呈现，不是新闸门

- 状态：proposed
- 日期：2026-08-17

## 背景

用户旅程已规定：主界面是今日开单本，嘴巴只写当前单，确认 = 生意事实成立。下一步若没有原型规格，容易把 Demo 做成聊天窗或把 ERP 列表当工作台，或把 `posted` 写进 Confirm Gate。

原型：[V1_SALES_CLERK_WORKBENCH.md](../V1_SALES_CLERK_WORKBENCH.md)。服从 [RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)。

## 问题

老板每天打开的第一页长什么样？当前订单的 empty / draft / pending_confirm / confirmed / posted 是不是新的业务状态机？

## 决策

1. **今日开单本 = AI 销售员工的工作台。** 不是 ERP 列表、不是聊天窗口、不是数据报表。
2. 第一页只含：今日日期、当前订单、待确认、已确认、入账状态、异常提醒；主操作是按住说话与「好了」。
3. 五态是 **本子呈现**，映射到已有未确认 / 已确认 / Read 投影。不改变 Confirm Gate。`posted` 不进口播、不挡确认。
4. Voice First：按住 → 理解 → 草稿 → 复述。不设计复杂聊天。
5. 实现只允许 Demo / Workbench 投影。不新增 Agent，不引入库存 / 支付 / 财务。

## 原因

档口要的是摊开的本和跟着喊的笔。把入账做成闸门或把页面做成 ERP，老板就不会在摊前用。

## 影响

- 好处：5 分钟试用有明确页面与三条 Demo；与旅程、Freeze 对齐。
- 限制：已确认不能喊着改；看不见入账只能标出来；没有报表和收款。
