# ADR-011

标题：客户冷启动走 Catalog candidate；商品本阶段只记 mention

- 状态：accepted
- 日期：2026-08-16

## 背景

V0.1 与 Adaptive Memory 已能服务「培训过的」种子客户与本体。真实新档口客户库可能为空。零命中今天会 `customer_not_found` 停住。商品未知若在同一 Sprint 里创建 SKU，会把实体识别和 Catalog 治理混在一起。

## 问题

如何让未知客户从陌生变成可开单的人，同时不猜 SKU、不改 Ontology、不改 Memory 写入路径？

## 决策

Sprint 8A 只做客户冷启动 + ProductMention candidate。

客户生命周期在 Catalog，不是第二套 Memory：

```text
unknown → candidate → observed → trusted
```

- 零命中：`customer_unknown`，问 `stall_no`（或电话尾号）。
- 有区分事实才 `CustomerService.create_candidate`；同称呼+同档口复用。
- `candidate` 再遇须核档口，禁止静默绑。
- 第一张 `order.confirmed` → `observed`；确认单数 ≥ 3 → `trusted`。
- 别名写在客户实体上，供 lookup。不经 Extractor / MemoryPolicy。

商品：Resolver 零命中只把 `ProductMention.status=candidate` 记入 Session。禁止创建节点、禁止猜 SKU。未到 sku 不能确认。命中已有本体并确认后，Evidence 仍走原写入路径。

冻结：Parser、Resolver 主流程、`confirm_gate`、OrderService、Memory 写入路径。

## 原因

客户是「这是谁」；商品叶节点是货盘主数据。先解决身份，Catalog 生长留给以后的商品冷启动 Sprint。确认闸门保持「有客户 id、行到 sku」，冷启动是补实体，不是打穿闸门。

## 影响

- 好处：空库可录入新客户并开单；错误称呼不会在无档口时落库。
- 限制：未知特指商品仍无法确认；不从口语长出 Ontology；`candidate` 客户在首次确认前不能当熟客静默绑定。
