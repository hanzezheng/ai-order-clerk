# V0.5 ERPNext Adapter

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)。
> 本 Sprint 只允许修改：**ERPNext Adapter**（本文件为设计；实现另 PR）。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory。
>
> 当前版本：`v0.4 Voice Adapter`。
>
> **只输出设计，不写代码。** 最高架构约束仍是架构文。产品细则见 [DESIGN.md](DESIGN.md)。决策见 [ADR-022](ADR/ADR-022-erpnext-adapter-not-runtime.md)。

路径固定：

```text
老板 → Input Adapter → Turn Intake → Parser → Understanding
     → Resolver → Policy → OrderService → Domain Event → Outbox
     → ERPNext Adapter → ERPNext
```

ERPNext 是企业业务事实系统。AI Runtime 是自然语言业务执行层。Adapter 是防腐层，不是第二套开单内核。

---

## 0. 结论

V0.5 增加一个 **Outbox Consumer**：`erpnext_adapter`。它只在 **`order.confirmed` 已经发生之后**，把 Runtime 已确认的结构化事实翻译成 ERPNext 的 Customer / Item / Sales Order。

| 真 | 假 |
| --- | --- |
| 确认在 Runtime 已经完成 | Adapter 再裁决能不能确认 |
| ERP 存公司账上的销售事实 | ERP 教 AI 选客户、选 SKU |
| Adapter 认识 `item_code` / DocType | Parser / OrderLine 认识 `item_code` |
| TBD 价随 `prices_incomplete` 进 ERP | 缺价就改 `confirm_gate` |
| 失败重试 Adapter | 回滚已确认的 SalesSession |

评审六问：

1. **哪一层？** ERPNext Adapter（Outbox 消费者）。
2. **改 LLM 权限？** 否。
3. **绕过 Policy？** 否。只消费闸门通过后的事件。
4. **污染 Memory？** 否。不订阅、不写 Memory。
5. **经 Event？** 是。`Domain Event → Outbox → Adapter`。禁止 `OrderService` 调 ERP API。
6. **属于 Adapter 而非 Runtime？** 是。所有 ERPNext 表名、字段名、REST 只存在 Adapter。

---

## 1. ERPNext Adapter 边界

### 1.1 位置

```text
                    Runtime（冻结）
OrderService.confirm
        │
        │  publish order.confirmed
        v
     Outbox（信封不改语义）
        │
        ├─ memory_extractor     已有
        ├─ timeline             已有
        └─ erpnext_adapter      V0.5 新增
                │
                │  只在 Adapter 内
                │  Customer / Item / Sales Order
                v
            ERPNext
```

Adapter 与 Voice Adapter 对称：都在 Runtime **之外**。Voice 换 text 来源；ERPNext 换「确认后事实写到哪套账」。

禁止新增 HTTP「给 ERP 用」的自然语言入口。自然语言仍只进 `POST /v1/sessions/{id}/turns`。

### 1.2 允许看见

- Outbox 信封：`event_id` / `event_type` / `aggregate_id`（`order_id`）/ `session_id` / `payload`
- 装配层已经给 Memory 的同一份 **已确认 `SalesSession` 快照**（Dispatcher 按 `session_id` 加载）
- 领域形状的只读字段：客户 id / 名 / 档口；行 `product_sku_id`、qty、uom、`price.source`、`unit_price`、`prices_incomplete`

### 1.3 禁止看见 / 禁止做

| 禁止 | 原因 |
| --- | --- |
| import ERPNext / Frappe 进 `app/agent` `app/policy` `app/services/order_service` `app/memory` | 表结构污染 |
| `OrderService.confirm` 里 `requests.post(ERP)` | 错误路径 |
| 读 ERP 库存来决定 `confirm_ok` | ERP 驱动 AI |
| 改 `confirm_gate`、缺价改阻断 | 冻结 Policy |
| 创建 Runtime SKU / 改 Ontology | 冻结 Resolver |
| 把 ERP 客户主数据写回 Memory | 污染 Memory |
| `Sales Order.submit`、Delivery Note、Stock Entry、Sales Invoice、Payment Entry、GL | 库存/支付/财务 |
| 把草稿行（未确认）推到 ERP | 只有确认是公司事实 |
| 在 ERP 页面做聊天框反向开单 | 架构禁止 |

### 1.4 模块边界（落地时，本文件不写代码）

建议包：`app/erpnext/`（或 `app/adapters/erpnext/`），**禁止**被 Parser / Policy / OrderService import。

| 模块 | 职责 |
| --- | --- |
| `ErpnextConsumer` | Outbox consumer 名 `erpnext_adapter`；只处理 `order.confirmed`（V0.5） |
| `ErpGateway` | HTTP/RPC；超时、重试；不知道 SpeechAct |
| `CustomerMapper` / `ItemMapper` / `SalesOrderMapper` | Runtime 实体 → ERP 文档 |
| `CorrelationStore` | `runtime_id ↔ erp_name`，只存在 Adapter |
| `FakeErpGateway` | CI；断言调用形状，不连真站 |

现有 `OutboxRepository.list_pending(consumer)` / `processed_events(consumer, event_id)` **复用**。不改 Outbox 表语义，不在 outbox 行上写总开关「已消费」。

### 1.5 失败域

Runtime 确认与 ERP 投递 **不是同一事务**（与 Memory 的事务 B 相同模式）：

```text
事务 A（已有）：草稿 confirmed + Outbox 同行提交
事务 B（Adapter）：调 ERP + processed_events.mark 同行提交
```

| 失败 | Adapter | Runtime |
| --- | --- | --- |
| ERP 5xx / 超时 | 不 mark；下次 drain 重试 | 单仍是 confirmed |
| 缺 Item 映射 | 不 mark；记 Adapter 错误；**不**在 Runtime 建 SKU | 单仍 confirmed |
| 重复 drain | 凭 `event_id` 与 correlation 幂等 | 不变 |
| ERP 创建了 SO 但 mark 前崩溃 | 重试时按 `order_id` 发现已有 SO，跳过创建 | 不变 |

老板听的仍是 Runtime `reply_text`（「单已确认 / 价未定」）。ERP 失败 **不得**改口播、不得让 LLM 解释账套。

---

## 2. Outbox 到 ERPNext 的映射

### 2.1 现网信封（不改）

`order.confirmed` 现网 payload：

```text
prices_incomplete: bool   # 任一行 price.source == tbd
line_count: int
```

`aggregate_id` = Runtime `order_id`。Dispatcher 另带 `session_id`。

V0.5 **不扩大** OrderService 的 payload（冻结 Domain Service）。行、客户、SKU、单价从 **已确认 Session 快照** 读取，与 MemoryConsumer 同一来源。Adapter 不得为了「payload 不够」去改 `confirm()`。

### 2.2 消费哪些事件

| 事件 | V0.5 | 说明 |
| --- | --- | --- |
| `order.confirmed` | **要** | 唯一写 Sales Order 的触发 |
| `order.started` / `line_upserted` / `line_removed` | 不要 | 草稿不是公司事实 |
| `order.cancelled` | 不要（登记） | 若以后做：Adapter 取消 ERP 草稿 SO；不改 Runtime 闸门 |
| `order.price_filled` | 不要（登记） | 确认后补价再补 ERP 金额；本阶段不做 |
| `memory.preference_adjusted` | **禁止** | Memory 专用 |
| `customer_ambiguous` | **禁止** | 未确认，无 ERP 客户 |

### 2.3 一次确认的翻译步骤

```text
order.confirmed
  → 加载已确认 SalesSession
  → 断言 draft.status == confirmed（否则 skip + mark，防脏事件）
  → ensure Customer（映射表或 upsert ERP Customer）
  → 对每一行 ensure Item（仅 product_sku_id 对应的叶 SKU）
  → ensure Sales Order（一单一张；Draft，不 submit）
  → 写入 correlation
  → processed_events.mark(erpnext_adapter, event_id)
```

顺序固定。缺客户映射不得先造 SO。缺某一行 Item 不得部分造 SO（整单重试）。

### 2.4 幂等键

| ERP 文档 | 幂等 |
| --- | --- |
| Customer | `runtime_customer_id` |
| Item | `runtime_sku_id` |
| Sales Order | `runtime_order_id`（= `aggregate_id`） |

禁止用老板原话、`utterance_id`、Timeline 当 ERP 键。

### 2.5 不映射的东西

- SpeechAct、`user_text`、ASR、`reply_text`
- Ontology 非 sku 节点（variety / cultivar）作为 Item
- `product_default` / Evidence / last_deal（那是 Memory）
- Workbench 班次
- 库存仓、科目、税则、收款账户

---

## 3. Customer / Item / Sales Order 映射策略

ERPNext 字段名只出现在本节与 Adapter 实现里。Runtime entity **不增加**这些字段。

### 3.1 Customer

Runtime 事实：`CustomerRef.id` + `CustomerRecord`（`display_name`、`stall_no`、`phones`、`status`）。

Policy 已保证：能确认则客户唯一且已绑定。Adapter 不再消歧。

| Runtime | Adapter 写入 ERP | 不写 |
| --- | --- | --- |
| `display_name` | Customer `customer_name` |  |
| `stall_no` | **自定义字段**（仅 ERP）如档口 | 不写进 Runtime 新列 |
| `phones` | 可选 `mobile_no` | 不登录、不验证码 |
| `status=observed` | 仍可建 Customer（冷启动已确认） | 不把 ERP 的 customer_group 写回档案 |

策略：

1. Correlation 已有 → 复用 `erp_customer`（ERPNext `name`）。
2. 无映射 → **upsert** 一个 Customer（Customer Type = Company 或 Individual，由 Adapter 配置，不进 Policy）。
3. 禁止用 ERP 模糊搜索「谁更像王老板」覆盖 Runtime 已绑定的 id。
4. 禁止因 ERP 里已有同名客户就改 Runtime 客户。

同名王强 / 王记：Runtime 已在确认前拆开。ERP 侧用 `stall_no` 自定义字段区分；不要合并成一个 Customer。

### 3.2 Item

Runtime 事实：只有 **`product_sku_id` 指向的叶节点** 可进 ERP。Confirm Gate 已拒绝无 SKU 行。

```text
category / variety / cultivar     → 不建 Item
sku（红富士 80# 一级 烟台 件装） → 一个 Item
```

| Runtime SKU 节点 | Adapter 写入 ERP | 不写 |
| --- | --- | --- |
| `name` | `item_name` |  |
| `default_uom` | `stock_uom` | 不改 Runtime 单位制 |
| `id` | 只进 correlation；`item_code` 由 Adapter 生成 | `item_code` 不得写回 `ProductNode` |
| attributes（size/grade/…） | 可选 Item 描述或自定义字段 | 不在 Runtime 加 `item_group` 字段 |

策略：

1. 已有 sku 映射 → 用该 `item_code`。
2. 无映射 → Adapter **可以**按该 SKU 节点在 ERP **建 Item**（这是向 ERP 写主数据，**不是** Runtime 建 SKU）。
3. 禁止把「苹果」variety 建成 Item。
4. 禁止 ERP Item 反向同步进 Catalog / Alias / Ontology。
5. 禁止 `is_stock_item` 触发出库。V0.5 建 Item 时视为非库存销售项，或建了也不在 SO 上 `update_stock`。
6. 映射缺失且无法建 Item（权限/校验）→ 整单不 mark，人工补映射。不让 Parser「换个说法」。

紫麒麟等未落 SKU 的货：**到不了** `order.confirmed`。不是 Adapter 的事。

### 3.3 Sales Order

Runtime 事实：一张已确认 `DraftOrder`（`order_id`、客户、行、价）。

策略：

1. **一确认单 = 一张 Sales Order**。不要拆按仓、按税。
2. 状态：**Draft**（或 ERP 里未 submit）。禁止 `submit`。submit 会进总账/交期/可选扣库存。
3. 行：qty、uom、`item_code`；`explicit` 价写入 `rate`；`tbd` 行 `rate=0`（或空，以 ERP 校验能保存 Draft 为准）。
4. 整单 `prices_incomplete=true` → ERP 自定义字段标记；**不**因此删除 SO，也 **不**回 Runtime 改闸门。
5. 禁止 Delivery Note、Sales Invoice、Payment Entry、Journal Entry。
6. 禁止 `update_stock`。
7. SO `customer` 必须是 §3.1 映射结果，不是老板口头「王老板」。

老板在 Demo 里看到的仍是 Runtime 只读草稿，不是 ERP 表单。

### 3.4 金额与 TBD

现网档口：`qty_first_price_optional`，缺价可确认。这是 Runtime 产品语义，Adapter 必须服从。

| Runtime | ERP |
| --- | --- |
| `price.source=explicit` 且有 `unit_price` | SO 行 rate |
| `tbd` | rate 占位 0 + 整单 `prices_incomplete` |
| `last_deal` 只进 notice、不静默改行 | 若行上仍是 tbd，按 tbd 处理（不把 Memory 价写成 ERP 官方价） |

V0.5 不做 `order.price_filled` 补丁。补价仍只活在 Runtime，直到下一阶段单独设计。

---

## 4. 哪些业务必须留在 Runtime

这些能力 **不搬进 ERP**，也不许 ERP 回调改写：

| 能力 | 为什么留下 |
| --- | --- |
| 语音 / 文本 Intake | Input Adapter；ERP 无 turns 契约 |
| Parser → SpeechAct | 理解语言 |
| Product Understanding | 八零果等货语 |
| Resolver + Catalog 树 | 识别已有节点；ERP Item 不是口语索引 |
| Policy / Confirm Gate | 歧义、未落 SKU、空单；安全边界 |
| OrderService 草稿合行/改口 | 连报、focus、line_id |
| Memory / Evidence | 确认后学习习惯；禁止 ERP 客户组当档案 |
| Session = 一张订单 | 聊天与跨单禁止 |
| Workbench | 当天任务，不是 ERP 工作台 |
| `reply_text` / Response | 一张嘴；禁止按 ERP 单据拼口播 |
| `price_tbd` 可确认 | 产品档；不因 ERP 必填金额而改闸门 |

Runtime Catalog 仍是 **开单员工作目录**（口语、别名、档案默认）。ERP Item 是 **入账目录**。V0.5 单向：工作目录的叶 SKU → 入账 Item。反向同步、以 ERP 为 Catalog 真相，都不是本阶段。

---

## 5. 哪些事实交给 ERPNext

V0.5 ERP 只接收 **已经确认** 的销售事实，作为公司侧底账（Draft SO，未过账）：

| 事实 | ERP 文档 | 说明 |
| --- | --- | --- |
| 谁买 | Customer | 已消歧的 Runtime 客户 |
| 卖什么（履约 SKU） | Item | 仅叶 SKU |
| 卖多少 | Sales Order Item qty/uom | 确认数量 |
| 是否有正式单价 | rate 或 0 + `prices_incomplete` | 不编行情 |
| 哪张 Runtime 单 | correlation / 自定义字段 `runtime_order_id` | 排障 |

明确 **不** 交给 ERP（本阶段及本设计禁止项）：

- 库存数量、预留、出库
- 收款、核销、账期、总账
- 税务申报
- 未确认的连报过程
- 口语原文、ASR
- 档案默认、Evidence 计数

阶段 2 后续（**另批**，不在 V0.5）：Inventory 订阅 `order.confirmed` 但仍不在 SalesSession 里扣库存；Payment 独立会话。那些仍是独立 Adapter，不是把逻辑塞回 OrderService。

---

## 6. 如何避免 ERPNext 表结构污染 Runtime

### 6.1 名字隔离

| 允许出现的位置 | 禁止出现的位置 |
| --- | --- |
| `app/erpnext/**` | `app/agent` `app/policy` `app/services/order_service.py` `app/memory` `app/entity/order.py` `app/entity/catalog.py` `SpeechAct` |
| Adapter 测试 | Prompt、parser schema |
| 本设计文档 Adapter 节 | Runtime API JSON（turns / session draft） |

禁止向 `OrderLine`、`CustomerRef`、`ProductNode`、`TurnIn` 增加：`item_code`、`doctype`、`frappe`、`naming_series`、`debit_to`、`warehouse`、`cost_center`。

Session 只读投影继续是客户名、行 label、qty、价未定。不展示 ERP `name`。

### 6.2 相关表只住 Adapter

```text
erp_customer_map  (runtime_customer_id → erp_customer_name)
erp_item_map      (runtime_sku_id → item_code)
erp_order_map     (runtime_order_id → sales_order_name)
```

不要把这些列加到 `customer_profiles` / `product_nodes` / `order_lines`。Kill & Restart 后 Adapter 靠自己的表 + Outbox pending 恢复投递，不靠重放 Memory。

### 6.3 读模型方向

```text
✅ Adapter 读 Runtime 领域快照，写出 ERP 文档
❌ Runtime 读 tabCustomer / tabItem 做 Resolver
❌ Policy 问 ERP「有没有库存」
❌ Parser 输出 item_code
```

CI 默认 `FakeErpGateway`。真站点只在显式配置（如 `ERPNEXT_URL`）下出现，与 LLM live 一样不进默认 pytest。

### 6.4 契约测试（设计；实现时再写）

- 确认李老板苹果 TBD：Runtime `confirm_ok` 与现网一致；Fake ERP 收到一张 Draft SO、`prices_incomplete`、无 submit、无 stock。
- G1 确认后：SO 客户不是王强；行 Item 对应 FUJI80 与金边 SKU，不是「苹果」节点。
- 重复 drain 同一 `event_id`：SO 仍一张。
- Adapter 抛错：Session 仍 confirmed；Memory 仍按原规则学习。
- grep 守卫：`app/agent` `app/policy` `app/memory` `app/services/order_service.py` 不得出现 `item_code` / `frappe` / `erpnext`。

---

## 7. 明确禁止

- ERPNext API 进入业务层（OrderService / Policy / Parser / Memory）
- 修改确认逻辑 / `confirm_gate`
- ERP 驱动 AI 决策（库存、信用、科目、定价单）
- 库存扣减、预留、出库
- 支付、核销、发票过账
- 财务：GL、Journal、税费作为 Runtime 裁决输入
- 自动建 Runtime SKU、Ontology 学习、Vector DB
- 多 Agent、LangGraph 开单图、ERP 聊天框
- 为迁就 ERP 必填金额而禁止 TBD 确认

---

## 8. 设计批准后的落地顺序

仍不在本文件写代码：

```text
1. FakeErpGateway + CorrelationStore（内存）
2. ErpnextConsumer 挂上 Dispatcher（只订 order.confirmed）
3. Customer / Item / Sales Order mapper 单测（领域快照 → 调用形状）
4. 与现网 G2 确认剧本的契约测试（Runtime 结局不变）
5. 显式配置才连真 ERPNext；默认 CI 不连
```

任一步需要改冻结内核才能「ERP 过账」→ **停**，回本设计，不改闸门。
