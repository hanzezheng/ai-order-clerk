# Runtime Admission（V0.3D G1–G4）

> 验证的不是「会不会抽 SpeechAct」，而是：**真实 LLM 能否稳定驱动已有开单 Runtime**。
>
> 冻结：不改 Prompt、Resolver、Policy、`confirm_gate`、OrderService、Memory。不上 ASR/TTS、ERP、LangGraph、Tool Calling。失败只记录，不为通过测试放宽闸门。

L1 live（qwen3.7-plus + `parser.v4`）已证明 `Text → SpeechAct[]`。parser.v6 用语言结构 few-shot 修多行货名+规格归属。本文件是 L4 金脚本准入。

---

## 怎么跑

本入口只组 **InMemory** 世界（与 G1–G4 种子目录一致），不连 Postgres，因此不需要 `sqlalchemy`。L1 `live_eval` 本来就不经过 `bootstrap`。

若本机还缺 pydantic 等语言层依赖：

```text
python3 -m pip install -e '.[dev]'
```

Fake（默认 CI，不发请求）：

```text
python3 -m app.agent.runtime_admission
```

Live（必须同时有密钥）：

```text
export RUN_LIVE_LLM=1
export LLM_API_KEY=…
export LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export LLM_MODEL=qwen3.7-plus
python3 -m app.agent.runtime_admission
```

产物：`docs/eval/runs/runtime_admission_report.md`（不进 git）。live 默认重复 **3** 次。

---

## 脚本

| ID | 流程 | 必须 | 禁止 |
| --- | --- | --- | --- |
| G1 | 开王老板的单 → 王记水果店 → 苹果60件 → 梨60件 → 加两个金边榴莲 → 苹果要烟台八零果 → 金边榴莲改三个 → 好了 | 消歧王记；苹果提升已有 FUJI80；refine 不裂行；榴莲 qty=3；`confirm_ok` | LLM 选 SKU；改闸门 |
| G2 | 开李老板的单 → 苹果60件 → 统货 → 再加20 → 好了 | 档案默认生效；qty=80；确认成功；`product_default` 不被 LLM 改写 | 静默改档案 |
| G3 | 开王老板的单 → 王记 → 苹果60件梨60件（`expect_more`）→ 好了 | 苹果 hang、梨入单、ack、确认失败 | 为完整订单猜苹果 SKU |
| G4.1 | 开王老板的单 | 继续问；不绑王强 | 猜店名 |
| G4.2 | 李老板 + 紫麒麟60件 | candidate；不建 SKU | 创建节点 |
| G4.3 | 王记 + 金枕60个 | 不落到金边 | 替品 |
| G4.4 | 还是以前那个价 | `use_old_price` 语言动作 | 编单价 |

G1 比口语清单多两步：`王记水果店`（否则无法确认）、`加两个金边榴莲`（否则无法改三个）。这是 Runtime 契约，不是让模型选行。

---

## 判定

| 码 | 含义 |
| --- | --- |
| A | 真模型 G1–G4 全绿且三轮快照一致 → Parser 可作默认语言入口 |
| B | LLM 仅实验；含 Fake 绿但未跑 live、危险行为、不稳定 |
| C | 失败主要在语言抽取，需改 Prompt 后重评（本阶段仍不改 Prompt） |

未得 A 之前，不上语音。

---

## live 结论（qwen3.7-plus + parser.v4）

| 项 | 值 |
| --- | --- |
| model | qwen3.7-plus |
| prompt_id | parser.v4 |
| dataset_rev | g1-g4.v1 |
| Decision | **C** |

Runtime：G1 fail；G2 / G3 / G4 未出现在失败脚本中。taxonomy：`spec_lost×1`，`wrong_act×1`。无 `guessed_sku` / `guessed_customer` / `confirm_violation`。

含义：

- 真模型可以驱动熟客（G2）、连报不中断（G3）、失败保持（G4）。
- 不能作为默认语言入口：王记规格闭环（G1）规格未落到已有 FUJI80，随后 `confirm_gate` 正确拒绝。
- 不上语音。不改 Resolver / Policy / Confirm Gate / Memory。

最可能机制（与 Fake 金脚本对照，本阶段不改 Prompt）：

G1 在「加两个金边榴莲」之后说「苹果要烟台八零果」。Session focus 在榴莲。`parser.v4` 写着规格「槽位只用 spec_mention」，光杆 `refine_spec` 会打在最后一行，苹果保持 hang，确认失败。这正好是 `spec_lost×1` + `wrong_act×1`。G2 的「统货」能过，是因为当时只有苹果一行。

下一阶段若升 Prompt（如 parser.v5），只允许改语言契约：句中带货名的规格必须带着 `product_mention`，禁止拆成「光杆 refine_spec」。不得为此改闸门或让模型选 SKU。

---

## parser.v6

Runtime 已 pin `parser.v6`（v5 文本保留）。few-shot 只示范语言结构，不塞 Catalog / SKU / 客户列表。不改 Resolver / Policy / Confirm Gate / Memory。

请用真模型重跑 L1 与 G1–G4（G1 默认三轮）：

```text
export RUN_LIVE_LLM=1
export LLM_API_KEY=…
export LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export LLM_MODEL=qwen3.7-plus
python3 -m app.agent.live_eval
python3 -m app.agent.runtime_admission
```

未得 A 之前仍不上语音。
