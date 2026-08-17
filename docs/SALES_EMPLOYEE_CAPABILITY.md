# Sales AI Employee 产品能力评审

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)、[RUNTIME_FREEZE.md](RUNTIME_FREEZE.md)。
> 本阶段只允许修改：**产品能力定义文档**。
> 禁止修改：Parser / Policy / Confirm Gate / OrderService / Memory / Runtime Freeze 边界。
>
> **不写代码，不新增功能。** 决策见 [ADR-025](ADR/ADR-025-sales-employee-before-second.md)。

当前状态：AI Employee **Runtime Foundation 已完成**。本文件把第一个商业员工从「技术流水线」收成「老板雇得动的岗位」。

第一个员工岗位名：**农批档口开单员**。不是档口经理，不是会计，不是仓管。

可雇版本规格：[V1_SALES_CLERK.md](V1_SALES_CLERK.md)。产品化用户旅程：[V1_SALES_CLERK_USER_JOURNEY.md](V1_SALES_CLERK_USER_JOURNEY.md)。工作台原型：[V1_SALES_CLERK_WORKBENCH.md](V1_SALES_CLERK_WORKBENCH.md)。垂直切片：[V1_SALES_CLERK_VERTICAL_SLICE.md](V1_SALES_CLERK_VERTICAL_SLICE.md)。Pilot：[V1_SALES_CLERK_PILOT_CHECKLIST.md](V1_SALES_CLERK_PILOT_CHECKLIST.md)。观察：[V1_SALES_CLERK_PILOT_OBSERVATION.md](V1_SALES_CLERK_PILOT_OBSERVATION.md)。数据边界：[V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md](V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md)。数据访问：[V1_SALES_CLERK_PILOT_DATA_ACCESS.md](V1_SALES_CLERK_PILOT_DATA_ACCESS.md)。接入：[V1_SALES_CLERK_PILOT_ONBOARDING.md](V1_SALES_CLERK_PILOT_ONBOARDING.md)。反馈：[V1_SALES_CLERK_PILOT_FEEDBACK_LOOP.md](V1_SALES_CLERK_PILOT_FEEDBACK_LOOP.md)。执行手册：[V1_SALES_CLERK_PILOT_RUNBOOK.md](V1_SALES_CLERK_PILOT_RUNBOOK.md)。Flutter App：[V1_SALES_CLERK_FLUTTER_APP.md](V1_SALES_CLERK_FLUTTER_APP.md)。

---

## 0. 结论

1. 现网已经能替老板完成 **「喊着开单 → 改口 → 好了 → 账上留草稿」** 这一岗。这是真老板价值，不是 Demo 功能清单。
2. 农批老板一天里，AI **现在就能承担**的只有：接订单、改未确认单、开下一单、用眼睛看今日单是否入账。查询客户/跟进/对账收款 **还不是这个员工的岗位**。
3. 下一阶段继续增强 **Sales Employee**，只做冻结允许的外侧能力（语音可靠、工作台今日本、投递可见）。不启动第二个 Employee。
4. 第二个员工的门槛：开单员这一岗被真实使用之后，才复制流水线做 **收款员（PaymentSession）**。不是采购，不是平台。

---

## 1. 当前 Sales AI Employee 已具备哪些老板价值

用老板听得懂的话说：雇了一个会开单的伙计，还不会管账、不会催款、不会看库存。

| 老板要的 | 现网能否给 | 证据 |
| --- | --- | --- |
| 连着喊、不等问完再报下一品 | **能** | 多 SpeechAct、`expect_more` 不打断追问 |
| 喊错了改口 | **能**（仅未确认） | 合行 / 改量 / 去掉；确认后 409 |
| 两个王老板不弄错 | **能** | 同名必须问档口，禁止静默选 |
| 熟客只说「苹果」也能落到常拿的货 | **能**（有档案时） | Memory `product_default`；无档案则挂起不猜 |
| 先开量、价回头再说 | **能** | `price_tbd` 可确认；口播「价未定」；不编单价 |
| 新客当场建档再开 | **能** | 冷启动：档口区分事实 → observed |
| 今天开完一张再开下一张 | **能** | Workbench 显式新任务 |
| 确认后公司账上有单 | **能** | Outbox → Draft Sales Order（未过账） |
| 这张单进账了没有 | **能看见，不能用嘴说** | Read 投影 `pending \| posted \| unavailable`；不进口播、不进闸门 |
| 收钱 / 核销 / 库存够不够 | **不能** | 冻结 + Adapter 黑名单 |

技术 Runtime（Parser、Memory、Postgres、Voice、ERP 读写）是这岗的底座，**不是**老板买的东西。老板买的是：不用填表，喊完一单，账上留底。

尚未构成雇人理由的缺口（产品，不是再加框架）：

- 真机语音在档口噪声下是否稳（Input，允许扩展）
- 今日已开哪些单，老板要一眼看见（Workbench 已有数据，产品化不足）
- 确认后不能再改；价未定确认后不能用嘴补价（Session 冻结：一单结束）
- 「李老板今天拿了啥」不能当查账口令（不新开 SpeechAct）

---

## 2. 农批老板一天，哪些环节 AI 可以承担

真实流程不是 ERP 菜单，是档口节奏。

```text
开始营业 → 接订单（反复）→ 改口
         → 偶尔问「谁是哪家」
         → 偶尔跟客 / 催欠
         → 收摊对账
```

| 环节 | 老板实际在干什么 | 现网 AI | 冻结内下一阶段 | 明确不承担 |
| --- | --- | --- | --- | --- |
| **开始营业** | 开档、看今天要开哪些客、准备纸本/旧系统 | **部分**：Workbench 当天任务列表、当前单 | 把工作台做成「今日开单本」（客户、行数、价未定、是否入账） | 开钱箱、盘货、排车 |
| **接订单** | 客到或电话连报：谁、什么货、多少 | **主责**：语音/文本 → 草稿 → 确认 | 真机 ASR/TTS 更稳；仍走现有 turns | 替客下单进商城、自动选 SKU |
| **修改订单** | 「不对改 80」「梨不要了」 | **主责（未确认）** | 保持；禁止把已确认单当聊天继续改 | 改已过账单、自动改价 |
| **查询客户** | 「哪个王老板」「他一般拿什么」 | **开单中能消歧、能套档案默认**；不能跨单问答 | Workbench/侧栏展示已绑定客户与今日单；**不**新增「查客」SpeechAct | CRM 搜索、ERP 客户名模糊搜 |
| **跟进客户** | 催货、催欠、改明天再拿 | **不能** | 不做。这是另一岗 | 电话、账期、信用挡开单 |
| **对账** | 今天开了几张、进没进账、收了没 | **部分看见**：今日任务 + `posting` | 让老板用眼睛对「开了/进草稿了」 | 收款核销、发票、总账、库存对账 |

承担原则：

- **能喊着完成、且闸门已存在的** → 开单员继续做深。
- **要新口令才能问账/问客** → 冻结 Parser，不做。
- **要钱或库存才能闭环的** → 不是开单员；另开 Session + 另开 Adapter，且现在不启动。

`query_draft`（「现在有啥」）只念 **本单 Runtime 草稿**，不是查 ERP、不是查客户历史。

---

## 3. 下一阶段应该增加什么能力

约束：不破坏 Runtime Freeze；不修改 Policy 边界；不让 ERP 驱动 AI；不引入通用 Agent Framework。

因此下一阶段 **只走冻结允许的扩展点**。

### 3.1 做（Sales 岗位变可雇）

| 能力 | 哪一层 | 老板价值 | 为什么不破冻结 |
| --- | --- | --- | --- |
| 档口真机语音更稳 | Input Adapter | 不用打字，才像伙计 | 只换 text 来源与 TTS；不改口播语义 |
| 工作台 = 今日开单本 | Workbench 投影 / Demo | 开业一眼看到今天几张单、谁、价未定、入账没 | 展示已有任务 + `posting`；不解析语言、不写 Memory |
| 入账状态可见 | Read Adapter 投影（已有） | 「好了」之后知道草稿进没进账 | 不进 Policy、不改 `reply_text` |
| 作废未过账单（可选） | Write Adapter 新 consumer 订已有 `order.cancelled` | 这单不要了，账上草稿也别留 | 不改闸门；只消费已有事件 |

### 3.2 不做（看起来像产品，实则破冻结或换岗）

| 想法 | 为什么现在不做 |
| --- | --- |
| 「李老板账上还有单吗」口令 | 新 SpeechAct；Read 进嘴巴要改 Policy notice |
| 确认后补价 / 改已确认行 | Session 已结束；会改 Confirm 后契约 |
| 库存不够不让「好了」 | ERP 驱动 AI |
| 挂账额度挡开单 | 财务驱动 Policy |
| 催款、收款、发票 | 第二个员工（PaymentSession） |
| 采购补货 | 第二个员工（PurchaseSession） |
| LangGraph / 多 Agent 总管 | Freeze 明确禁止 |

### 3.3 产品验收（下一阶段）

老板能完成：

1. 开口开一张缺价单并确认；
2. 工作台看到这张单；
3. 看到入账 `posted` 或 `pending` / `unavailable`；
4. 再开第二张给另一个客户。

不要求：嘴上念 ERP 单号、收钱、查历史成交。

---

## 4. 继续增强 Sales，还是启动第二个 Employee

**继续增强 Sales Employee。不启动第二个 Employee。**

| | 继续 Sales | 现在启动第二员工 |
| --- | --- | --- |
| 岗位是否可雇 | 开单这一刀已经闭合，差的是可用与可见 | 收款/采购/仓都还没有可雇的第一岗样本 |
| 冻结 | 只动 Input / Workbench / Adapter 外侧 | 必新开 Session、闸门、SpeechAct 文件 → 立刻碰 Freeze |
| 风险 | 把催款、查账塞进开单员 | 平台幻觉；`SalesSession` 被当成万能图 |
| 收益 | 第一个商业故事完整：喊单进账 | 过早复制流水线，抽错类型 |

第二个员工的正确形态（登记，不实施）：**收款员**，`PaymentSession`，确认开单 ≠ 已收款。复制流水线，不继承 `OrderService`。启动条件：开单员在档口被连续使用，而不是「Runtime 已经很完整」。

---

## 5. 未来三个阶段路线

这是 **产品阶段**，不是再做一个技术 Sprint 清单。服从 Freeze：阶段跨越先改文档。

### 阶段 A — 开单岗可雇

目标：农批老板肯把「接单」交给这个伙计。即 [V1_SALES_CLERK.md](V1_SALES_CLERK.md)。一天怎么用见 [V1_SALES_CLERK_USER_JOURNEY.md](V1_SALES_CLERK_USER_JOURNEY.md)。

- 真机语音走现有 turns（Input）
- 工作台就是今日开单本（投影，不新 Agent）
- 入账状态用眼睛看（Read 已有）
- 行为仍以 [VALIDATION.md](VALIDATION.md) 为准：会不会改口喊单，而不是会不会打分

不做：第二员工、submit SO、收款、库存。

### 阶段 B — 开单岗日结可见

目标：收摊时老板能对上「今天开了哪些、进草稿了没」。

- 当日已确认任务索引（Workbench 已有结构）
- `posted / pending / unavailable` 作为对账线索，不是财务核销
- 可选：`order.cancelled` → 取消 ERP 草稿（Adapter consumer）

仍不收款、不改 Policy、不让员工用嘴查 ERP。

### 阶段 C — 第二岗门槛（仅评估 / 另批）

目标：决定要不要雇「收款员」，而不是做成平台。

- 仅当阶段 A/B 的开单员已被使用
- 若启动：新 `PaymentSession` + 新闸门 + 新 Adapter；员工之间只经 Event
- 禁止：LangGraph 总管、财务读账指挥销售 `confirm_gate`、采购/仓与开单员混岗

阶段 2 路线图里的 Inventory / Payment / Purchase **全部推到本阶段之后另批**。当前 ROADMAP「阶段 2 真实业务连接」里未做的项，不得借产品评审提前开工。

---

## 评审六问

1. **哪一层？** 产品定义；实现仍只允许 Input / Workbench 投影 / Adapter 外侧。
2. **改 LLM 权限？** 否。
3. **绕过 Policy？** 否。下一阶段不改 Confirm Gate，不把 `posting` 送进 `BusinessContext`。
4. **污染 Memory？** 否。不从跟客聊天学习。
5. **经 Event？** 开单事实仍经 Outbox；日结看见走 Read 投影。
6. **属于 Adapter 还是 Runtime？** 入账可见属 Adapter 投影；接单属已冻结的 Sales Runtime。

不确定则继续只做开单员。
