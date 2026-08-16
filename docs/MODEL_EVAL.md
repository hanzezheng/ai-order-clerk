# 真模型评测（V0.3D）

> 验证的不是「哪个模型更会聊天」，而是：**真实 LLM 能否稳定驱动现有 Runtime**（同一套 `LLMTurnParser` → SpeechAct → Understanding → Resolver → Policy → Service）。
>
> 分层与金脚本仍以 [LANGUAGE_BENCHMARK.md](LANGUAGE_BENCHMARK.md) 为准。本文只规定：**怎么接模型、怎么跑、Fake 与真模型差在哪、Prompt 怎么版本化、什么算成功、失败怎么记。**
>
> 冻结：Resolver、Policy、OrderService、Memory、Response、Outbox。
> 禁止：ASR/TTS、ERP、Vector DB、LLM 选 SKU、LLM 写 Memory、把 Catalog/档案/草稿塞进 Prompt。

---

## 0. 与 V0.3C 的关系

| | V0.3C | V0.3D |
| --- | --- | --- |
| 问题 | 测什么（分层、金脚本、缺口） | 用真模型怎么测 |
| CI 默认 | 无密钥 + Fake 夹具 | **不进默认 CI**（无密钥不得发请求） |
| 裁判 | 确定性断言 | 同一套断言；**禁止 LLM 当裁判** |
| 通过线 | Fake / 规则路径能复现契约 | **至少一个候选模型**在冻结 Runtime 上达到 §5 |

真模型评测必须走**生产同一入口**：`LLMTurnParser` + 当前 pinned Prompt + `LlmTurnParse` Schema + Converter。禁止另写评测专用 Agent、禁止 function calling、禁止 RAG。

---

## 1. Qwen / GPT 等模型接入方式

已有 `HttpLlmClient`：OpenAI 兼容 Chat Completions。换厂商只换环境变量，不换 Parser。

```text
LLM_API_KEY     有则发请求；无则 Unconfigured（直接规则，不算评测）
LLM_BASE_URL    默认 https://api.openai.com/v1
LLM_MODEL       默认 gpt-4o-mini
LLM_TIMEOUT     单次 HTTP 超时秒数，默认 45
LLM_RETRIES     超时 / 429 / 5xx 额外重试次数，默认 2（共 3 次）
LLM_EVAL_PAUSE  live 条间间隔秒数，默认 0.25；仅 HttpLlmClient
```

| 候选 | 接入 | 说明 |
| --- | --- | --- |
| GPT（OpenAI） | `LLM_BASE_URL=https://api.openai.com/v1` | 现默认形态 |
| Qwen（DashScope 兼容模式） | 兼容 `/v1` 或厂商文档给出的 OpenAI 兼容根路径 | 仍走同一 Client，不上 DashScope SDK |
| 其他兼容网关 / 本地 vLLM | 改 `BASE_URL` + `MODEL` | 必须 Chat Completions；禁止工具调用 |

请求契约（与现网一致，评测不得放宽）：

- `temperature=0`
- messages 仅 `system= pinned Prompt` + `user= 本回合原文`
- **不传** Session、草稿、Catalog、客户列表、价格、历史 turns
- 期望模型返回可经 `LlmTurnParse` 校验的 JSON；markdown 围栏可剥，其它包装算失败
- Schema `extra=forbid`；`sku_id` / `product_id` / `customer_id` / `target_line_id` 等业务 id 不得出现在 LLM 槽位。Converter 再剥一遍。出现即 L0 失败或 Schema 失败，**不得**当成功抽取
- 传输层：超时、429、5xx 可重试；401/400 不重试。耗尽后仍 `fallback_reason=client_error`，`raw` 记 `client_error:timeout` / `client_error:http_429` 等，禁止把 API Key 写入报告。规则兜底成功仍不算模型成功。

一次评测运行必须记录：`model`、`base_url` 的 host（不含密钥）、`prompt_id`、数据集版本、git sha、时间。同一报告里禁止混跑两个模型。

Qwen 与 GPT **分别出报告**，不合成「平均分」。准入是「名单上至少一个模型达标」，不是「大家平均够用」。

---

## 2. Benchmark 运行方式

三种跑法，不得互相冒充：

| 模式 | 何时 | Parser | 算不算真模型分 |
| --- | --- | --- | --- |
| `unconfigured` | 默认 pytest / 无密钥 | 外壳直接规则 | 否 |
| `fake` | V0.3C 金脚本夹具 | `FakeLlmClient` 按句给槽 | 否（测 Runtime，不测模型） |
| `live` | 显式开启真模型评测 | `HttpLlmClient` | **是** |

`live` 开启条件（不得默认打开）：

- 环境同时有 `LLM_API_KEY` 与 `RUN_LIVE_LLM=1`
- 仅有密钥时，日常 `pytest` **不发**请求（live 用例 skip）

生成报告：

```text
RUN_LIVE_LLM=1 LLM_API_KEY=… python3 -m app.agent.live_eval
```

产物默认 `docs/eval/runs/<utc>-<model>-parser.v5.json`，不进 git。默认 CI 只跑 Fake / unconfigured。

运行切片：

1. **L1 live**：`sales_parser_cases.json` 逐条 `parse(text)`。记录 `parser_name` / `fallback` / `fallback_reason`。
2. **L0 live**：每条预测的领域对象跑 S1–S6 能静态检查的项（无业务 id、无编造行情数字）；链路项在 L4 查。
3. **L4 live**：G1–G4 金脚本用**真 Parser** 驱动同一 `SalesSessionRunner`（Understanding / Resolver / Policy 均现网实现，冻结不改）。入口：`python3 -m app.agent.runtime_admission`（无密钥走 Fake；live 须 `RUN_LIVE_LLM=1`）。细则 [RUNTIME_ADMISSION.md](RUNTIME_ADMISSION.md)。qwen3.7-plus + parser.v4 结论 **C**（仅 G1 规格落行失败）。parser.v5 只改语言契约：句中货名+规格必须同槽 `product_mention`+`spec_mention`。未得 A 不上语音。
4. **稳定性**：`stall_oral` 与 G1 全文各重复 **3** 次。三次草稿快照或 L1 acts 不一致记 `unstable`。

输出一份 `EvaluationReport`（扩现有 `ParserEvaluationReport`）：`scored=true` 仅在 `live` 模式。Fake / unconfigured 保持 `scored=false`。

失败回退规则：

- Schema / JSON / 空 acts / 客户端错误 → 整回合规则兜底（现行为）
- **评测记账**：`fallback=true` 对 `stall_oral` 与 G1 规格步计为该条**未通过真模型**（规则可能碰巧对，也不得记成模型成功）
- `canonical` 口令：模型失败回退到规则且规则正确 → 记 `fallback_recovered`，**不计入**模型 L1 成功，但 Runtime 仍可用（与 ADR-016 一致）

禁止：评测脚本改 Prompt 热修补、禁止失败后自动重试换温度、禁止把标准答案提示给模型。

---

## 3. Fake 与真实模型差异

| | Fake | 真模型 |
| --- | --- | --- |
| 输入 | 测试作者写好的 acts | 只有原文 |
| 稳定性 | 全确定 | 同温度仍可能漂；故跑 3 次 |
| Schema | 夹具保证合法 | 可能多字段、缺字段、围栏、废话 |
| 「八零果」 | 直接 `spec_mention` | 可能改成「红富士80果…」、或抽成 qty=80 |
| 连报 | 夹具按顺序给齐 | 可能丢后半句、合并错 act |
| 指代 | 夹具保持原词 | 可能猜成红富士 |
| 测到的层 | L2–L5 与闸门 | **外加 L1 是否真能抽对** |
| 不能证明 | Prompt 是否够用 | — |
| 不能替代 | — | Fake 回归。真模型绿不能删 Fake |

因此：V0.3C Fake 金脚本全绿，只说明 Runtime 在**正确 SpeechAct** 下安全。V0.3D 才说明「模型会不会给出正确 SpeechAct」。两条都要，缺一不得称「LLM 可驱动开单」。

真模型即使 L4 草稿碰巧对（例如把「八零果」抽成 product_mention，又被 FUJI80 别名命中），**L1 仍判失败**：规格被当成品名，属于越权映射，后续换树就会错。

---

## 4. Prompt 版本管理

当前正文在 `app/agent/prompts.py` 的 `PARSER_SYSTEM_PROMPT`，**无版本号**。V0.3D 把它当成评测钉死的工件。

| 规则 | 说明 |
| --- | --- |
| `prompt_id` | 形如 `parser.v5`。Runtime 与 live 评测必须用同一 id |
| 钉死内容 | 系统提示全文 + Schema 字段名。改字即升版本 |
| 禁止写入 | Catalog 名、客户名、价格、SKU 全称、档案默认、草稿 |
| 变更流程 | 先加 `parser.vN` 文本 → live 评测对比 vN-1 → 达标再切换 Runtime 指针 |
| 评测报告 | 必须带 `prompt_id`。禁止「改了 Prompt 却沿用旧报告」 |
| 自动优化 | 禁止（无 DSPy / 无根据失败集回写 Prompt） |

`parser.v1` = 语言规则 + 禁止猜 SKU / 禁止编数字。  
`parser.v2` = v1 + 强制 `{"acts":[{"type","slots"}]}`，禁止顶层数组、禁止槽位与 type 同级摊开。  
`parser.v3` = v2 + 列出允许的 `type` 枚举（禁止 `add_item` 等自造名）+ 规格口语必须 `refine_spec`/`spec_mention`。  
`parser.v4` = v3 + 量词 uom、「再加N件」为 `set_qty mode=add`、货名指代用 `product_mention`、光杆「那个X」为 `unknown`。  
`parser.v5` = v4 + 句中货名+规格必须同时输出 `product_mention` 与 `spec_mention`；只有规格时仍允许光杆 `spec_mention`。当前 Runtime pin 为 `parser.v5`。仍禁止加商品库、禁止 `line_id`。

Schema 前的语言层归一（仍不是领域放宽）：

1. 根数组包成 `{"acts": ...}`；已知语言槽抬入 `slots`。
2. **封闭 type 同义词**（如 `add_item`→`add_line`，`set_spec`→`refine_spec`）。表外自造 type 仍 Schema 失败。禁止把 `done`/`checkout` 映射成 `confirm_order`。
3. **原文可核对的槽位修补**：货名 act 上 `mention`→`product_mention`（`clarify` 除外）；无货名的 `add_line`+qty → `set_qty mode=add`；无数量的「那个X」`set_line`/`add_line` → `unknown`；「两个」补 `uom=个`。不猜 SKU，不编原句没有的数字。
4. `sku_id` / `customer_id` 等业务字段仍 `extra=forbid`。

L1 匹配：`set_line` 与 `add_line` 在必填槽一致时视为同类（merge 语义仍由 Runner 按 type 区分）。其它 type 必须字面一致。

Prompt 回归（无密钥也要跑）：现有「Prompt 不含 Catalog / 店名 / 价格」断言保留；新版本同样必须过。

---

## 5. 成功指标

对象：单次 live 运行 = `(model, prompt_id, dataset_rev, git_sha)`。

### 5.1 一票否决（任一失败则该模型未通过）

- L0 任何一条（含预测里出现 sku_id / 店名全称 / 编造行情数字）
- `must_not_guess` 未 100%
- Catalog / Alias 快照变化
- `confirm_ok` 在无 `product_sku_id` 时为真
- LLM 输出被当成 Memory 写入（本阶段 Memory 路径本就不读 Parser；若评测发现写入，直接否决）

### 5.2 必须达到（准入「可驱动 Runtime」）

针对**每一个**申报模型单独算：

| 指标 | 门槛 | 口径 |
| --- | --- | --- |
| L1 `stall_oral` | ≥ 90% 条通过 | `parser_name=llm` 且 `fallback=false`，type + 必填槽一致；规格槽保持原词 |
| L1 `canonical` | 100% Runtime 等价 | 允许 `fallback_recovered`；最终草稿与规则路径一致 |
| L4 G1、G2 | 100% 步骤 | 真 Parser 驱动；3 次重复快照一致 |
| L4 G3、G4 | 100% 步骤 | 失败保持与连报不中断 |
| `stall_oral` fallback 率 | ≤ 10% | Schema/空 acts/客户端错误进兜底 |
| 不稳定率 | 0 | 3 次 acts 或 G1 快照不一致 |

L5 口播：沿用 V0.3C 义务；真模型不得为了「像人」多报 SKU 全称或假价格。

### 5.3 不计入成功、只记录

- 延迟、token 费用
- 厂商排行榜
- 规则路径单独分数（属于 V0.3C）
- `replace_product` / `cancel_order` 执行（仍是 Runner 债）

### 5.4 与 V0.4 的关系

未完成 V0.3C Fake 金脚本，不得用 V0.3D 分数代替。  
未有**至少一个**模型达到 §5.1+§5.2，不得宣传「默认 LLM 入口已在真模型上可用」；Demo 无密钥路径仍可用规则兜底（ADR-016）。  
V0.4（ASR/ERP/LangGraph）仍以前序冻结与 V0.3C 准入为准；真模型达标是「打开 LLM 成功路径」的条件，不是改闸门的条件。

---

## 6. 失败案例记录

每条失败写一条记录，禁止只留一个准确率。

必填字段：

- `case_id` / 金脚本步号
- `text`
- `model` / `prompt_id` / git sha
- `raw`（模型原文，截断保存；**禁止**把 API Key 写入文件）
- `fallback` / `fallback_reason`（`invalid_json` / `schema_validation_error` / `empty_acts` / `client_error`）
- `predicted_acts` vs `expected_acts`（L1）或草稿 diff（L4）
- `taxonomy`
- L0 是否被破坏

分类（`taxonomy`）：

| 类 | 含义 |
| --- | --- |
| `schema_invalid` | 非 JSON / 多字段 / 类型错 |
| `guessed_sku` | 规格或指代被写成 SKU 全称或 sku_id |
| `guessed_customer` | 「王老板」被写成店名全称 |
| `invented_number` | 原句没有的价或量 |
| `spec_as_product` | 八零果进了 `product_mention` 且无 `spec_mention` |
| `dropped_act` / `extra_act` | 连报丢失或多造动作 |
| `fallback_to_rule` | 真模型本回合未产出合法 LLM 结果 |
| `unstable` | 三次不一致 |
| `focus_mismatch` | 光杆规格打错行（对照金脚本契约，不是让模型选行） |
| `l0_violation` | 安全层失败 |

存放：

- 运行产物默认**不进 git**（本地 / CI artifact：`docs/eval/runs/<utc>-<model>-<prompt_id>.json`）
- 仓库只收：本文件、报告模板、**已脱敏**的典型失败摘录（无 raw 密钥、无完整客户电话）
- 同一 `taxonomy` 重复出现 ≥ 3 次才允许讨论是否升 Prompt 版本；升版不得塞商品库

失败不得用于自动微调、不得回灌 Memory、不得当 Ontology 学习语料。
