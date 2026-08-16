# ADR-013

标题：同一套 Repository Port，业务层禁止依赖 InMemory

- 状态：accepted
- 日期：2026-08-16

## 背景

Sprint 9A 后，开单、记忆、工作台都能跑，但持久化口子不完整：`ports.py` 只有 Catalog 读、`put_customer`、Session、Order。Alias / PriceMemory / Evidence / Timeline / Workbench / 已消费事件 / Intake 收据仍是业务对象里的私有 dict，或类型写死 `InMemory*`。进程一停，客户候选、证据计数、未完成 Session、工作台都会丢。若启动时重放历史 `order.confirmed`，Evidence 还会被加爆。

## 问题

如何在不改 Parser / Resolver / Policy / OrderService / Response / Memory 规则的前提下，让存储可替换，且默认测试仍用内存？

## 决策

**同一套 Port，替换可重启实现。** 不是新业务能力。

```text
Service / Extractor / Intake / Workbench
        ↓
  app/services/ports.py     （唯一持久化契约）
        ↓
  InMemory*  |  PostgreSQL（10B）
```

### 补齐的 Port

| Port | 职责 |
| --- | --- |
| `CatalogRepository` | 读客户/本体/档案；`put_customer`；`put_product_default` |
| `AliasRepository` | 长期商品别名 |
| `PriceMemoryRepository` | 价格记忆 |
| `EvidenceRepository` | EvidenceRecord 存取；计数规则仍在 `EvidenceStore` |
| `TimelineRepository` | 按 session 追加业务事件 |
| `ProcessedEventRepository` | 按 consumer 标记已消费 `event_id` |
| `WorkbenchRepository` | 当日 `WorkbenchShift` |
| `IntakeReceiptRepository` | `utterance_id` 收据 + `seq` 游标 |
| `SessionRepository` | `SalesSession` 工作态（已有） |
| `OrderRepository` | 草稿双写（已有） |

### 硬约束

1. 业务层（`agent` / `policy` / `memory` / `response` / `services` / `session` / `workbench`）禁止 import `app.database`，禁止依赖 `InMemory*` 类。
2. InMemory 继续作为默认测试实现；`bootstrap` 是唯一组装点。
3. Entity 仍是领域契约。ORM / 表映射不得漏出业务层。
4. 禁止启动时重放事件流来恢复 Evidence。持久化**结果 + 已消费 event_id**。
5. Timeline / Receipt payload 继续禁止 `user_text`。
6. 冻结：Parser、Resolver 主流程、Policy、OrderService、Response、Memory 规则（Extractor 决策、阈值、负向债务语义）。

## 原因

Port 收口之后，10B 才能只在 `database` 层换 PostgreSQL，而不改裁决与学习规则。已消费事件与证据结果一起存，重启才安全。

## 影响

- 好处：测试与生产走同一契约；Kill & Restart 成为存储问题，不是业务问题。
- 限制：本 ADR 不引入 PostgreSQL、ERP、库存、支付、登录、多租户、向量库。

## 10A 最终文件计划

| 文件 | 动作 |
| --- | --- |
| `docs/DESIGN.md` | 改：分层、Port 清单、§12 8i、§14.9 |
| `docs/ADR/ADR-013-persistence-ports.md` | 新（本文件） |
| `docs/ROADMAP.md` | 改：Sprint 10A |
| `app/services/ports.py` | 改：补齐全部 Port |
| `app/entity/memory.py` | 改：`EvidenceRecord` 升为领域契约 |
| `app/entity/intake.py` | 新：`IntakeReceipt` |
| `app/database/memory.py` | 改：全部 InMemory 实现对应 Port |
| `app/memory/evidence.py` | 改：只依赖 `EvidenceRepository` |
| `app/memory/extractor.py` | 改：`_seen` → `ProcessedEventRepository` |
| `app/session/timeline.py` | 改：Timeline + ProcessedEvent Port |
| `app/session/intake.py` | 改：IntakeReceipt Port |
| `app/workbench/service.py` | 改：WorkbenchRepository |
| `app/services/memory_service.py` | 改：构造类型改为 Port |
| `app/services/price_memory_service.py` | 改：构造类型改为 Port |
| `app/services/context_loader.py` | 改：构造类型改为 Port |
| `app/services/product_resolver.py` | 改：构造类型改为 Port（`resolve` 逻辑不动） |
| `app/bootstrap.py` | 改：组装 InMemory |
| `app/tests/test_ports_memory.py` | 新：Port 契约 + 业务层不依赖 InMemory |
| `app/tests/test_adaptive_memory.py` | 改：EvidenceStore 注入内存实现 |

**不改：** `app/agent/*`、`app/policy/decision.py`、`app/services/order_service.py`、`app/response/*`、`app/memory/policy.py`。
