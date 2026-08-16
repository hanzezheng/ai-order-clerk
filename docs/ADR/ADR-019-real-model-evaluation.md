# ADR-019

标题：真模型只评测同一 Runtime 入口，不另建评测 Agent

- 状态：accepted
- 日期：2026-08-16

## 背景

V0.3A 已用 OpenAI 兼容 Client 接 LLM；V0.3C 定义了分层 Benchmark 与金脚本，但默认 CI 只用 Fake / 无密钥规则路径。`ParserEvaluator.scored` 仍为预留。若为 Qwen/GPT 另写一套带 Catalog 的评测图，会让「分数」与现网行为脱节，并诱使 LLM 选 SKU。

## 问题

如何验证真实模型能否稳定驱动现有开单 Runtime，同时不改 Resolver / Policy / 闸门、不把评测变成第二个 Agent？

## 决策

V0.3D 只增加**可选 live 评测模式**：

- 走现网 `LLMTurnParser` + pinned `prompt_id` + `LlmTurnParse`；Qwen / GPT / 兼容网关只换 `LLM_BASE_URL` 与 `LLM_MODEL`。
- 默认 pytest 仍不发请求。live 必须显式开关 + 密钥。
- Fake 金脚本与 live 分数分开记账。规则兜底成功不算模型成功。
- Prompt 以 `parser.vN` 版本化；改字即升版；禁止写入 Catalog / 档案 / 价格。
- 失败按 taxonomy 落盘；禁止 LLM 当裁判、禁止用失败集自动改 Prompt 或写 Memory。

细则见 [MODEL_EVAL.md](../MODEL_EVAL.md)。

## 原因

Runtime 的安全来自 Schema、Converter 与 Policy，不来自模型自觉。评测入口必须与生产入口重合，分数才有意义。

## 影响

- 好处：可比较 Qwen 与 GPT 谁能抽出合法 SpeechAct；不达标不宣传 LLM 成功路径。
- 限制：无密钥环境出不了 live 分；模型达标不授权改 `confirm_gate` 或上 ASR。
