# 产品路线

Voice-first 行业 AI Agent。当前垂直：农批开单员。路线服从 `docs/AI_EMPLOYEE_ARCHITECTURE.md` 的分层与 `docs/DESIGN.md` 的产品细则。阶段跨越先改文档再写 ADR。每个 Sprint 必须声明只允许修改哪一层。

## 阶段 1：AI 开单员 POC

目标：连续语音订单理解（可用文本模拟 ASR）。不接 ERP。V1 允许最小 Demo Shell；6A.5 起 Demo 口播只展示后端 `reply_text`。

包含：

- SpeechAct（一段话多个动作、改口、指代）
- Session（SalesSession，结构化任务上下文）
- Product Ontology
- Customer Profile
- Price Memory
- Decision Policy（确认 / 询问 / 自动执行）

验收见 DESIGN §13：30 秒连报、中途改口、同名客户、层级歧义、缺价不中断。

是否进入真 ASR/TTS 仍以 [VALIDATION.md](VALIDATION.md) 的行为指标为准，并服从 [V04_VOICE_ADAPTER.md](V04_VOICE_ADAPTER.md)。阶段 1 稳定合并节点：`v0.1-learning-agent`。v0.2-persistent-agent：Port + PostgreSQL 可重启。Sprint 11：Durable Outbox。V0.3A：LLM 默认语言入口。V0.3B：商品理解（规格属性过滤；不建 SKU、不接 ERP）。V0.3C：农批语言分层评测与复杂订单金脚本；未达标不得开工 V0.4。V0.3D：真模型 live 评测（同一 Runtime 入口；默认 CI 不发请求）。parser.v6 + qwen3.7-plus 的 G1–G4 为 A 之后，V0.4 只做 Voice Adapter。V0.5 落地 ERPNext Adapter：只经 Outbox 写 Draft Sales Order，不改开单内核。V0.6 落地 Read Adapter：只经领域查询读投递状态，不进 Policy。见 [V06_ERPNEXT_READ_ADAPTER.md](V06_ERPNEXT_READ_ADAPTER.md)。冻结清单：[RUNTIME_FREEZE.md](RUNTIME_FREEZE.md)。

Runtime 收口之后的**产品**阶段见 [SALES_EMPLOYEE_CAPABILITY.md](SALES_EMPLOYEE_CAPABILITY.md)。第一个可雇版本：[V1_SALES_CLERK.md](V1_SALES_CLERK.md)。产品化用户旅程：[V1_SALES_CLERK_USER_JOURNEY.md](V1_SALES_CLERK_USER_JOURNEY.md)（今日开单本为主界面；嘴巴只写当前单；确认不是付款）。ROADMAP 阶段 2 的库存/付款/采购仍另批。

## 阶段 2：真实业务连接

在阶段 1 内核上接业务系统，不推翻开单图。

包含：

- ERPNext Adapter（V0.5 已落地 Draft Sales Order；V0.6 设计只读投递状态；TBD 价标记 `prices_incomplete`；仍不 submit）
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
