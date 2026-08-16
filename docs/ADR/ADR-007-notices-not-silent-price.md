# ADR-007

标题：主动提醒是 Policy Notice，不得静默改价

- 状态：accepted
- 日期：2026-08-16

## 背景

开单员应能提醒「有老价未采用」「行情未写入」「成交价已过期」，但不能擅自把记忆写进订单，也不能让 Memory 自己开口。

## 问题

提醒由谁决定？数字从哪来？何时能说？

## 决策

唯一合法路径：

```text
BusinessContext（只读投影）
  → Policy.collect_notices
  → Issue(block_level=notice)
  → ReplyPlan.notices（code / severity / source_refs，无最终中文）
  → TemplateResponseGenerator
```

禁止：

- ReminderAgent 或第二套 LLM
- Memory / ContextLoader 直接生成 `reply_text`
- 把 Profile 或价格记忆全量塞进 `SalesSession`
- 未绑定客户时加载 Profile、PriceMemory、历史成交
- 因 `last_deal` / `market_today` 修改订单行价

`NoticePriority` 预留，本阶段不排序。连报 `ack` 不说 notice。

## 原因

静默套价与档口行情日变冲突；让记忆直接说话会绕过 ADR-004/006。Notice 是告知，不是成交。

## 影响

- 好处：可提醒未采用的老价，订单仍保持 `price_tbd`。
- 限制：5A 不实现「要按老价格吗？」的 `use_old_price` 填价；不提醒库存与账期。
