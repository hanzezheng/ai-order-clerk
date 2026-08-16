# ADR-009

标题：长期记忆只从确认后的领域事件学习

- 状态：accepted
- 日期：2026-08-16

## 背景

Sprint 1–5A 的 Memory 闸门已在，但 Extractor 几乎只在 `set_price` 时写 `last_quote`，确认被跳过，`last_deal` / `product_default` 不会从成交长出。若从用户原话或 LLM 直接写记忆，会把「60 件」「好了」「今天换青苹果」当成偏好。

## 问题

AI 开单员如何跨单学习，同时不把聊天当知识、不让模型改档案？

## 决策

唯一写入路径：

```text
order.confirmed
  → Extractor（只读客户 id、行 SKU、价源、品种节点）
  → Evidence（偏好计数）
  → MemoryPolicy
  → Storage
```

- 禁止从用户原话、SpeechAct.span、Timeline 写长期记忆。
- LLM 不得参与 Extract / Policy / Storage。Parser 仍可替换，但与 Memory 隔离。
- `product_default` 必须先累计确认证据，`count ≥ 3` 才升级为档案默认。
- `last_deal` 仅确认且该行 `price.source=explicit`；TBD 不写。
- 记录预留 `status`、`last_confirmed_at`；本阶段不做衰减。
- 读侧：`last_deal` 仍只 notice，禁止静默改行价。

## 原因

确认后的草稿是已过 Policy 闸门的结构化事实。聊天是过程。证据层把「习惯」和「一次改口」分开。

## 影响

- 好处：熟客默认 SKU 与成交价可从真实成交长出，且可测。
- 限制：未确认的报价不进长期记忆；别名 / last_quote / 行情本阶段不自动写；衰减未做。
