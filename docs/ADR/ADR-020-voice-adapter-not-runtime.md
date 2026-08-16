# ADR-020

标题：语音只做 Adapter；ASR/TTS 不得进入 Runtime

- 状态：proposed
- 日期：2026-08-16

## 背景

V0.3D 上，qwen3.7-plus + `parser.v6` 的 G1–G4 Runtime Admission 为 A。语言入口可以默认。产品下一增量是档口按住说话，而不是新的开单图。

现网已有唯一自然语言入口 `POST /v1/sessions/{id}/turns`，以及 `TurnIntake` 对 `utterance_id` / `seq` / `is_final` 的幂等与丢弃。Demo 仍用文本模拟麦。

若把 ASR partial、TTS 生成、LLM 端点检测做进 Parser / Policy / Response，会把外壳噪声写成业务语义，并堵死供应商替换。

## 问题

真麦克风和真喇叭接在哪一层？谁决定 `expect_more`？TTS 是否可以「说得更好听」？

## 决策

1. **V0.4 只增加 Voice Adapter**（采集、ASR Port、PTT 状态机、TTS Port）。音频不到 Runtime。自然语言仍只进现有 turns。
2. **ASR 只交出 final 文本。** partial 可画 UI，禁止 POST。禁止用 LLM 修识别结果。
3. **TTS 只念当轮 `reply_text`。** 禁止再生成。屏幕与喇叭同一句。失败仍展示该句。
4. **`expect_more` 由壳用封闭规则填写：** 普通 PTT 默认 `true`；结束词表或「好了」按钮为 `false`。禁止 VAD 静音当确认，禁止 LLM 判断说完。
5. **冻结** Parser、ProductUnderstanding、Resolver、Policy、Confirm Gate、OrderService、Memory、Response。不上 ERP、多 Agent、LangGraph 开单。
6. **合格标准**是 Text/Voice 等价（同一 `text` 序列草稿与闸门一致）加上真机外壳脚本，不是 ASR 字准率。

细则：[V04_VOICE_ADAPTER.md](../V04_VOICE_ADAPTER.md)。

## 原因

档口产品是 Voice-first 开单员，但开单智能已经在 Runtime。语音只替换 text 来源和 reply 播出。Intake 已能丢弃 partial、幂等、保序；Adapter 必须把这些当契约遵守，而不是另做一套会话协议。

## 影响

- 好处：可换 ASR/TTS 供应商；G1–G4 文本基线可直接当 Voice 等价夹具；确认闸门不被「听不清」绑架。
- 限制：一次 PTT 只一条 final，连报靠 Parser 多 act；乱序 seq 仍 409；真机听错记为 ASR 类失败，不回写内核。
