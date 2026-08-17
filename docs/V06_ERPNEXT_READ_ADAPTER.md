# V0.6 ERPNext Read Adapter

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)。
> 本 Sprint 只允许修改：**ERPNext Read Adapter**（本文件为设计；实现另批）。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory。
>
> 当前版本：`v0.5 ERPNext Write Adapter`（Draft Sales Order 已写入）。
>
> **只输出设计，不写代码。** 最高架构约束仍是架构文。产品细则见 [DESIGN.md](DESIGN.md)。决策见 [ADR-023](ADR/ADR-023-erpnext-read-adapter.md)。

路径固定（读与写分离）：

```text
写：order.confirmed → Outbox → Write Adapter → Draft Sales Order

读：装配层 Domain Query → Read Adapter → 领域事实投影
                              ↑
                         只在 Adapter 内
                         DocType / item_code / REST
```

ERPNext 是企业业务事实系统。AI Runtime 是自然语言业务执行层。Read Adapter 让员工**看见**公司账，不让账本**指挥**开单。

---

## 0. 结论

V0.6 **需要独立的 Read Adapter**。V0.5 Write Adapter 不能兼读。

| 真 | 假 |
| --- | --- |
| 员工读取本 Runtime 已经写入的销售事实 | 员工用库存/信用/科目做开单裁决 |
| Runtime 问领域问题（这张单投递了吗） | Runtime 拼 SQL / `frappe.get_doc` / DocType |
| 事实进 Workbench / Session **投影** | 事实进 `OrderLine` / Catalog / Memory |
| ERP 失败 → `unavailable` | ERP 失败 → 改 `confirm_ok` 或 HTTP 500 |
| `query_draft` 仍是本单 Runtime 草稿 | 「现在有啥」去搜 ERP 订单列表 |

评审六问：

1. **哪一层？** ERPNext Read Adapter（与 Write 同属 Adapter 层，不同端口）。
2. **改 LLM 权限？** 否。不新增 SpeechAct，不把 ERP 表交给 Parser。
3. **绕过 Policy？** 否。读结果不得变成 `session_block` / `line_hold` / `confirm_ok`。
4. **污染 Memory？** 否。不写 Evidence / Alias / PriceMemory。
5. **经 Event？** **写**仍经 Outbox。**读**是同步领域查询，不是第二套 Outbox。
6. **属于 Adapter 而非 Runtime？** 是。`item_code` / DocType / `warehouse` 只存在 Adapter。

本阶段**不改口播**。`reply_text` 仍只由现网 Policy + Response 生成。老板从工作台/Session 投影看见账本状态；要让员工**用嘴说**账本，必须另批且只允许增加 `notice`（不得动 Confirm Gate）。

---

## 1. 为什么必须有 Read Adapter

### 1.1 Write 不能兼读

| | V0.5 Write | V0.6 Read |
| --- | --- | --- |
| 触发 | `order.confirmed` 已经发生 | 老板看工作台 / Session GET / 装配层在回合后投影 |
| 方向 | Runtime → ERP | ERP → 领域事实 |
| 时机 | 事务 A 提交后的 drain | 查询当时 |
| 失败 | 不 mark，重试；Runtime 已 confirmed | 返回 `unavailable`；Runtime 开单继续 |
| 幂等 | 禁止重复建 SO | 天然可重复读 |
| 调用者 | Outbox Consumer | 装配层 `EnterpriseFactPort` |

把 GET 塞进 `ErpnextConsumer.consume` 会把查询绑在确认事件上：未确认看不到，确认失败的重试队列也会被读请求污染。

### 1.2 禁止的替代方案

| 方案 | 为什么拒绝 |
| --- | --- |
| `OrderService` / `confirm_gate` 直调 ERP REST | 错误路径；ERP 驱动 AI |
| Parser 输出 `doctype` / `item_code` | 语言层污染 |
| Resolver 用 ERP Item 搜「苹果」 | Catalog 被账本取代 |
| ContextLoader 扩字段给 Policy 用 | `BusinessContext` 是 Notice 输入；Policy 冻结 |
| Response 自己去读 ERP 再多说一句 | 违反 [ADR-006](ADR/ADR-006-response-not-override-policy.md) |
| 把跨单 ERP 列表塞进 `SalesSession` | 违反 Session = 一张订单 |
| LLM 写 SQL / 动态 filters | 禁止 |

### 1.3 位置

```text
老板 → Input Adapter → Turn Intake → Parser → Understanding
     → Resolver → Policy → OrderService → Event → Outbox
                                              │
                                              v
                                        Write Adapter → ERPNext
                                              │
装配层（TurnGateway / Workbench / Session GET）
     │
     │  EnterpriseFactPort（领域键：customer_id / order_id）
     v
Read Adapter → ERPNext GET
     │
     v
领域事实投影（无 DocType）
     ├─ Workbench 任务卡片
     └─ Session 只读侧栏（不是 draft.lines）
```

Read Adapter 与 Voice Adapter、Write Adapter 对称：都在 Runtime **之外**。Voice 换 text 来源；Write 换「确认后写到哪」；Read 换「公司账怎么翻译成员工能看的事实」。

禁止新增「给 ERP 用」的自然语言入口。自然语言仍只进 `POST /v1/sessions/{id}/turns`。

---

## 2. ERPNext 只读查询边界

只读 **V0.5 已经写入** 的文档，外加它们的投递状态。不扩大 ERP 能力面。

### 2.1 允许查询（白名单）

查询键只能是 **Runtime id**（经 correlation 翻译）。禁止用老板原话、`utterance_id`、ERP `name` 模糊搜。

| 查询 | 键 | 目的 |
| --- | --- | --- |
| 本单投递状态 | `runtime_order_id` | 确认之后，Draft SO 是否已在账上 |
| 本单标记 | 同上 | `prices_incomplete` 是否仍在 ERP 草稿上（只读，不回写行价） |
| 已绑定客户的未过账销售单计数 | `runtime_customer_id` | 工作台对账；**不是**本 Session 的行 |

返回必须先经 Adapter 剥掉 ERP 字段，变成 §4 的领域事实。

实现时允许的 ERP API（只在 Adapter 内）：

- `GET /api/resource/Sales Order`，filter = `runtime_order_id` 或 correlation 里的 SO name
- `GET /api/resource/Customer`，filter = `runtime_customer_id`（只为确认映射仍在，不把 ERP 客户名写回 Runtime）
- 禁止 `GET /api/resource/Bin`、`Item` 按 `item_name` like、`GL Entry`、`Sales Invoice`、`Payment Entry`

CI 默认不连真站：`FakeErpGateway` 的内存 SO 列表即读模型。

### 2.2 禁止查询（黑名单）

| 禁止读 | 原因 |
| --- | --- |
| 库存（Bin / Warehouse / Stock Ledger） | 库存自动决策；ERP 驱动 AI |
| 信用额度、应收账款、账期 | 财务驱动确认 |
| Price List / Item Price 写回行价 | 自动改价 |
| Item 按名称/规格搜索 | 反向污染 Resolver / Catalog |
| Customer 按 `customer_name` 模糊搜 | 反向覆盖 Runtime 已绑定客户 |
| Submitted SO / Delivery Note / Invoice / Payment | V0.5 未写这些；读了会诱使过账 |
| 其他公司、其他用户的单据 | 无租户模型 |
| `tab*` SQL、Report、Frappe Query Builder | DocType 进 Runtime 的捷径 |
| 未确认草稿行对应的 ERP 文档 | 公司事实尚未发生 |

### 2.3 相关表仍只住 Adapter

沿用 V0.5：

```text
erp_customer_map  (runtime_customer_id → erp_customer_name)
erp_item_map      (runtime_sku_id → item_code)
erp_order_map     (runtime_order_id → sales_order_name)
```

读路径：**correlation 优先**，ERP GET 作确认。

| correlation | ERP GET | 投影 |
| --- | --- | --- |
| 无 SO | 无 | `pending`（Runtime 已确认但尚未投递，或未确认） |
| 有 SO | 通、仍是 Draft | `posted` |
| 有 SO | 超时/5xx | `unavailable`（不改 Runtime 单） |
| 无 SO | 却搜到同 `runtime_order_id` | `posted`（Write 已建、mark 前崩溃的恢复态） |

禁止把 ERP `name` / `item_code` 写入这些表以外的任何 Runtime 表。

---

## 3. AI Runtime 如何查询 ERP 数据

答案：**Runtime 内核不查询。装配层查询。**

### 3.1 领域端口（设计形状，本文件不写代码）

建议端口名：`EnterpriseFactPort`。方法只接受 UUID，只返回领域事实。

```text
posting_for(runtime_order_id) -> OrderPostingFact
open_draft_count(runtime_customer_id) -> int   # 仅 Workbench 用
```

禁止出现在端口签名里：`doctype`、`item_code`、`warehouse`、`filters`、`sql`、`frappe`。

实现类：`ErpnextReadAdapter`，放在 `app/erpnext/`，与 Write 共用 Fake / correlation / `HttpErpGateway` 的 GET。禁止被 `app/agent` `app/policy` `app/services/order_service.py` `app/memory` import。

### 3.2 谁可以调用端口

| 调用者 | V0.6 | 说明 |
| --- | --- | --- |
| TurnGateway / 装配（回合提交之后） | 允许 | 给 Session 投影附上本单 `posting`；失败吞掉 |
| Workbench 快照装配 | 允许 | 任务卡片上的投递状态；跨单计数 |
| `GET /v1/sessions/{id}` 投影 | 允许 | 侧栏，不进 `draft.lines` |
| Parser / Understanding / Resolver | **禁止** | 冻结 |
| Policy / Confirm Gate | **禁止** | 冻结；否则 ERP 驱动裁决 |
| OrderService | **禁止** | 与 V0.5 同一禁令 |
| Memory Extractor | **禁止** | 不学账本 |
| ResponseGenerator | **禁止** | 只能吃 ReplyPlan |
| LLM / Prompt | **禁止** | 不得带 ERP JSON |

### 3.3 现有 SpeechAct 不改语义

| SpeechAct | V0.6 |
| --- | --- |
| `query_draft`（「现在有啥」） | **仍只念 Runtime 本单草稿**。禁止改去列出 ERP SO |
| `confirm_order` | 闸门不变；确认后仍只走 Write Outbox |
| 其它开单动作 | 不变 |

老板说「李老板账上还有单吗 / 进 ERP 了没」——现网没有对应 SpeechAct。V0.6 **不新增** `query_ledger`。那要改 Parser，本阶段冻结。登记为后续：解冻 Parser 之后才能把「查账」变成领域查询 SpeechAct，且仍须经 Policy 决定说不说。

### 3.4 同步查询，不是第二套 Outbox

读是拉模型。为了语音回合不把 ERP 超时做成 500：

- 超时预算短（与 Write HTTP 同量级，数秒）
- 失败 → `unavailable`，装配层继续返回 200
- **禁止**用 Outbox 做「查询请求」往返（会把读变成最终一致的聊天，口播无法当回合回答）

Write 仍然最终一致。Read 承认短暂不一致：`pending` 表示「单已确认、账尚未见到」。这是正确的员工认知，不是 bug。

---

## 4. 哪些数据允许进入 Context

这里的 Context = 员工可看见的只读投影。**不是**把 ERP 行塞进 `SalesSession.draft`。

`BusinessContext`（`profile_defaults` / `price_facts`）**保持不变**。它是 Policy Notice 的输入，字段已被测试钉死。ERP 事实用**兄弟投影** `EnterpriseFacts`，Policy 看不到。

### 4.1 允许进入 Session 投影（本单）

仅当 `draft.status == confirmed` 且有 `order_id`：

| 领域字段 | 含义 | 不包含 |
| --- | --- | --- |
| `posting` | `pending` / `posted` / `unavailable` | ERP `name` |
| `prices_incomplete` | 与确认时一致的只读回显 | 行 `rate`、Price List |
| `line_count` | 账上草稿行数（对账） | `item_code`、qty 明细（V0.6 不必回放行，避免把 Item 形状带进 API） |

未确认：不查 ERP，投影为「无企业事实」（空）。禁止对草稿行预演「如果确认会写成哪张 SO」。

### 4.2 允许进入 Workbench（班次，跨单）

Workbench 本来就是跨单索引（[ADR-012](ADR/ADR-012-workbench-not-session.md)）。V0.6 **只加领域投递字段**，Workbench 仍不 import ERP、不解析语言。

| 领域字段 | 含义 |
| --- | --- |
| 每张已确认任务的 `posting` | 这张 Runtime 单在账上了没有 |
| 可选：当前绑定客户的 `open_draft_count` | 未过账 Draft SO 张数；整数，无单据列表 |

禁止：在工作台渲染 ERP 表单、科目、库存列、收款状态。

ADR-012 原文「Workbench 不负责 ERP」修正为：不负责写 ERP、不认识 DocType；**可以展示 Read Adapter 给的领域投递状态**。

### 4.3 禁止进入任何 Context

- `item_code`、`doctype`、`warehouse`、`naming_series`、`cost_center`、`debit_to`
- 库存数量、预留、可用量
- 单价表、折扣规则、税则
- 应收账款、已收、账期
- ERP 客户名（用 Runtime `display_name`）
- SpeechAct、`user_text`、ASR
- Memory / Evidence / `product_default`

### 4.4 口播 / ReplyPlan

V0.6 **不**把 `EnterpriseFacts` 送进 `collect_notices`，**不**新增 notice code，**不**改 `reply_text`。

老板听见的仍是「单已确认 / 价未定」。账本状态用眼睛看投影，不用耳朵听。

若下一阶段要说「这张单已经进账（草稿）」：

1. 另批；
2. 只改 `Policy.collect_notices` 增加 **notice**（不得 `session_block` / 不得改 `confirm_gate`）；
3. 仍走 ADR-007：`EnterpriseFacts → Policy.collect_notices → Issue(notice) → ReplyPlan → 模板`；
4. 库存与金额仍然禁止。

---

## 5. 如何避免 ERP 反向污染 Policy

这是 V0.6 的安全核心。Policy 是业务安全边界；账本是事实。事实不能升格为闸门。

### 5.1 硬隔离

```text
DecisionPolicy / confirm_gate
        │
        │  只读 SalesSession + BusinessContext
        │  （客户歧义、SKU、空单、price_tbd notice）
        v
    confirm_ok / issues
        │
        ✕  禁止 import app.erpnext
        ✕  禁止读 EnterpriseFacts
        ✕  禁止读库存、信用、Price List
```

| 规则 | 做法 |
| --- | --- |
| 输入不变 | `confirm_gate(session)` 签名与判定条件不增加 ERP 参数 |
| Context 形状不变 | 不给 `BusinessContext` 加字段，避免「顺手」在 `collect_notices` 里读账本 |
| 失败不影响裁决 | Read 超时不得抛到 `TurnGateway.handle`；与 V0.5 Write 失败隔离同构 |
| 库存不存在 | Adapter 黑名单；测试 grep `Bin` / `warehouse` / `actual_qty` 不得出现在 Runtime |
| 不改订单 | Read Adapter 无 `PUT`/`POST`/`submit`；不能改 Runtime 行、不能改 ERP 行 |
| 不反向建 SKU | 读不到 Item 映射时 `unavailable`，禁止 Resolver 去 ERP 找替身 |
| 不覆盖客户 | 禁止用 ERP 同名客户替换 `CustomerRef.id` |

### 5.2 污染测试（设计；实现时再写）

- 确认李老板苹果 TBD：`confirm_ok` 与现网字节级一致；即使 Fake 读返回 `unavailable` 或 `posted`。
- 库存夹具：Read Adapter 即使内存里有 qty，端口也不得暴露；Policy 测例不出现库存字段。
- grep：`app/agent` `app/policy` `app/memory` `app/services/order_service.py` `app/services/product_resolver.py` 不得出现 `item_code` / `frappe` / `doctype` / `warehouse`。
- `BusinessContext.model_fields` 仍是 `customer_id` / `profile_defaults` / `price_facts`。
- `query_draft` 口播不含 ERP SO 名。

### 5.3 「员工读取」≠「员工听从」

读取：知道公司账上这张确认单是否已成 Draft SO。

听从（禁止）：库存 0 就拒绝确认；ERP 有同名客户就换人；Price List 自动填价；未过账就改口说「还不能好了」。

---

## 6. 与 V0.5 Write / Outbox 的关系

```text
事务 A：草稿 confirmed + Outbox 提交     （已有）
事务 B：Write Adapter 建 Draft SO + mark （已有）
读路径：装配层 GET 领域事实              （V0.6，无新事务语义）
```

读不得插入事务 A。读不得 `processed_events.mark`。读不得为了「读到最新」去触发 Write。

若 Read 见到 `pending`：那是 Write 还在重试，**正确**。禁止 Read 为了消除 pending 去调用 `ensure_sales_order`（那是写，且会绕过 Outbox）。

---

## 7. 失败域

| 失败 | Read Adapter | Runtime |
| --- | --- | --- |
| ERP 5xx / 超时 | `posting=unavailable` | 确认结果、口播、HTTP 200 不变 |
| 无 correlation | 未确认 → 空；已确认 → `pending` | 不变 |
| 真站未配 `ERPNEXT_URL` | Fake 内存读 | CI 默认 |
| 自定义字段缺失 | `unavailable` | 不在 Runtime 补字段 |

老板听的仍是 Runtime `reply_text`。ERP 读失败 **不得**改口播、不得让 LLM 解释账套。

---

## 8. 明确禁止

- ERPNext SQL / DocType / REST 进入 Parser、Policy、OrderService、Memory、Resolver
- 修改确认逻辑 / `confirm_gate`
- 库存自动决策、预留、出库
- 自动改订单（Runtime 行或 ERP 行）
- ERP 驱动 AI 裁决（信用、科目、定价单、可用量）
- 把 `query_draft` 改成查 ERP
- 新增 SpeechAct / 改 Prompt 以「查账」
- 把跨单 ERP 列表写入 `SalesSession`
- Response 绕过 Policy 朗读账本
- 以 ERP Item 反向同步 Catalog
- submit、发票、收款、总账

---

## 9. 设计批准后的落地顺序

仍不在本文件写代码：

```text
1. EnterpriseFacts 形状 + Fake 读（只读 V0.5 内存 SO）
2. EnterpriseFactPort：posting_for(order_id)；装配层挂到 Session/Workbench 投影
3. 契约测试：确认结局不变；posted/pending/unavailable；冻结文件 grep
4. 显式 ERPNEXT_URL 才 GET 真站；默认 CI 不连
5. （另批）若要口播账本：只加 notice，不改 confirm_gate，不改 Parser
```

任一步需要改冻结内核才能「让员工听库存/改价」→ **停**，回本设计。
