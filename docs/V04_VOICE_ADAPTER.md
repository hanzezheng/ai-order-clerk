# V0.4 Voice Adapter

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)。
> 本 Sprint 只允许修改：**Input Adapter**。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory / Response / Outbox。
>
> 当前版本：`v0.3-agent-intelligence`（Qwen + `parser.v6` 默认语言入口已得 Runtime Admission **A**）。
>
> 本文件是 V0.4 **语音壳**设计。产品细则见 [DESIGN.md](DESIGN.md)。决策见 [ADR-020](ADR/ADR-020-voice-adapter-not-runtime.md)。
>
> **只换两件事：** (1) `text` 的来源；(2) `reply_text` 的播出方式。
>
> **不改：** Parser、ProductUnderstanding、Resolver、Policy、Confirm Gate、OrderService、Memory、Response。

路径固定：

```text
Voice
  → ASR final text
  → POST /v1/sessions/{id}/turns
  → 现有 Runtime
  → reply_text
  → TTS 原句播出
```

---

## 0. 结论

V0.4 增加一层 **Voice Adapter**，挂在已有 `TurnIntake` **之外**。Runtime 继续只看见字符串 `text` 与控制字段 `is_final` / `utterance_id` / `seq` / `expect_more`。

| 层 | 职责 | 禁止 |
| --- | --- | --- |
| 设备 / PTT | 按住说话、打断、好了按钮 | 解析商品、选客户 |
| ASR Port | 一段按住 → **一条 final 文本** | partial 出站；用 LLM 修稿 |
| Voice Controller | 填 turns 字段、驱动状态机 | 调 Runner；改 `reply_text` |
| `TurnIntake`（已有） | 幂等、保序、丢弃 partial | 不感知音频 |
| Runtime（冻结） | 开单 | 不感知麦 / 喇叭 |
| TTS Port | **只念**当轮 `reply_text` | 重新生成回复；第二张嘴 |

准入前提：G1–G4 live 为 A（已满足）。本阶段绿灯是「同一 Runtime 结局 + 真机能按住说话」，不是 ASR 字准率、不是 TTS 好听。

---

## 1. Voice Adapter 架构

### 1.1 位置

Adapter 是壳，不是 Agent，不是新 HTTP 业务入口。自然语言仍然只进已有接口：

```text
POST /v1/sessions                    # 开任务，已有
POST /v1/sessions/{id}/turns         # 唯一语言入口，已有
GET  /v1/sessions/{id}               # 只读草稿，已有
```

禁止新增 `/voice`、WebSocket SpeechAct 流、把音频 POST 到后端。音频不出设备（或最多到 ASR 供应商，不到本仓库 Runtime）。

```text
┌─────────────────────────────────────────────────────────┐
│  Voice Adapter（本阶段新增，只在壳上）                    │
│                                                         │
│  PTT / Mic ──► AudioCapture                             │
│                   │                                     │
│                   ▼                                     │
│              AsrPort.final(audio) ──► text              │
│                   │                                     │
│                   ▼                                     │
│         VoiceController（PTT 状态机 + 字段策略）          │
│                   │                                     │
│                   │  TurnCommand                         │
│                   │  source=voice                        │
│                   │  is_final=true                       │
│                   ▼                                     │
└───────────────────┼─────────────────────────────────────┘
                    │
                    ▼
         TurnIntake.handle（已有，不改）
                    │
                    ▼
         SalesSessionRunner（冻结）
           Parser.v6 → Understanding → Resolver
           → Policy → OrderService → Memory → Response
                    │
                    ▼
              reply_text + draft
                    │
┌───────────────────┼─────────────────────────────────────┐
│                   ▼                                     │
│              TtsPort.speak(reply_text)                  │
│                   │                                     │
│                   ▼                                     │
│              Speaker / 屏幕同一句                        │
└─────────────────────────────────────────────────────────┘
```

### 1.2 模块边界

落地时（本文件不写代码）只允许新增壳侧模块，建议拆成：

| 模块 | 输入 | 输出 | 可替换 |
| --- | --- | --- | --- |
| `AudioCapture` | PTT 按下/松开 | 一段 PCM/容器音频 | 浏览器 / 原生 |
| `AsrPort` | 一段音频 | `AsrFinal { text }` 或空/失败 | Fake / 云 ASR / 端侧 |
| `VoiceController` | ASR final、按钮、当前 session | `POST turns` 的 JSON | 与 Demo 同态 |
| `TtsPort` | `reply_text: str` | 播放开始/结束/被打断 | Fake / 云 TTS / 端侧 |
| `VoiceUi` | 状态 + `reply_text` + `draft` | 按住说话 / 只读订单 | 现有 `index.html` 演进 |

现有 `TurnIntake` / `SalesSessionRunner` **不出现**在上表。Controller 只当 HTTP 客户端。

### 1.3 与现有 Demo 的关系

当前 Demo（`app/api/static/index.html`）是 **文本模拟麦**：textarea 当 ASR，`source=text`，且每句 `expect_more=false`。V0.4 把「模拟麦」换成真 ASR 后：

- 主路径：`source=voice`，字段策略见 §4。
- 开发逃生：保留文本框或 `?dev=1` 注入 Fake ASR，**必须走同一 Controller**，禁止另写一套 turns 拼装。
- 「一张嘴」不变：屏幕与喇叭都只用当轮 `reply_text`。禁止按 `draft` 拼接口播。

### 1.4 装配

| 环境 | ASR | TTS | Runtime |
| --- | --- | --- | --- |
| CI / 等价测试 | FakeAsr（注入金脚本原文） | FakeTts（记录被念的字符串） | 现网 InMemory |
| 本机 Demo | 可先 Fake，再换真 ASR | 可先 Fake，再换真 TTS | 现网 |
| 真机验收 | 真 ASR | 真 TTS | 现网；评测仍固定 InMemory 种子 |

切换供应商只换 Port 实现。禁止为某个 ASR 的 partial 协议改 Intake 或 Parser。

### 1.5 失败域

| 失败 | Adapter 行为 | Runtime |
| --- | --- | --- |
| 没听清 / 空 final | 不 POST；回 IDLE；UI「再说一遍」 | 不调用 |
| ASR 超时 / 供应商 5xx | 不 POST；不拿 partial 顶替 | 不调用 |
| turns 409 `seq_out_of_order` | 不自动改 seq 重放另一句；提示再说 | 草稿不变 |
| turns 409 `task_completed` | 必须 `POST /v1/sessions` 新任务 | 已确认单不可写 |
| LLM 语言入口超时 | **继承现有 Parser 兜底**；Adapter 不另调 LLM | 规则兜底仍是 Runtime 内已有路径 |
| TTS 失败 | 屏幕仍显示同一 `reply_text` | 不重跑 Runner |

Adapter **不得**在失败时让 LLM「决定下一句该说什么」或「把半句补全」。

---

## 2. ASR / TTS 接口边界

### 2.1 ASR Port

```text
AsrRequest
  audio          一次 PTT 按下到松开的完整缓冲
  utterance_id   由 Controller 在按下时发放，ASR 实现可当追踪号

AsrResult
  kind = final | empty | error
  text           仅 kind=final 时有值；已是要交给 Parser 的字符串
```

硬边界：

1. **只有 `kind=final` 可以离开 ASR 适配器**，交给 Controller 去 POST。
2. 供应商若推送 partial / incremental / `is_final=false`：允许画在「正在听」层（半透明、不落订单），**禁止**进入 `TurnCommand.text`。
3. 禁止用第二段模型（标点模型、纠错 LLM、热词 LLM）改写 final。热词表若必须有，只允许离线词典，且不得把「苹果」映射成 SKU 名。
4. 禁止把 `confidence`、`words[]`、`speaker` 传给 Runtime。
5. 禁止 ASR 输出 `SpeechAct`、JSON、`sku_id`。
6. 空文本、纯标点、纯噪音 → `empty`，不 POST。
7. 一次 PTT 只产生 **零或一条** final。不要把一次松开切成多条 turns（连报是 Parser 的事，不是 ASR 切片的事）。

### 2.2 TTS Port

```text
TtsRequest
  text = 当轮 HTTP 响应的 reply_text   # 逐字，禁止改写
  play_id  本轮播放号，打断时取消

TtsEvent
  started | ended | interrupted | failed
```

硬边界：

1. **TTS 不是生成器。** 禁止再调 Response、禁止再调 LLM、禁止按 `draft` / Timeline / Memory 另写一句。
2. 输入必须等于 HTTP 字段 `reply_text`。允许的唯一变换：供应商要求的编码（UTF-8）。禁止同义改写、禁止插入「老板您看一下」。
3. `reply_text == ""`（含 Intake 丢弃 partial 的空回复）→ 不播放。
4. `ignored=true` → 不播放。
5. 播放期间 PTT 按下 → 立即 `interrupted`，停止出声；不回滚已执行的那一轮业务。
6. TTS 失败不影响草稿；屏幕继续展示那句 `reply_text`。

### 2.3 一张嘴

| 通道 | 内容 |
| --- | --- |
| 喇叭 | `reply_text` |
| AI 区文字 | 同一 `reply_text` |
| 订单区 | API `draft` 只读投影（客户、行、数量、价未定）——**不是口播** |
| Timeline | 业务事件；无用户原话；`reply_text` 不进 Timeline（已有） |

旁白 / 引导（「先说开谁的单」）保持 UI 提示，不进 TTS。

---

## 3. PTT 状态机

状态机只存在 Voice Adapter / Demo，**不写入** `SalesSession`。Session 状态仍是 `drafting` / `confirmed` 等业务态。

```text
                    按下
        ┌──────────────────────────┐
        │                          ▼
      IDLE ──按下──► LISTENING ──松开且有 final──► PROCESSING
        ▲                │                              │
        │                │空/失败                       │ 200 + 未确认
        │                └──────────────► IDLE          │
        │                                               ▼
        └──────────── SPEAKING ◄──── TTS 开始播放
        │                 │
        │                 │ 播放结束 / TTS 失败
        │                 ▼
        │               IDLE
        │
        │  200 且 draft.status=confirmed
        └──────────────────────────► DONE
                                          │
                                          │ 按下（再开一单）
                                          ▼
                                   POST /v1/sessions
                                          │
                                          ▼
                                        IDLE
```

### 3.1 状态

| 状态 | 用户看到 | 麦 | 喇叭 | 可否 POST |
| --- | --- | --- | --- | --- |
| `IDLE` | 按住说话 | 关 | 关 | 否 |
| `LISTENING` | 正在听 | 开，缓冲音频 | 必须静音 | 否 |
| `PROCESSING` | 正在整理 | 关 | 关 | 本轮已发出，忽略新的松开 |
| `SPEAKING` | 按住说话（可打断） | 关，直到按下 | 在念 `reply_text` | 否 |
| `DONE` | 单已经定了 | 关 | 可把确认句念完 | 禁止对旧 session 再 turns |

### 3.2 转移规则

**IDLE → LISTENING**

- 指针/触控按下主按钮。
- 立刻发放本轮 `utterance_id`（见 §4.2）。
- 若上一轮 TTS 仍在响，先打断。

**LISTENING → PROCESSING**

- 松开 **且** ASR 给出非空 final。
- 此时才 `seq += 1` 并 POST。`is_final` 恒为 true。

**LISTENING → IDLE**

- 松开但 ASR `empty` / `error`。
- `seq` **不增加**，`utterance_id` 作废（不复用到下一句，避免空听与下一句撞幂等）。

**PROCESSING → SPEAKING**

- HTTP 200、`ignored=false`、`reply_text` 非空、草稿未确认。
- 先把 `reply_text` 写上屏幕，再 `TtsPort.speak`。

**PROCESSING → IDLE**

- HTTP 200 但 `reply_text` 为空（不应发生在 final；若发生则不播）。
- HTTP 4xx/5xx：提示再说一遍；**不要**为了对齐 seq 而重放另一句用户没说的话。

**PROCESSING → DONE**

- `draft.status == "confirmed"`。允许把确认句 TTS 念完，念完仍停在 DONE。

**SPEAKING → LISTENING（打断）**

- 按下 PTT。停 TTS。新的 `utterance_id`。上一轮业务 **已经完成**，不得 rollback。

**SPEAKING → IDLE**

- 播放结束或 TTS 失败。

**DONE → IDLE**

- 按下主按钮或「再开一单」：`POST /v1/sessions`，本地 `seq=0`。禁止继续向已确认 session POST（现网会 409 `task_completed`）。

### 3.3 互斥

| 事件 | 处理 |
| --- | --- |
| PROCESSING 时再按 PTT | 忽略。防止双 seq。 |
| PROCESSING 时点「好了」 | 忽略。 |
| LISTENING 时点「好了」 | 先结束收听（按松开处理）；不要同时发「好了」和第二句货。 |
| 已确认后说货 | 必须新 session。 |
| 芯片示例 | 视为 Fake ASR final，走同一 Controller，不得绕过字段策略。 |

### 3.4 连报手势

档口连报的产品语义是 **`expect_more=true` 时 Runtime 不追问**，不是「一个 PTT 里切多段 ASR」。

推荐手势：

- 普通按住 → 松开 = 一句 final，`expect_more=true`（§4.4）。
- 老板可以连续多次按住，每句都是新的 `utterance_id` / `seq`。
- 「好了」按钮或口令 = 结束连报。

禁止：用 VAD 静音自动切句并自动确认；禁止「沉默 800ms 就当好了」。

---

## 4. `is_final` / `utterance_id` / `seq` / `expect_more` 策略

现网 Intake 语义（**不改**，Adapter 必须遵守）：

| 字段 | 现网 |
| --- | --- |
| `is_final=false` | 丢弃，不调 Runner，不占 `seq` |
| 同一 `utterance_id` | 返回首次 payload（幂等） |
| `seq` 非 `last+1` | 409 `seq_out_of_order`，V1 不缓冲 |
| `expect_more=true` | 可写草稿，`reply_mode=ack`（`session_block` 仍优先问） |
| `source` | 仅标记；Runtime 不分支 |

### 4.1 `is_final`

Adapter **只发送 `true`**。

| ASR 事件 | POST？ | `is_final` |
| --- | --- | --- |
| partial / 中间结果 | 否 | — |
| final 非空 | 是 | `true` |
| 松开但无 final | 否 | — |

不要依赖 Intake 丢弃来当主路径。Intake 丢弃是防御网，不是产品设计。测试必须证明 Adapter 在出站前已经丢掉 partial（§5.2）。

### 4.2 `utterance_id`

| 规则 | 说明 |
| --- | --- |
| 发放时机 | PTT **按下**（LISTENING 开始），UUID |
| 一生一次 | 一次按下–松开最多一次成功 POST |
| 重试 | 同一 final 因网络重试 POST，必须带**同一个** id + 同一个 seq + 同一 text |
| 作废 | 空听 / ASR 失败：id 丢弃，下次按下新发 |
| 禁止 | 用供应商 session id 当业务幂等键（不稳定）；跨 session 复用 |

partial 若仅用于 UI，可以在内存里暂存同一 `utterance_id`，但它们从不 POST，因此不会撞幂等。

### 4.3 `seq`

| 规则 | 说明 |
| --- | --- |
| 范围 | 单个 `SalesSession` 内从 1 递增（与现网测试一致：第一句 `seq=1`） |
| 增加时机 | 即将发出 `is_final=true` 且非空 text 的那一刻 |
| 不增加 | partial、空听、ASR 失败、被忽略的 PROCESSING 重复点击 |
| 权威 | 本机 Controller 是该 session 的唯一写者。不要用 GET 猜 seq（API 不暴露 `last_seq`） |
| 409 | 视为外壳失步。提示再说。下一句继续尝试 `local_seq+1` 之前，先 `POST /v1/sessions` **仅当**确认已 409 `task_completed`。普通乱序不要擅自开新单（会丢草稿） |
| 确认后 | 新 session 从 1 再计 |

芯片、「好了」按钮与语音共用同一 `seq` 计数器。

### 4.4 `expect_more`

这是壳策略，不是 Parser 策略。**禁止 LLM / VAD / 置信度**参与判定。

| 用户动作 | `expect_more` | 理由 |
| --- | --- | --- |
| 普通 PTT 松开（报客户、报货、改口、消歧） | `true` | 档口连报默认未结束；Runtime ack，不问价/规格 |
| 主按钮「好了」 | `false`，`text="好了"` | 明确结束 |
| 口令整句是结束词 | `false` | 封闭词表，见下 |
| 一句里既有货又有结束词（「苹果60件好了」） | `false` | 整句交给 Parser；壳不拆句。`false` 才允许 recap / 走确认后的回复模式 |
| 文本 Demo / 芯片（非连报） | 与上表同一套规则，按那条 **text** 判 | 禁止语音一套、芯片一套 |

**结束词表（封闭、大小写与空白 trim 后精确或整句匹配）：**

```text
好了
就这样
可以了
定了
```

只允许这张表扩词，必须改本设计再改壳。禁止「听起来像说完了」。禁止把「不对」当结束。

**明确禁止：**

- 静音 N 秒 → `expect_more=false`
- ASR `confidence` 低 → 改字段或吞句进业务
- 用 LLM 判断「用户是否说完」
- 因 `reply_mode=ack` 觉得冷淡，就在壳上改成 `false` 逼 Runtime 追问

`session_block`（同名客户）优先于 ack：这是 Runtime 已有行为，Adapter 无需、也不得改。

### 4.5 `source` 与 `text`

- 真 ASR 与 Fake ASR：`source="voice"`。
- 仅当用户在开发框里**打字**且不经过 AsrPort：`source="text"`。两种 source 的 Runtime 结局必须等价（§5）。
- `text` = ASR final 原串（trim 首尾空白）。禁止壳把「六十五」换成「65」、禁止补「件」。那是 Parser 的事。

### 4.6 推荐出站包

普通一句货：

```json
{
  "text": "苹果60件梨60件",
  "source": "voice",
  "utterance_id": "…",
  "seq": 3,
  "is_final": true,
  "expect_more": true
}
```

结束：

```json
{
  "text": "好了",
  "source": "voice",
  "utterance_id": "…",
  "seq": 4,
  "is_final": true,
  "expect_more": false
}
```

---

## 5. Text 与 Voice 等价测试

目标：证明 Adapter 只换管道，不换业务。**断言草稿与闸门，不用口播好听代替 SKU。**

### 5.1 等价定义

对同一 `SalesSession` 种子世界，逐步输入相同 `text` 序列：

| 左 | 右 |
| --- | --- |
| `source=text`，直 POST turns（现网 `test_api_turns` 风格） | FakeAsr 注入同一 text，经 Controller 组包，`source=voice` |

每步必须相等：

- `draft.status` / customer id 与 name / 每行 `line_id` 稳定策略下的 sku、qty、uom、`line_status`
- `verdict.confirm_ok`、`reply_mode`、issue `code` 集合
- `commands_executed`
- `reply_text`（同一张嘴）
- Timeline `event_type` 序列；payload 仍禁止聊天字段

允许不等：HTTP 的 `source` 字段本身、`utterance_id` 值、音频相关日志。

### 5.2 必须落地的测试（设计；本文件不写代码）

**E1 金脚本等价（G1–G4）**

- FakeAsr 按 [RUNTIME_ADMISSION.md](RUNTIME_ADMISSION.md) 逐步吐出 G1 / G2 / G3 / G4.1–G4.4 原文。
- G3 连报句必须 `expect_more=true`（Controller 规则，不是手写分叉）。
- 「好了」必须 `expect_more=false`。
- 与 `source=text` 直打同一序列的快照 diff 为空。

**E2 partial 永不进业务**

- FakeAsr 先推 `苹果` partial，再推 `苹果60件` final。
- 断言：partial 阶段零 HTTP 或仅内部 UI；草稿行数仍 0。
- final 后与纯文本「苹果60件」等价。
- 即便误测向 Intake 发 `is_final=false`，现网仍丢弃——回归保留，但不算 Adapter 合格。

**E3 幂等**

- 同一 `utterance_id`+`seq`+text 连 POST 两次：一行货，两次 `reply_text` 相同。
- Fake 网络重试不得加行。

**E4 seq**

- 空听不占号：空结果后再说「开李老板的单」，该句 `seq=1` 成功。
- 乱序 409 后草稿不变。

**E5 TTS 契约**

- FakeTts 收到的字符串 `==` 响应 `reply_text`。
- `ignored` / 空回复：FakeTts 调用次数为 0。
- 禁止测试去断言 SSML、禁止断言「更口语的改写」。

**E6 打断不回滚**

- 一轮已 200 且草稿已有「苹果60件」，SPEAKING 中打断，再听下一句。
- 苹果行仍在；新句按新 `seq` 执行。

**E7 确认后新 session**

- 「好了」成功后，下一句货不得写进旧 session（409 或 Controller 先开新单）。
- 新单草稿为空。

**E9 ASR 错误隔离**

- ASR 输出什么，`TurnCommand.text` 就是什么（只允许 trim）。
- 禁止语音层把「六十五」改成 `65`、把「金枕」改成「金边」、补 `sku_id` / `product_mention`。
- HttpAsrPort 若收到 `is_final=false`，必须变成 empty，不得出站。

### 5.3 不测什么

- 真 ASR 字错误率、口音、信噪比（归真机脚本，且分类为外壳失败，不是 Runtime 失败）。
- Parser 抽槽（G1–G4 / L1 已测）。
- Policy / confirm_gate 新语义。

CI 默认：FakeAsr + FakeTts + InMemory。不发 ASR/TTS 供应商请求。不把 live LLM 当作 Voice 等价的前提（语言层已有独立 Admission）。

---

## 6. 真机验收脚本

对象：真麦克风 + 真 ASR + 真 TTS + 现网 Runtime。主持人按本表打勾。失败必须勾 **分类**，禁止把 ASR 听错写成「闸门坏了」。

### 6.1 环境

| 项 | 要求 |
| --- | --- |
| 设备 | 一部手机或带麦的笔记本；用 PTT，不用免提一直听 |
| 网络 | 能访问 turns 与所选 ASR/TTS |
| 数据 | 与 G1–G4 相同的种子客户/商品（李老板、王记/王强、苹果树、金边） |
| 页面 | 默认 `/`，不要 `?dev=1`（排障时另开） |
| 噪声 | 至少一轮在有人走动的环境说完 G2 |

### 6.2 分类

| 码 | 含义 | 是否阻塞 V0.4 壳合格 |
| --- | --- | --- |
| `ASR` | 听成别的字，导致 Parser 合理失败 | 记录；同一句用 Fake 能过则不判 Runtime 回归 |
| `TTS` | 念对了但听不清 / 被打断体验差 | 记录；`reply_text` 正确则业务仍过 |
| `ADAPTER` | partial 进了单、TTS 另说一句、沉默当确认、已确认还写旧 session | **阻塞** |
| `RUNTIME` | 听对了但闸门/合行/消歧与文本路径不一致 | **阻塞**（先停语音，回 V0.3） |

### 6.3 脚本 A — 熟客 30 秒（G2）

对麦按住，一句一松（除注明外）：

1. 「开李老板的单」
2. 「苹果60件」
3. 「统货」
4. 「再加20」
5. 「好了」（可口说或按钮）

必须：

- 确认成功；口播与屏幕同一句，且含「价未定」类既有义务（以 `reply_text` 为准）。
- 数量 80，一行苹果，档案默认未被改写。
- 连报过程中 TTS 不得追问「哪种苹果多少钱」（`expect_more=true` 的 ack）。
- Timeline 无用户原话。

### 6.4 脚本 B — 消歧与规格（G1）

1. 「开王老板的单」→ 必须问哪一家，不得绑王强。
2. 「王记水果店」
3. 「苹果60件」
4. 「梨60件」
5. 「加两个金边榴莲」
6. 「苹果要烟台八零果」→ 改苹果规格，不得打到榴莲行。
7. 「金边榴莲改三个」
8. 「好了」→ 允许确认。

任一步 ASR 听错：在记录里写下 **听到的字**，用文本再打一遍对照。听对仍做错 = `RUNTIME`。

### 6.5 脚本 C — 连报不中断（G3）

1. 「开王老板的单」→ 「王记水果店」
2. **一次按住**说「苹果60件梨60件」松开，`expect_more` 必须为 true。
3. 必须：苹果 hang、梨在、ack、不追问。
4. 「好了」→ **不得确认**（苹果无 SKU）。梨行还在。

禁止：松开后因静音自动再发「好了」。

### 6.6 脚本 D — 失败保持（G4）

各开新单：

| 步 | 说 | 必须 |
| --- | --- | --- |
| D1 | 「开王老板的单」 | 继续问；不绑王强 |
| D2 | 李老板 + 「紫麒麟60件」 | 留下 mention；不建 SKU |
| D3 | 王记 + 「金枕60个」 | 不落到金边 |
| D4 | 李老板苹果后「还是以前那个价」 | 不编单价 |

### 6.7 脚本 E — 外壳专测（真机）

| ID | 操作 | 必须 |
| --- | --- | --- |
| E-PTT | 按下看到「正在听」，松开才整理 | 按下瞬间不得已有新货行 |
| E-PARTIAL | 慢慢说「苹果六十件」，看中间字幕 | 字幕可变；**订单区不得出现半句行** |
| E-EMPTY | 按住不说话松开 | 不占单；下一句仍能开李老板 |
| E-BARGE | 确认前让 TTS 念到一半，按住说改口 | 喇叭立刻停；上一轮已写入的行仍在 |
| E-DONE | 确认后立刻说「梨60件」 | 进新单或被拒写旧单；旧单保持 confirmed |
| E-MOUTH | 拔掉喇叭 / TTS 故意失败 | 屏幕仍是那句 `reply_text`，没有第二句 |

### 6.8 合格线

V0.4 壳 **设计验收**（实现后）：

1. §5 E1–E8 在 CI Fake 路径全绿。
2. 真机脚本 A、C、E 各至少成功 1 次（听对的前提下）。
3. 无 `ADAPTER` 类缺陷。
4. 无新增 `RUNTIME` 相对文本基线的漂移。

不把「嘈杂市场 ASR 全对」当绿灯。那是供应商问题，不回写 Parser。

---

## 7. 明确禁止

- 改 Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory / Response
- ASR partial 进入 `TurnCommand` 或 Runner
- TTS 重新生成或改写 `reply_text`
- LLM 参与 PTT、endpointing、`expect_more`、打断、热词纠错
- 新的语音 Agent、多 Agent、LangGraph 开单图
- ERP / 库存 / 支付 / 自动建 SKU
- 把音频、原文、ASR nbest 写入 Timeline 或 Memory
- 用静音当确认
- 前端按草稿拼接口播
- 已确认 session 继续加行

---

## 8. 设计批准后的落地顺序

仍不在本文件写代码。顺序只约束以后的实现 PR：

```text
1. AsrPort / TtsPort + Fake          ✅ `app/voice/`
2. VoiceController 状态机 + 字段策略 ✅
3. §5 等价测试（E1–E9）              ✅ `app/tests/test_voice_adapter.py`
4. Demo 迁到同一 Controller          ✅ `voice-controller.js`
5. 接真 ASR / TTS（可配置，CI 默认 Fake）✅ 浏览器 SpeechRecognition / speechSynthesis；可选 `ASR_URL` / `TTS_URL`
6. 按 §6 真机打勾                    真机主持人脚本，不在 CI
```

任一步需要改冻结内核才能「好演示」→ **停**，回设计，不改闸门。
