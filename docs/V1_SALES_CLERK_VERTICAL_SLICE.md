# 农批 AI 销售开单员 V1 — 垂直切片

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)、[RUNTIME_FREEZE.md](RUNTIME_FREEZE.md)。
> 本阶段只允许修改：**垂直切片范围文档**；落地编码时只允许 **Demo / Workbench 呈现**（及证明闭环的测试）。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory / Runtime Freeze 边界。
>
> **不重构 Runtime。不新增 Agent。不改变 Confirm Gate。不引入库存 / 支付 / 财务。不做完整 ERP UI。**
>
> 规格 [V1_SALES_CLERK.md](V1_SALES_CLERK.md)。旅程 [V1_SALES_CLERK_USER_JOURNEY.md](V1_SALES_CLERK_USER_JOURNEY.md)。工作台 [V1_SALES_CLERK_WORKBENCH.md](V1_SALES_CLERK_WORKBENCH.md)。决策见 [ADR-029](ADR/ADR-029-v1-vertical-slice.md)。Pilot [V1_SALES_CLERK_PILOT_CHECKLIST.md](V1_SALES_CLERK_PILOT_CHECKLIST.md)。观察 [V1_SALES_CLERK_PILOT_OBSERVATION.md](V1_SALES_CLERK_PILOT_OBSERVATION.md)。数据边界 [V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md](V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md)。数据访问 [V1_SALES_CLERK_PILOT_DATA_ACCESS.md](V1_SALES_CLERK_PILOT_DATA_ACCESS.md)。接入 [V1_SALES_CLERK_PILOT_ONBOARDING.md](V1_SALES_CLERK_PILOT_ONBOARDING.md)。反馈 [V1_SALES_CLERK_PILOT_FEEDBACK_LOOP.md](V1_SALES_CLERK_PILOT_FEEDBACK_LOOP.md)。执行手册 [V1_SALES_CLERK_PILOT_RUNBOOK.md](V1_SALES_CLERK_PILOT_RUNBOOK.md)。

本文定义 **第一个完整可运行闭环** 的实现范围。不追求功能数量。

目标只有一句：

**证明 AI 员工可以坐在老板旁边，完成一天中最核心的一分钟工作。**

这一分钟是：喊出一单 → 改一口 → 好了 → 今日本上看得见。

---

## 0. 结论

1. 垂直切片 **复用已冻结流水线**，不新写开单内核。路径已经是：

```text
Input → Parser → Product Understanding → Resolver
  → Policy → OrderService → Event → Outbox
  → Memory | ERPNext Write Adapter → Draft Sales Order
装配层 Domain Query → Read Adapter → 今日开单本投影
```

2. 现网缺的不是「会不会开单」，是老板 **在一页上走完这一分钟并看见本子变了**。P0 只补 Demo / Workbench 呈现，把已有 API 摊开。
3. 复述当前草稿 **不是 Confirm**。Confirm 只有「好了」。确认不是付款、不是发货。
4. 只能改 **当前未确认** 单。已确认 turns 继续拒绝。
5. 金脚本用现网种子就能跑的客户（唯一 **李老板**）。产品文案里的「张老板苹果八十果二十箱」是同一条路径的说法；种子补张老板是 P1，不挡 P0。

---

## 1. 切片是什么 / 不是什么

| 是 | 不是 |
| --- | --- |
| 一条老板能走完的开单闭环 | 新 Runtime、新 Agent |
| 今日开单本上看得见结果 | ERP 列表、聊天窗、报表 |
| Fake ERP 上留下 Draft SO | submit、库存、收款、财务 |
| 5 分钟试用及格 | 档口全天功能清单 |

不做完整 ERP UI：入账只在已确认行旁显示「排队中 / 已进草稿 / 看不见」。

---

## 2. 核心流程（必须按此实现，不得另开旁路）

### 2.1 开单

输入（语音或文本，同一 turns）：

> 张老板苹果八十果二十箱

P0 金脚本用现网可跑的等价句（唯一客户，避免同名挡 5 分钟）：

> 开李老板的单，苹果六十件

流程（已存在，禁止重写）：

```text
Input
  → Parser
  → Product Understanding
  → Resolver
  → Policy / OrderService
  → Workbench 当前订单
```

输出：当前订单草稿。老板看见当前区有客户、有货、状态为待确认。口播是当轮 `reply_text`，前端不另编一句。

### 2.2 复述确认

AI 让老板看见（当前区 + 一句口播），例如：

```text
客户：  李老板
商品：  苹果（落到档案时点明具体货）
规格：  能从货行看见则看见；P0 不新拆字段
数量：  60件
状态：  待确认
```

产品故事里的张老板 / 80 果 / 20 箱，同一块区域，同一套规则。

注意：

- **复述不是 Confirm。** 本子停在待确认。没有「好了」不得留底、不得写 ERP。
- 口播继续只念 `reply_text`。当前区展示草稿字段，不是第二张嘴。
- P0 不改 Response / 不改口播语义。规格单独成列若现网 `label` 不够拆，标在当前区即可，不为此改 Parser。

### 2.3 修改

输入：

> 刚才苹果改30箱

（金脚本等价：当前是 60 件时说「苹果改 30 件」。）

只能修改 **当前未确认** 订单。改完仍待确认，当前区数量跟着变，再复述。还要再说「好了」。

禁止：修改 `confirmed`。已确认再喊改口 → 现网 409 `task_completed`，口播/界面明确这张已经定了。不为此改闸门。

### 2.4 确认

输入：

> 好了

结果（已存在，禁止另写确认逻辑）：

```text
Confirm Gate 通过
  → confirmed event
  → Outbox
  → ERPNext Draft Sales Order
```

明确：

| 确认是 | 确认不是 |
| --- | --- |
| 这笔生意事实成立 | 付款完成 |
| 可以留底 | 发货完成 |
| 账上出现 Draft SO | 财务过账 / 核销 |

缺价可确认，口播带「价未定」。ERP 失败不撤回「好了」。入账事后用眼睛看。

### 2.5 今日开单本

同一页展示（P0 必须从「概念」变成 Demo 上看得见）：

| 看见 | 来源（已有则只呈现） |
| --- | --- |
| 今日订单数量 | Workbench 当日 `tasks` 条数 |
| 当前订单 | `current_session_id` 对应草稿 |
| 待确认 | 未确认任务 |
| 已确认 | `status = confirmed` |
| 入账状态 | 已确认行上 `posting`：排队中 / 已进草稿 / 看不见 |

确认后本子必须变：当前合上，已确认 +1，入账字出现。不进 ERP 页面。

---

## 3. Demo 验收标准

对象：没有培训过的农批老板（或扮演者）。打开 `/`，可以提醒「按住说话」，不得替他填表、不得打开 `?dev=1`。

**5 分钟内完成四件事，缺一不可：**

1. **开第一张单** — 喊出客户和货，当前区出现待确认草稿  
2. **修改数量** — 未确认前改量，当前区变成新数量  
3. **确认** — 说或按「好了」，确认成功  
4. **看到今日开单本变化** — 已确认多一张，能看见入账状态  

卡住则不过：先登录、先选 ERP 菜单、改口变成两行、确认后仍当当前单改、本子没有变化、口播编单价、出现收款/库存入口。

金脚本（P0，现网种子）：

```text
开李老板的单
苹果60件          → 当前待确认
苹果改30件        → 仍待确认，数量 30
好了              → 已确认；今日本 +1；入账可见
```

产品口号脚本（P1 种子齐了再用）：`张老板苹果八十果二十箱` → `刚才苹果改30箱` → `好了`。

---

## 4. 实现优先级

落地时按此砍范围。P0 做完即本阶段完成。不要把 P1/P2 塞进这一刀。

### P0 — 必须完成

证明「旁边坐一分钟」成立。只动 Demo / Workbench 呈现和验收测试。

| 项 | 说明 |
| --- | --- |
| 开单走现有 turns | 语音或文本；不新入口、不改 Parser |
| 当前草稿可见 | 客户、货、数量、待确认；复述不是 Confirm |
| 未确认改量 | 只打当前单；禁止改 confirmed |
| 「好了」留底 | 现有 Confirm Gate + Outbox + Draft SO（Fake 即可） |
| 今日开单本在第一页 | 数量、当前、待确认、已确认、入账状态；确认后列表变化 |
| 5 分钟金脚本 | 上节四步；HTTP 测试锁住：改量后确认、workbench 已确认 + posting |
| 一张嘴 | 业务口播 = `reply_text` |
| 没有旁路 | 无库存、支付、财务、ERP 单据页、新 Agent、改闸门 |

P0 **不包含**：新客户「张老板」种子、同名消歧出现在 5 分钟必过项、真机噪声调优、点待确认恢复、作废已确认。

Demo 壳对金脚本两句做口令映射（不改 Parser）：`李老板苹果八十果二十箱` → `开李老板的单苹果二十箱`；`刚才苹果改30箱` → `苹果改30箱`。规格 80 果来自李老板档案默认，数量走「二十箱 / 30箱」。

### P1 — 下一阶段

开单岗更好用，仍在 Freeze 外侧。

| 项 | 说明 |
| --- | --- |
| 种子唯一张老板 | 让口号句与金脚本合一 |
| 显式下一单更醒目 | 确认后开第二张不串页 |
| 点待确认变当前 | 已有 `POST /v1/workbench/current`，做成可点 |
| 同名王老板进试用剧本 | 不是 5 分钟必过 |
| 货行上看见规格 | 不改 Parser；装配层能展示则展示 |
| 入账从排队中等到已进草稿 | 仍不进口播 |

### P2 — 暂不做

| 项 | 原因 |
| --- | --- |
| 收款 / 核销 / 发票 | 第二员工；确认不是付款 |
| 库存够不够挡确认 | ERP 驱动闸门 |
| 确认后改单 | Session 已结束 |
| 自动报价 / 静默套价 | 行情日变 |
| submit / 过账 SO | Adapter 越权 |
| 查账口令、完整 ERP UI | 新 SpeechAct / 做成 ERP 前端 |
| 第二员工、LangGraph | Freeze 禁止 |
| 作废 ERP 草稿 consumer | 日结增强，不是这一分钟 |

---

## 5. 允许改哪里

```text
允许：app/api/static/index.html（及必要的 Demo 壳）
      Workbench / Session 装配层投影的展示
      证明闭环的测试（HTTP / Demo 文案）
禁止：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate
      OrderService / Memory / reply_text 语义
      新 SpeechAct、新 Employee、库存支付财务
```

现网已经具备：turns、改口、`confirm_ok`、Outbox、Fake Draft SO、`GET /v1/workbench` 的 `posting`。P0 不要把这些再实现一遍。

---

## 6. 这一分钟减少的老板活

少抄一行、少改错数、少问伙计「写了没」。货和钱仍是老板自己的。切片只证明这一分钟，不证明一整天。

---

## 评审六问

1. **哪一层？** Demo / Workbench 呈现。流水线只调用，不重构。
2. **改 LLM 权限？** 否。
3. **改变 Confirm Gate？** 否。复述 ≠ 确认。
4. **污染 Memory？** 否。本子不存喊单原文。
5. **经 Event？** 确认仍经 Outbox 写 Draft SO。
6. **属于 Adapter 还是 Runtime？** Draft SO 与入账属已有 Adapter；开单属已冻结 Runtime。本切片属工作台可见性。
