# ADR-015

标题：Outbox 是可靠事实出口，不是消息平台

- 状态：accepted
- 日期：2026-08-16

## 背景

v0.2 已让客户、Evidence、Session、Workbench 可 Kill & Restart。领域事件仍写在进程内 `RecordingEventPublisher.events`：Memory 与 Timeline 扫描这份列表。进程在「确认已落库、消费未完成」之间崩溃，会出现少记或多记。若启动时重放全部 `order.confirmed`，Evidence 的 delta 会计爆。

## 问题

如何让确认后的业务事件成为可靠扩展出口，同时不引入消息平台、不改 Memory 规则、不接 ERP？

## 决策

采用**同库最小 Outbox**：

```text
事务 A：业务状态 + Outbox 同行提交
    → EventDispatcher.drain
事务 B（每个 consumer × 每个 event_id）：
    副作用 + processed_events.mark 同行提交
```

- `DomainEvent` 语义不变。Outbox 只存信封（`event_id` / type / aggregate / session_id / payload / 时间）。
- 业务层只调用 `DomainEventPublisher.publish`。不知道 Outbox 表，不知道 Consumer 名字。`EventDispatcher` 是装配层。
- Memory / Timeline **不再**扫描进程事件列表。它们按 `list_pending(consumer, event_types)` 消费 Outbox。
- `processed_events` 继续按 `(consumer, event_id)` 隔离。禁止在 outbox 行上写总开关「已消费」。
- Memory 规则不变：`observe`/`adjust` 仍是 delta。禁止用全量 replay 重建 Evidence。启动只 drain「该 consumer 尚未 mark」的行。
- Extractor 先写副作用，再 mark；二者同事务。禁止先 mark 后写 Evidence。
- 没有 Kafka、worker、topic、死信。本进程在事务 A 之后同步 drain；启动时补漏。
- 测试探针可继续记录本回合事件，但不得作为消费来源。

## 原因

扩展出口必须是库里的 `event_id`，否则库存/付款一旦接入就会在 `confirm` 里写副作用。本阶段只把事实放进箱子，不建设总线。

## 影响

- 好处：确认与事件同生共死；Memory/Timeline 可崩溃重试且不加爆。
- 限制：不做 ERP、库存、支付、多 Agent、Event Sourcing、独立消息进程。
