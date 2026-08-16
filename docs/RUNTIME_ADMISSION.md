# Runtime Admission（V0.3D G1–G4）

> 验证的不是「会不会抽 SpeechAct」，而是：**真实 LLM 能否稳定驱动已有开单 Runtime**。
>
> 冻结：不改 Prompt、Resolver、Policy、`confirm_gate`、OrderService、Memory。不上 ASR/TTS、ERP、LangGraph、Tool Calling。失败只记录，不为通过测试放宽闸门。

L1 live（qwen3.7-plus + `parser.v4`）已证明 `Text → SpeechAct[]`。本文件是 L4 金脚本准入。

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

## 第一次 live（qwen3.7-plus + parser.v4）

用户回报 Decision **B**：出现危险行为（猜 SKU/客户或确认闸门被绕过）。

当时的分类有误：G1/G2「该确认却没确认」被标成 `confirm_violation`，会把语言失败抬成 B。`confirm_violation` 只保留给「不该确认却确认了」（例如 G3 苹果仍 hang）。请再跑一次，把 **Failure taxonomy** 与 **Runtime结果** 整段贴回。

未得 A 之前仍不上语音。不改 Prompt / Resolver / Policy / Confirm Gate / Memory。
