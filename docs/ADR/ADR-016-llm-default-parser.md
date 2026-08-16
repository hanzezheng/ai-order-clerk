# ADR-016

标题：LLM 是默认语言入口，不是业务大脑

- 状态：accepted
- 日期：2026-08-16

## 背景

Sprint 3 已有可替换的 `LLMTurnParser`、双层 Schema 与规则回退，但默认装配仍是 `RuleTurnParser`。v0.2 + Durable Outbox 之后，开单员能记住、能重启、能留下确认事实，却仍只吃得动口令句。把 LLM 做成裁决或商品检索，会选错客户、猜 SKU、编价格。

## 问题

如何让默认语言入口听懂档口话，同时保持 Resolver / Policy / OrderService / Memory / Confirm 不变？

## 决策

`LLMTurnParser` 成为默认 `TurnParser`。流水线仍是：

```text
Text → SpeechAct[] → Resolver → Policy → Service
```

- LLM 只抽语言提及。禁止选客户、选 SKU、定价、写 Memory、判断能否确认。
- 双层 Schema：`LlmTurnParse` → Converter → 领域 `SpeechAct`。禁止 LLM JSON 直接当领域对象。
- 有 LLM 配置：先走模型，失败则整回合回退规则 Parser（`fallback=true`）。
- 无配置：不发请求，外壳直接规则解析。`parser_name=rule`，`fallback=false`，`fallback_reason=llm_unconfigured`。无模型时行为与 v0.2 一致。
- `spec_mention` 只是语言槽。禁止映射成 SKU / sku_id / 规格全称。
- Prompt 只写语言规则。禁止塞 Catalog、客户档案、价格知识。
- 不上 LangGraph、ASR、Vector DB。

## 原因

语言理解与业务裁决必须分开。规则兜底保证无密钥仍能开 Demo 单；模型只在抽 act 时出现。

## 影响

- 好处：默认入口可换模型；口令剧本与现网测试不依赖密钥。
- 限制：LLM 成功路径上的口语切分可以比规则更好，但不得改变闸门。Canonical 口令必须与规则 Parser 业务等价。
