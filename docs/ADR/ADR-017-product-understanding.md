# ADR-017

标题：商品理解只约束候选，不点选 SKU

- 状态：accepted
- 日期：2026-08-16

## 背景

V0.3A 已能抽出 `spec_mention`，但 Runner 只把 `product_mention` 交给 Resolver。规格口语被丢掉或被前缀匹配吞掉。若让 LLM 返回 SKU，会绕过本体与 `confirm_gate`。

## 问题

如何把档口规格落到已有商品树上，同时不创建商品 Agent、不改确认闸门？

## 决策

增加确定性 `ProductUnderstanding`，不增加 LLM 选货：

```text
SpeechAct → ProductUnderstanding → ProductQuery → Resolver → Policy.fill_sku → Service
```

- Understanding 只做 spec 归一（size / grade / origin / packing）和 `ProductQuery`。禁止写 Catalog / Memory，禁止输出 sku_id。
- `focus_node_id` 只来自 Session 已有行，不来自 LLM。
- Resolver 识别节点、按属性过滤候选、唯一 SKU 命中时提升 `matched_node` 到该 sku 节点。禁止自动替品。
- `resolved_sku` 仍只由 `Policy.fill_sku` 填写。`confirm_gate` 仍只认 `product_sku_id`。
- 不做自动建 SKU、Ontology 学习、ERP 同步、Vector DB。

## 原因

「八零果」是规格，不是新品类。属性唯一命中已有节点，等于老板说清了货；多个候选仍应 `line_hold`。闸门条件不能改成「规格够了就能确认」。

## 影响

- 好处：规格口语能落到现有树上；无规格时歧义与档案默认行为不变。
- 限制：词典是封闭小表；树上没有的规格不会长出新 SKU。
