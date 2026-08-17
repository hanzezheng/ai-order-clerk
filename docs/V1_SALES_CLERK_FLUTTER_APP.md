# 农批 AI 销售开单员 V1 — Flutter App

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)、[RUNTIME_FREEZE.md](RUNTIME_FREEZE.md)。
> 本阶段只允许修改：**Flutter Input / 工作台壳**（`mobile/`）及必要文档、API 契约测试。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory / Runtime Freeze 边界。
>
> **不是 ERP 前端。不做库存 / 财务 / 支付 / CRM。不新增 Agent。不改 Runtime 核心。**
>
> 工作台规格 [V1_SALES_CLERK_WORKBENCH.md](V1_SALES_CLERK_WORKBENCH.md)。决策见 [ADR-037](ADR/ADR-037-v1-flutter-app.md)。

本文把老板手里的 **今日开单本** 做成可安装的手机 App。自然语言仍只进现有 `POST /v1/sessions/{id}/turns`。

---

## 0. 结论

```text
Flutter App（按住说话 / 今日开单本 / 档口绑定）
    → HTTP API
    → AI Employee Runtime（不改）
    → ERPNext Adapter（确认后 Draft SO；入账只投影）
```

第一目标：农批老板拿手机完成

```text
打开 App → 喊第一单 → 确认「好了」→ 查看今日开单本
```

音频不出 Runtime。设备上 ASR 成字，再 POST `text`。口播只展示/播 `reply_text`。

---

## 1. 这一层是什么

| 是 | 不是 |
| --- | --- |
| Input Adapter + 今日开单本壳 | Runtime、新 Agent、ERP 列表 |
| 一个老板绑定一个档口（本机） | 登录中台、多租户 CRM |
| 未确认可改、确认走现有闸门 | 确认后改单、收款、库存 |

---

## 2. 调用的现有 API

禁止新增自然语言入口。

| 动作 | API |
| --- | --- |
| 打开今日本 | `GET /v1/workbench` |
| 再开一单 | `POST /v1/workbench/tasks` |
| 点待确认变当前 | `POST /v1/workbench/current` |
| 看本单草稿 | `GET /v1/sessions/{id}` |
| 喊单 / 改口 / 好了 | `POST /v1/sessions/{id}/turns` |

`source=voice` 当按住说话；`好了` 按钮 `source=text` 且 `expect_more=false`。`seq` / `utterance_id` 与现网 Demo 相同。

确认成功后：Runtime 发 confirmed event → Outbox → Write Adapter → Draft SO。App 只刷新 workbench 上的 `posting`（排队中 / 已进草稿 / 看不见）。

---

## 3. 页面

只有两页：

1. **档口绑定**（第一次）：档口名。一个老板对应一个档口，存在本机。
2. **今日开单本**：当前订单、待确认、已确认、今日张数、入账状态、按住说话、好了。

当前订单展示：客户、商品、规格、数量、状态。规格从现有 `draft.lines[].label` 呈现，不改 Parser。

没有：库存、欠款、报表、聊天记录、`item_code`、加行表单。

---

## 4. 目录

代码在仓库 `mobile/`（Flutter，包名 `sales_clerk`）。

```text
mobile/lib/     App
mobile/test/    壳测试（Fake API，不启动 Runtime）
```

本机：

```bash
cd mobile
flutter pub get
flutter test
# 后端另开：python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
flutter run --dart-define=API_BASE=http://127.0.0.1:8000
```

Android 模拟器把 API 写成 `http://10.0.2.2:8000`。

---

## 评审六问

1. **哪一层？** Flutter Input / 工作台壳。
2. **改 LLM 权限？** 否。
3. **改 Confirm Gate？** 否。「好了」仍 POST 现有 turns。
4. **污染 Memory？** 否。不存喊单原文进 Memory。
5. **经 Event？** 确认仍经现有 Outbox；App 不直连 ERP。
6. **Adapter 还是 Runtime？** 语音在设备 Adapter；ERP 仍在现有 Adapter。Runtime 只消费 `text`。
