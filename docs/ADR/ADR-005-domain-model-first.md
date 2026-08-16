# ADR-005

标题：领域模型优先

- 状态：accepted
- 日期：2026-08-16

## 背景

本项目是 Voice-first 行业 Agent，不是表单 App。先做 UI / 先做扁平商品表，会把「苹果」做成零售 SKU，无法支撑档口连报。

## 问题

实现顺序以什么为准？

## 决策

不能先做 UI。必须先定义：

- Customer（含同名、档口、价格关系）
- Product Ontology（category → variety → cultivar → sku）
- Price Memory（客户 × 商品 × 时间，带单位与过期）
- Order Session（SalesSession + SpeechAct + Issue 分级）

第一阶段不做前端、不做麦克风/ASR，但 API 按语音连报契约（`expect_more`、`utterance_id`、多 act）实现。

## 原因

口语打在本体任意层；价可后补；客户称呼不唯一。没有这四块，Agent 只能填表，不能当开单员。

## 影响

- 好处：阶段 2 接 ERP / 库存时有稳定内核。
- 限制：POC 看起来「没有界面」；禁止用 demo 页倒逼改领域。
