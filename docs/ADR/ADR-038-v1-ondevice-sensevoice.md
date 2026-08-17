# ADR-038

标题：V1 按住说话默认用端侧 SenseVoice；不依赖系统听写，不改 Runtime

- 状态：proposed
- 日期：2026-08-17

## 背景

Flutter 今日开单本已能调现有 turns。真机系统听写（Google / 手机自带 RecognitionService）在国内常见机上不出字。Voice First 第一下失败，体验没有意义。

规格：[V1_SALES_CLERK_CHINA_ASR.md](../V1_SALES_CLERK_CHINA_ASR.md)。服从 [ADR-020](ADR-020-voice-adapter-not-runtime.md)、[ADR-037](ADR-037-v1-flutter-app.md)、[RUNTIME_FREEZE.md](../RUNTIME_FREEZE.md)。

## 问题

国内真机如何把按住的声音变成字，同时不把音频送进 Runtime、不把话术写成固定口令？

## 决策

1. 默认 ASR 是 **端侧 sherpa-onnx SenseVoice**。不把系统 SpeechRecognizer 当主路径。
2. 一段按住 → 零或一条 final 文本。partial 只可画「正在听」。禁止口令映射，禁止 LLM 修稿。
3. 自然语言仍只进现有 `POST /v1/sessions/{id}/turns`。音频不到 Runtime。
4. 云听写（阿里 / 讯飞）只作为可替换 Port，不是 P0 前提。
5. 禁止：改 Confirm Gate、新 Agent、库存 / 支付 / 财务、新增 `/voice` 业务口。

## 原因

开单智能已经在 Runtime。听写是 Input Adapter。系统听写在目标机上不可用，端侧中文模型不依赖 Google、不强制外部 API。

## 影响

- 好处：国内机可离线出字；供应商可换。
- 限制：APK 含约 230MB 模型；字准不是闸门；嘈杂档口是 P1。
