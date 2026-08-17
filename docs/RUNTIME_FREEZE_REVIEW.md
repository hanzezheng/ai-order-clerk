# AI Employee Runtime v0.x 架构冻结评审

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)。
> 本阶段只允许修改：**架构评审文档**。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory。
>
> **不写代码，不新增功能。** 决策见 [ADR-024](ADR/ADR-024-runtime-freeze-not-framework.md)。

当前版本：AI Employee Runtime + ERPNext Boundary（Write 已落地；Read 仅设计）。

结论先写：

1. 现网已经形成 **可复用的员工流水线**，还不是可复用的 **Employee Runtime 产品**。
2. 流水线本身（语言 → 理解 → 裁决 → 执行 → 事件 → 适配器）值得冻结。
3. 类型与模块名大多仍是 **Sales Agent 专属**。现在抽象平台会抽错。
4. **不要**用 LangGraph / CrewAI / AutoGen / OpenAI Agents SDK 替换现网 Runtime。
5. 下一阶段优先 **完成已设计的 ERP 读写边界**，而不是增强 ERP 业务，也不是做多 Agent。

---

## 1. 当前架构分层

现网固定流水线（与架构文一致，按评审八层重排）：

```text
Input Layer
    → Language Layer
    → Understanding Layer
    → Decision Layer
    → Execution Layer
        → Event Layer ──→ Memory Layer
                       └─→ Enterprise Adapter Layer（Write）
装配层 Domain Query ──→ Enterprise Adapter Layer（Read）
```

Response（`ReplyPlan` → 模板 → Grounder）是 **表达层**，挂在 Decision 之后，不是第九个业务层。Workbench 是 **当天任务索引**，横切于 Session，不进入裁决链。

### 1.1 Input Layer

| | |
| --- | --- |
| 职责 | 把老板的声音或文本变成 Runtime 已有的 turns 契约；把同一句 `reply_text` 播出 |
| 输入 | 音频 / textarea；PTT 结束词；`utterance_id` / `seq` / `is_final` / `expect_more` |
| 输出 | `POST /v1/sessions/{id}/turns` 的 `text` + 控制字段；TTS 只念后端 `reply_text` |
| 禁止依赖 | Parser 内部、Catalog、Policy、OrderService、ERP、Memory |

现网：`app/voice/`、Turn Intake、HTTP turns。Partial 不得进业务。

### 1.2 Language Layer

| | |
| --- | --- |
| 职责 | 理解自然语言，抽取有序 `SpeechAct[]` |
| 输入 | 一句 `text`（final） |
| 输出 | `TurnParse`（acts、parser_name、fallback） |
| 禁止依赖 | Resolver、Policy、OrderService、数据库、ERP、Memory 写入 |

现网：规则 Parser + `LLMTurnParser`（parser.v6 / Qwen）为默认入口。LLM **只**理解语言。无配置时规则兜底，行为与 v0.2 对齐。

### 1.3 Understanding Layer

| | |
| --- | --- |
| 职责 | 把行业货语变成可查询形状，并在 **已有 Catalog** 上识别实体 |
| 输入 | `SpeechAct` 槽位；Session 的 focus / 已绑定客户 |
| 输出 | `ProductQuery` / `ProductMention`；已识别的客户引用、SKU 或挂起的层级节点 |
| 禁止依赖 | 创建 SKU、猜唯一解、写 Memory、读 ERP Item、改 `confirm_ok` |

现网两段、不可对调：

1. ProductUnderstanding：八零果等货语 → 属性，**不**输出 SKU。
2. Resolver：按已有本体识别；**不**猜、**不**建节点。

### 1.4 Decision Layer

| | |
| --- | --- |
| 职责 | 业务安全边界：问不问、能不能自动执行、能不能确认、notice 还是阻断 |
| 输入 | `SalesSession` + `BusinessContext`（本单档案默认与价格记忆事实） |
| 输出 | `DecisionVerdict`（`allow_execute` / `confirm_ok` / issues / `reply_mode`） |
| 禁止依赖 | LLM、ERP、库存、信用、Price List、直接改订单行价、直接写 Memory |

现网：`DecisionPolicy` + Confirm Gate；MemoryPolicy 是记忆写入闸门，同属裁决，不属执行。`price_tbd` 只做 notice，不挡确认。

### 1.5 Execution Layer

| | |
| --- | --- |
| 职责 | 按已通过的裁决执行开单、改口合行、确认草稿 |
| 输入 | 已允许的结构化命令 + Session |
| 输出 | 变更后的 `DraftOrder`；发布领域事件 |
| 禁止依赖 | ERP API、SQL、Parser、绕过 Confirm Gate 的第二条确认路径 |

现网：`OrderService`。确认与 Outbox 同行提交（事务 A）。禁止 `OrderService.confirm` 里调 ERP。

### 1.6 Memory Layer

| | |
| --- | --- |
| 职责 | 从 **确认后的结构化事件** 学习稳定习惯，不是聊天 |
| 输入 | Outbox 中的 `order.confirmed` 等；Extractor 建议 |
| 输出 | Alias / `product_default` / 带过期的价格记忆（经 MemoryPolicy） |
| 禁止依赖 | `user_text`、LLM 直写、ERP 客户组、未确认草稿 |

路径：`Extract → MemoryPolicy → Storage`。与 Confirm Gate 分离。

### 1.7 Event Layer

| | |
| --- | --- |
| 职责 | 把已发生的领域事实变成可靠信封；按 consumer 投递 |
| 输入 | Execution 发布的 `DomainEvent` |
| 输出 | Outbox 行；`processed_events(consumer, event_id)` |
| 禁止依赖 | 在 outbox 行上写总开关「已消费」；让投递失败回滚已确认 Session |

现网消费者：`memory_extractor`、`timeline`、`erpnext_adapter`。写路径最终一致；读路径 **不是** 第二套 Outbox。

### 1.8 Enterprise Adapter Layer

| | |
| --- | --- |
| 职责 | ERPNext 防腐：写公司账、读领域事实投影 |
| 输入 | Write：`order.confirmed` + 已确认 Session 快照。Read：`runtime_order_id` / `runtime_customer_id` |
| 输出 | Write：Draft Sales Order。Read：`pending \| posted \| unavailable`（设计） |
| 禁止依赖 | Parser / Policy / OrderService / Memory；submit；库存；收款；DocType 泄漏进 Runtime |

Write 已落地。Read 仅设计。两边都在 Runtime **之外**。

### 1.9 层间依赖（冻结）

```text
允许：Input → Language → Understanding → Decision → Execution → Event
允许：Event → Memory
允许：Event → Write Adapter
允许：装配层 → Read Adapter → 投影（不进 Decision）

禁止：Language → DB / ERP
禁止：Decision ← ERP / 库存 / LLM
禁止：Execution → ERP API
禁止：Memory ← user_text
禁止：Adapter → 回写 Catalog / OrderLine / confirm_ok
```

---

## 2. 哪些部分属于通用 Runtime

判断标准：换一个员工（采购 / 财务 / 仓）时，**类型能留下** 还是只 **角色能留下**。

### 2.1 可复用的是「角色与契约」，不是现成类名

| 能力 | 复用到 Sales / Purchase / Finance / Warehouse | 说明 |
| --- | --- | --- |
| Input（turns 契约、Voice） | 是 | 换 text 来源，不换业务 |
| SpeechAct **信封**（type + slots + 多 act） | 是 | 具体 type 闭包是销售的 |
| Parser「只理解语言」 | 是 | Prompt / schema 按员工换 |
| Resolver「只识别已有目录」 | 是 | 目录内容按行业换 |
| Policy「LLM 不能替代」 | 是 | **闸门表**按员工换 |
| Session = **一张任务** | 是 | 现网实现是 `SalesSession` |
| `session_type` 字段 | 预留 | 已有 `"sales_order"`，尚无第二种实现 |
| Memory：Extract → Policy → Storage | 是 | 记忆 **种类** 按员工换 |
| Event + Durable Outbox + 按 consumer 投递 | 是 | 事件名按限界上下文换 |
| Workbench = 当天任务索引 | 是 | 现网卡片字段是销售的 |
| Persistence Port + UoW | 是 | |
| Adapter：写走 Outbox、读走领域端口 | 是 | 文档类型按员工换 |
| Response：verdict → plan → 模板 → Grounder | 是 | 虚词表按员工换 |

这些构成 **AI Employee 基础流水线**。第二个员工应 **复制这条链**，而不是继承 `OrderService`。

### 2.2 Sales Agent 专属（不要当成 Runtime）

| 专属 | 为什么不能直接给采购/财务/仓 |
| --- | --- |
| `SpeechActType` 闭包（`add_line` / `confirm_order` / `query_draft`…） | 采购不是加销售行 |
| `DraftOrder` / `OrderLine` / 合行改口 | 销售草稿语义 |
| `DecisionPolicy.confirm_gate`（空单、未绑客户、未落 SKU、`qty_first_price_optional`） | 财务确认 ≠ 开单确认 |
| 农批 Product Ontology + ProductUnderstanding | 仓/财务没有「八零果」 |
| Customer Profile / 档口消歧 / 冷启动 | 销售客户；供应商是另一张档案 |
| Price Memory（`last_deal` / `market_today`） | 付款与库存不是这套价 |
| Memory 种类 `product_default` | 销售习惯 |
| `OrderService` | 销售执行器 |
| ERP Write：Customer / Item / **Draft Sales Order** | 采购是 PO；仓是 Stock；财务是 Payment/GL |
| `order.confirmed` 作为唯一公司销售事实 | 仓订阅它，但不得在 SalesSession 里扣库存 |
| parser.v6 农批 prompt / 金脚本 G1–G4 | 语言评测绑在开单员 |
| WorkbenchTaskRef 的 `prices_incomplete` | 销售 TBD 价 |

`SalesSessionRunner` 名字已经说明：它是开单员，不是 Employee Runtime 内核类。

### 2.3 四个未来员工如何接（只评复用，不实施）

| 员工 | 共享 | 必须新开 |
| --- | --- | --- |
| Sales Agent | 现网整条链 | —（已是当前员工） |
| Purchase Agent | Input、Outbox、Port、Workbench 角色、SpeechAct 信封 | `PurchaseSession`、采购闸门、PO Adapter、供应商目录 |
| Finance Agent | 同上 | `PaymentSession`；**确认开单 ≠ 已收款**；禁止读 GL 指挥销售闸门 |
| Warehouse Agent | 订阅 `order.confirmed` | `InventorySession`；SalesSession **内**不扣库存 |

---

## 3. 下一阶段战略选择

### A. 继续增强 Sales Agent

在冻结流水线上把开单员做完整：语音更稳、确认契约不漂、ERP 边界按已批设计收口。

| | |
| --- | --- |
| 收益 | 唯一真实员工继续产生可测行为；流水线被真实对话压实；抽象有样本 |
| 风险 | 把采购/库存需求塞进 `SalesSession`；SpeechAct 继续膨胀；Runner 更难拆 |
| 优先级 | **高**，但只允许「加固流水线 / 收口已设计边界」，不允许「销售里做仓和财务」 |

### B. 抽象 Employee Runtime

把 Session / Policy / Memory / Runner 抽成框架，Sales 变成插件。

| | |
| --- | --- |
| 收益 | 表面上接近阶段 3 平台 |
| 风险 | **现在抽会抽错。** 可复用的是角色，可复制的代码几乎都带着销售类型。平台化会迫使改 Parser 闭包、Policy 输入、`BusinessContext` 字段，正好打在冻结层上 |
| 优先级 | **低。** 第二个员工立项之前不做 |

### C. 深入 ERPNext 业务能力

submit SO、库存、发票、收款、科目、定价单。

| | |
| --- | --- |
| 收益 | 账更像「真 ERP」 |
| 风险 | **ERP 驱动 AI。** 库存挡确认、Price List 改价、信用挡「好了」，Runtime 变成 ERP 插件。与架构文、ADR-022/023 直接冲突 |
| 优先级 | **不做。** 库存/支付/财务是独立 Adapter + 独立 Session，且须另批 |

### 选择

**有约束的 A，外加把 V0.6 Read 按设计落地（仍属 ERP Boundary，不是 C）。**

不做 B。不做 C。不把 A 理解成「开单员功能清单继续加长」。

---

## 4. 是否需要引入通用 Agent Framework

评估对象：LangGraph、CrewAI、AutoGen、OpenAI Agents SDK。

**不应该替换当前 Runtime。**

| 框架 | 控制权在哪 | 与现网冲突 |
| --- | --- | --- |
| LangGraph | 图节点 + 可让 LLM 选边 | DESIGN 已禁止用 LangGraph 重写开单内核；澄清处短路会破坏连报 |
| CrewAI | 多角色对话协作 | 现网禁止多 Agent；Policy 不是「再请一个专家模型」 |
| AutoGen | Agent 互相对话 | Session 会变成 IM；Memory 会变成聊天记录 |
| OpenAI Agents SDK | LLM + tool loop | 工具循环把「是否确认 / 是否查库」交给模型，等于 LLM 调业务库 |

现网倒置了这些框架的默认假设：

```text
现网：  LLM 只出 SpeechAct → Policy 裁决 → Service 执行 → Event
框架：  LLM 选工具 / 选下一 Agent → 副作用发生 → 事后解释
```

替换代价：

- Confirm Gate 无法单测成确定性表
- ERP / SQL 会变成 tool
- 第二个员工会先长出聊天室，而不是任务 Session

允许的用法（若将来出现）：**只**作为 Language Layer 的可选运行时（等价于今天的 LLM HTTP 客户端），**不得**拥有 Policy、Memory 写入、ERP tool。即便如此，也不是本阶段，且不得替换 `SalesSessionRunner`。

---

## 5. 未来多 Agent 架构

架构文：**当前不是做多 Agent。** 下面只冻结「若将来要做，必须怎么拆」，避免到时把三人塞进一张销售图。

```text
老板
  → Input + Workbench（按任务类型开 Session）
       ├─ Sales Agent      → SalesSession      → order.*     → Sales Order Adapter
       ├─ Purchase Agent   → PurchaseSession   → purchase.*  → PO Adapter
       └─ Finance Agent    → PaymentSession    → payment.*   → Payment Adapter
                    │
                    v
              共享 Event Bus（Outbox，按 consumer 隔离）
                    │
                    v
                 ERPNext（事实系统，不是聊天框）
```

### 5.1 共享

| 共享 | 共享到什么程度 |
| --- | --- |
| Input / turns / Voice | 同一入口契约 |
| SpeechAct **信封** | 同一结构；**type 按员工分文件**，禁止一个超大 Literal |
| Parser 角色 | 每员工自己的 schema / 兜底 |
| Resolver 角色 | 每员工自己的目录（商品 / 供应商 / 科目禁止混成一张 Catalog） |
| Policy 角色 | 每员工一张闸门表；**不共享 `confirm_gate` 函数** |
| Memory 机制 | Extract → 审核 → 存储；**存储分区按员工/客户/供应商**，禁止财务记忆改销售默认 SKU |
| Event / Outbox | 同一套信封与 pending/mark；consumer 名按员工与 Adapter 分开 |
| Workbench | 同一「当天任务」壳；任务带 `session_type` |
| ERP Adapter **层** | 同一防腐规则（领域端口、禁止 DocType 进 Runtime）；**实现按单据拆**，不是一个万能 `ErpGateway` |

### 5.2 隔离

| 必须隔离 | 原因 |
| --- | --- |
| Session 类型 | 销售确认不得扣库存、不得收款 |
| Confirm Gate | 闸门语义不同 |
| Domain Service | `OrderService` 不能执行 PO / Payment |
| Catalog / Ontology | ERP Item 不是口语索引；科目不是 SKU |
| Memory 内容 | 采购习惯不是销售 `product_default` |
| ERP 文档 | SO / PO / Payment / Stock Entry 分 Adapter |
| 读模型 | Finance 不得把应收账款送进 Sales `confirm_gate` |
| LLM 上下文 | 禁止把三个员工的话塞进同一 Prompt 让模型分工 |

### 5.3 连接方式

员工之间 **只经 Event**，不经共享可变 Session。

```text
Sales 确认 → order.confirmed → Warehouse Adapter（另批，不在 SalesSession 扣）
Sales 确认 → order.confirmed → 不自动产生 Payment
Finance 收款 → payment.received → 只更新付款任务，不改已确认销售闸门
```

禁止：一个 Orchestrator Agent 调用另外三个；禁止 LangGraph 总图。

---

## 6. 当前最大技术债（只列架构风险）

不是功能缺口（缺库存、缺收款、Read 未实现当「还没做的功能」不在此列）。下列是 **现在的形状已经会把后续做歪** 的风险。

1. **流水线可复用，类型不可复用，但命名像已经平台化。** `SalesSessionRunner`、`OrderService`、`order.confirmed` 占据「Runtime」位置。后续采购会倾向于改这些类，而不是新开 Session。
2. **`session_type` 预留但无第二种实现。** 假通用：改字段当多态，比新开 `PurchaseSession` 更便宜，也更错。
3. **SpeechAct 闭包钉死在销售 type。** 第二个员工必然碰到 Parser；若图省事往 Literal 里加 `create_po`，语言层会变成全能 ERP 命令集。
4. **`SalesSessionRunner` 是装配上帝对象。** 分层在文档里，在进程里是一个构造函数注入整条链。没有进口岸防火墙，ERP / SQL 的「顺便一调」没有编译期阻力。
5. **Decision 的输入形状被销售钉死。** `BusinessContext` 只有档案默认与价格事实；测试钉死字段。这是正确的销售隔离，也意味着「员工读账」不能从 Policy 口播，除非另批 notice——Read 设计与冻结 Policy 之间已经拉紧。
6. **Write 已落地、Read 仅设计，边界不对称。** 不是缺功能，而是确认与账本最终一致 **不可从 Runtime 侧观察**。装配层会用「再调一次 Write / 直接 GET DocType」来补可见性，正好打穿 Adapter。
7. **ERP correlation 在进程内 Map。** Write 幂等依赖 Fake/单进程；跨进程 Postgres 世界里 Adapter 私有对照与 Outbox 不在同一持久化边界，Kill & Restart 后容易出现第二条「补写」路径。
8. **双目录（Runtime Ontology vs ERP Item）只有单向写。** 没有 Read 纪律时，Resolver 会被要求「去 ERP 搜苹果」。这是反向污染的最大斜坡。
9. **文档漂移：架构文写 Employee Runtime，DESIGN 仍留 LangGraph 目录与「图节点」口吻。** 实施者会按文件夹，不按冻结链。
10. **ADR-021 标题仍是「只经 Outbox」，正文已加读端口。** 写/读双路径若口口相传成「ERP 都能调」，装配层与 Runner 的界限会糊。

---

## 7. 下一阶段建议（三个 Sprint）

约束：不破坏 `Parser → Resolver → Policy → Service`；不引入 ERP 驱动 AI；不引入 LLM 直连业务库。

### Sprint N+1 — 按已批设计落地 Read Adapter

只改 Enterprise Adapter + 装配投影。

- `EnterpriseFactPort`：`posting_for(order_id)`
- 投影到 Workbench / Session 侧栏，**不**进 `BusinessContext`、**不**改口播
- ERP 失败 → `unavailable`，确认结果不变
- grep：Policy / Parser / OrderService 仍无 DocType

这是收口 §6.6 的边界不对称，不是深入 ERP 业务。

### Sprint N+2 — 冻结防火墙（仍无新产品）

只改装配/测试/文档，不改闸门。

- 层进口岸测试：`app/policy` `app/agent` `app/services/order_service.py` `app/memory` 不得 import `app/erpnext`
- 明确模块清单：何为 Runtime 角色、何为 Sales 专属（本文 §2）
- 接受 ADR-024：不替换框架、不抽象平台、不 submit/库存/收款

### Sprint N+3 — 有约束的 Sales 加固，或停

二选一，禁止第三选项（开采购员工 / 上框架 / submit SO）：

- **加固：** Voice 真机与 parser.v6 Admission 回归仍走同一 turns；不新 SpeechAct；不改 Confirm Gate
- **停：** 若开单员行为未稳，冻结功能面，只修契约测试

禁止在这三个 Sprint 内：Purchase Agent、Finance Agent、Warehouse 扣库存、LangGraph 重写、Vector DB、ERP 聊天框。

---

## 评审六问

1. **哪一层？** 本文件是跨层冻结评审，不改任何运行层。
2. **改 LLM 权限？** 否。明确拒绝 tool-loop 框架。
3. **绕过 Policy？** 否。禁止 ERP / LLM 进入 Decision。
4. **污染 Memory？** 否。记忆机制可复用，内容按员工隔离。
5. **经 Event？** 写：是。读：领域查询。员工之间将来只经 Event。
6. **属于 Adapter 还是 Runtime？** ERP 仍只属 Adapter；本评审冻结的是 Runtime 流水线，不是把 Runtime 做成 ERP。
