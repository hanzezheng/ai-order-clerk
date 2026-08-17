# 农批 AI 销售开单员 V1 — 国内端侧听写

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)、[RUNTIME_FREEZE.md](RUNTIME_FREEZE.md)。
> 本阶段只允许修改：**Flutter Input Adapter 的 ASR Port**（`mobile/` 录音 + 端侧 SenseVoice）。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory / Runtime Freeze 边界。
>
> 决策见 [ADR-038](ADR/ADR-038-v1-ondevice-sensevoice.md)。

系统听写在国内真机上不出字。本阶段把「按住说话」换成端侧中文听写。不是新员工，不改 Runtime。

```text
按住录音
  → sherpa-onnx SenseVoice（设备上）
  → 一条 final 文本（老板原话，不映射口令）
  → POST /v1/sessions/{id}/turns
  → 现有 Runtime
```

音频不到 Runtime。不新增 `/voice`。不用 LLM 修识别结果。金脚本只留在测试里，不是老板必须喊的话。

第一次打 APK 前：

```bash
./scripts/fetch_sensevoice_model.sh
cd mobile && flutter build apk --release --target-platform android-arm64
```

模型 `model.int8.onnx` 不进 git，打包装进 APK。
