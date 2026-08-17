# Runtime Freeze

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)。
> 本文件是 **v0.x 收口后的冻结清单**：已冻结层、允许扩展点、Adapter 边界、新员工如何复用。
>
> 不写新业务。不抽象平台。不引入新 Agent。不替换为 LangGraph / CrewAI / AutoGen / OpenAI Agents SDK。
>
> 评审背景：[RUNTIME_FREEZE_REVIEW.md](RUNTIME_FREEZE_REVIEW.md)、[ADR-024](ADR/ADR-024-runtime-freeze-not-framework.md)。

现网是可复用的 **员工流水线**，不是可复用的 Employee Runtime 产品。

```text
Input → Language → Understanding → Decision → Execution
              → Event → Memory
              → Event → Write Adapter
装配层 Domain Query → Read Adapter → 投影
```

---

## 1. 已冻结层

实现不得修改这些模块的职责、输入输出与禁止依赖。改闸门或 LLM 权限必须先改架构文 + ADR。

| 层 | 现网 | 冻结内容 |
| --- | --- | --- |
| Language | `app/agent/parser.py`、`llm_parser.py`、parser.v6 | 只出 `SpeechAct[]`；禁止选客户/SKU/定价/写 Memory/判断 Confirm；禁止访问 DB / ERP |
| Understanding | `product_understanding.py` | 货语 → 属性；禁止直接输出 SKU |
| Resolver | `product_resolver.py` | 只识别已有 Catalog；禁止猜、建 SKU、查 ERP Item |
| Decision | `policy/decision.py`（含 Confirm Gate） | 只读 Session + `BusinessContext`；禁止 LLM、ERP、库存、信用 |
| Execution | `order_service.py` | 禁止直调 Adapter / ERP API；确认不得绕过 `confirm_gate` |
| Memory | `app/memory/*` | 只从确认后结构化事件学习；禁止读 `user_text` / `raw_text` |
| Session | `SalesSession` | 一张订单；禁止聊天记录、禁止跨单字段 |

`BusinessContext` 字段钉死为 `customer_id` / `profile_defaults` / `price_facts`。ERP 事实不得加入此对象。

防火墙：`app/tests/test_architecture_firewall.py`。

---

## 2. 允许扩展点

只允许在流水线 **外侧** 或 Adapter 内收口，且不得改变冻结层输入。

| 扩展点 | 允许 | 仍禁止 |
| --- | --- | --- |
| Input Adapter | 换 ASR/TTS 实现 | 改 `reply_text` 语义、partial 进 Runner |
| Turn Intake / HTTP | 幂等字段、投影装饰 | 新自然语言入口 |
| Event / Outbox | 新 **consumer**（Adapter） | 改信封语义、让投递失败回滚确认 |
| Enterprise Write Adapter | 翻译已确认事实 | submit、库存、收款、改 `confirm_ok` |
| Enterprise Read Adapter | 领域查询 → 投影 | 结果进 Policy / Resolver / Memory |
| Workbench 投影 | 展示 `posting` | Workbench 解析语言、写 Memory |
| Persistence | 同一套 Port 的存储实现 | 业务层依赖 InMemory / ORM |
| 测试 / Fake | Fake ASR、Fake ERP | 默认 CI 连真站、连 live LLM |

禁止当作扩展点：新 SpeechAct type、新 `confirm_gate` 条件、新 Memory 从聊天学习、通用 Agent 框架、平台抽象层。

---

## 3. Adapter 边界

```text
写：order.confirmed → Outbox → Write Adapter → Draft Sales Order
读：装配层 EnterpriseFactPort → Read Adapter → pending | posted | unavailable
```

| 规则 | |
| --- | --- |
| Runtime 内核不查 ERP | Parser / Policy / OrderService / Memory / Resolver 不得 import `app.erpnext` |
| 查询键 | 只有 `runtime_order_id` / `runtime_customer_id` |
| 投影位置 | Session `enterprise` 侧栏、Workbench 任务 `posting`；**不是** `draft.lines` |
| 失败 | Write 不 mark；Read → `unavailable`；都不改确认结果 |
| 字段隔离 | `item_code` / doctype / warehouse 只存在 `app/erpnext/` |
| 口播 | V0.6 不改 `reply_text`；`query_draft` 仍念 Runtime 草稿 |

黑名单：库存、信用、Price List、Item 名搜索、Customer 模糊搜、SQL/`tab*`、submit 单据。

---

## 4. 新员工如何复用

**复制流水线，不要继承 `OrderService`。**

共享（角色）：turns 契约、SpeechAct 信封、Parser/Resolver/Policy 的权限模型、Session=一张任务、Memory 的 Extract→审核→存储、Outbox 按 consumer 投递、Adapter 防腐规则、Workbench 壳。

必须新开（类型）：`PurchaseSession` / `PaymentSession` / `InventorySession`、各自 Confirm Gate、各自目录、各自 ERP 单据 Adapter、各自 SpeechAct type 文件。

员工之间只经 Event。禁止总图、禁止三人共用 `SalesSession`、禁止财务读账指挥销售 `confirm_gate`。

当前 **不是** 做第二个员工。`session_type` 预留不得当成已实现多态。

---

## 5. 明确不做

- 新 Agent / 多 Agent 编排
- LangGraph / CrewAI / AutoGen / OpenAI Agents SDK 替换 Runtime
- 抽象 Employee Runtime 平台
- 新业务模块（采购执行、库存扣减、收款过账、submit SO）
- ERP 驱动 AI 决策
- LLM 直连业务数据库
