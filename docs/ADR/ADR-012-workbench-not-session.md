# ADR-012

标题：Workbench 组织当天任务，SalesSession 仍是一单

- 状态：accepted
- 日期：2026-08-16

## 背景

内核已能开完一张单并学习、纠错、冷启动客户。连续干活缺的是任务组织：确认后没有「下一单」，也没有当天已确认索引。若把跨单列表或聊天塞进 `SalesSession`，会变成 IM，并堵死采购/付款分会话。

## 问题

如何让 AI 员工连续开多张销售单，同时不扩大 Session、不增强 Memory？

## 决策

新增薄层 **Workbench**（当日班次）：

- 管理多个 `SalesSession` 指针与当前任务
- 投影已确认订单的结构化索引
- 显式 `POST /v1/workbench/tasks` 创建新销售任务并切换 current

不负责：商品理解、客户记忆、Memory 写入、ERP。不解析语言、不调用 Resolver。

`SalesSession` 保持一单一个任务。禁止跨单字段。已确认任务拒绝后续 turns（`409 task_completed`）。不做 `start_order` 自动开新单。`paused` 仅预留状态名。

自然语言入口仍是 `POST /v1/sessions/{id}/turns`。

## 原因

档口连续干活是「多张任务」，不是「一个更长的会话」。确认事件继续驱动 Memory；工作台只看见任务 id 与草稿投影。

## 影响

- 好处：当天可开第二单而不改内核裁决。
- 限制：确认后须显式新建任务；本阶段无自动路由、无跨日持久化。
