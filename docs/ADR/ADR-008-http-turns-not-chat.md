# ADR-008

标题：HTTP turns 是唯一自然语言入口；Timeline 只记业务事件

- 状态：accepted
- 日期：2026-08-16

## 背景

Sprint 1–5A 已落地开单内核（Parser → Resolver → Policy → OrderService → Response）。Sprint 6A 要把内核包成可体验产品。若把 Session 做成聊天室、或让 API 直写订单表，会破坏 ADR-001/003，并堵死以后的 ASR/TTS 外壳。

## 问题

自然语言从哪里进系统？会话时间线存什么？Demo 是否可以变成表单开单？

## 决策

1. **唯一自然语言入口**是 `POST /v1/sessions/{id}/turns`。`POST /v1/sessions` 只创建 `SalesSession` 任务。HTTP 适配层（`TurnIntake`）处理 `utterance_id` 幂等、`seq` 保序、`is_final=false` 丢弃，再调用现有 `SalesSessionRunner.handle`。
2. **API 禁止**直连 Repository、禁止绕过 Runner / Policy、禁止为 Demo 改 Parser / Resolver / Policy / Memory / OrderService / Response。
3. **Session Timeline** 按会话独立存储，只投影业务事件（`order.started`、`order.line_upserted`、`order.confirmed`、`customer_ambiguous` 等）。禁止保存聊天记录，payload 不得出现 `user_text` / `raw_text` / `text` / `utterance` / `chat` / `message`。Timeline 不写入 `SalesSession`。
4. **Web Demo Shell** 用文本模拟语音输入：巨大输入框、发送、展示 `reply_text` 与只读草稿。禁止加行表单、库存、支付、登录、多租户。

## 原因

档口产品是 Voice-first 开单员，不是 IM，也不是 ERP。同一 turns 契约以后可替换 ASR/TTS，而不改内核。聊天全文既不是 Memory，也不是 Session。

## 影响

- 好处：6B 接真语音时只换外壳；契约测试可锁幂等与 Timeline 禁字段。
- 限制：V1 不做事件缓冲（乱序 `seq` 直接 409）；Timeline 不是审计聊天，排障需看当轮响应而非历史原文。
