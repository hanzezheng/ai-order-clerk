# 产品路线

Voice-first 行业 AI Agent。当前垂直：农批开单员。路线服从 `docs/DESIGN.md`，阶段跨越先改 DESIGN 再写 ADR。

## 阶段 1：AI 开单员 POC

目标：连续语音订单理解（可用文本模拟 ASR）。不接 ERP，不做前端。

包含：

- SpeechAct（一段话多个动作、改口、指代）
- Session（SalesSession，结构化任务上下文）
- Product Ontology
- Customer Profile
- Price Memory
- Decision Policy（确认 / 询问 / 自动执行）

验收见 DESIGN §13：30 秒连报、中途改口、同名客户、层级歧义、缺价不中断。

## 阶段 2：真实业务连接

在阶段 1 内核上接业务系统，不推翻开单图。

包含：

- ERPNext Adapter（Customer / Item / Sales Order；TBD 价标记 `prices_incomplete`）
- Inventory（订阅 `order.confirmed`，SalesSession 内不扣库存）
- Payment（独立 PaymentSession；确认开单 ≠ 已收款）
- Purchase（PurchaseSession，复用本体与 SpeechAct）

## 阶段 3：行业 AI 员工平台

同一套 SpeechAct、Memory、Policy、Entity Resolver，换行业本体与档案。

支持：

- 农批
- 装修
- 汽修
- 物流
