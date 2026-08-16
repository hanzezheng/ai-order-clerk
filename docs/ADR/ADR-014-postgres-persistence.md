# ADR-014

标题：PostgreSQL 只实现 Port，不改业务内核

- 状态：accepted
- 日期：2026-08-16

## 背景

Sprint 10A 已把存储收口到 Repository Port。进程重启后客户、Evidence、Workbench、未完成 Session 仍会丢，因为默认实现是内存。需要可重启的 PostgreSQL 实现，但不能把 Policy / Resolver / Service 绑到 ORM。

## 问题

如何替换存储引擎，使 Kill & Restart 后业务状态仍在，同时 Entity 仍是领域契约？

## 决策

PostgreSQL 实现**只存在** `app/database/postgres/`。通过与 InMemory 相同的 Port 接入 `bootstrap`。

- `DATABASE_URL` 有则启用 PostgreSQL；无则 InMemory（测试默认）。
- ORM / 表映射不出 `database` 层。读写前后转换成 `app/entity`。
- 种子（稳定 UUID 的本体与客户）与 schema migration 分开：Alembic 只建表；启动时 upsert 种子且**不覆盖**已学习的档案。
- `SalesSession` 工作态以 JSONB 快照持久化；`OrderRepository.save_draft` 继续双写订单 JSONB + 规范化 `order_lines`。禁止第三套订单模型。
- Evidence 持久化**结果**；`processed_events` 按 consumer 记录已消费 `event_id`。禁止启动时重放 `order.confirmed`。
- Timeline / Intake payload 继续禁止 `user_text`。
- 不改 Parser / Resolver / Policy / OrderService / Response / Memory 规则。

Kill & Restart 必须验证：新 `AppWorld` 连接同一库后，客户、Evidence、Workbench、未完成 Session 仍在；已确认 turns 仍 `409`；王记梨确认 2 次后重启，第 3 次才写 `product_default`。

## 原因

存储可替换是 Port 的意义。把会话工作态放 JSONB，避免把嵌套 `ProductMention` / `ProductNode` 拆成第二套领域模型。规范化订单行留给后续 ERP，不参与本阶段裁决。

## 影响

- 好处：进程可杀可启；测试仍可不连库。
- 限制：不做 ERP、库存、支付、登录、多租户、向量库。本阶段无连接池调优、无跨日 Workbench 归档。
