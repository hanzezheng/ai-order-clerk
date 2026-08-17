# ADR-037

标题：V1 老板端是 Flutter 今日开单本壳；只调现有 API，不改 Runtime

- 状态：proposed
- 日期：2026-08-17

## 背景

Pilot 文档已齐。老板要拿手机喊单，而不是在电脑浏览器里试。若把 ERP 搬进 App，或改 Confirm Gate 迁就手机，会破坏冻结。

实现：`mobile/`。规格：[V1_SALES_CLERK_FLUTTER_APP.md](../V1_SALES_CLERK_FLUTTER_APP.md)、[V1_SALES_CLERK_WORKBENCH.md](../V1_SALES_CLERK_WORKBENCH.md)。服从 [RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)。

## 问题

真实农批老板如何在手机上完成开单、改未确认、好了、看今日本，同时不把 Runtime 做成 App 后端？

## 决策

1. 客户端用 **Flutter**。后端保持现有 AI Employee Runtime。**不改 Runtime 核心、不改 Confirm Gate、不新增 Agent。**
2. 路径：`Flutter App → HTTP API → Runtime → ERPNext Adapter`。
3. 自然语言只进 `POST /v1/sessions/{id}/turns`。音频在设备上 ASR；只提交 `text` 与 `reply_text` 回放。
4. 第一页是今日开单本：当前 / 待确认 / 已确认 / 今日张数 / 入账三字。
5. 「好了」走现有确认：confirmed event → Outbox → Draft SO。App 只刷新 `posting`。
6. 基础账号绑定：一个老板对应一个档口，存在本机。不是 CRM、不是多租户引擎。
7. 禁止：ERP 前端、库存、财务、支付、改 Parser。

## 原因

手机是 Input 壳。开单裁决已经在 Runtime。把壳做成 ERP 或新 Agent，老板雇不到开单伙计。

## 影响

- 好处：摊前可按住喊；确认与入账契约不变。
- 限制：真机 ASR 字准不是本阶段闸门；无切片时仍询问/挂起。
