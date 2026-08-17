# 农批 AI 销售开单员 V1 — Pilot 数据边界

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)、[RUNTIME_FREEZE.md](RUNTIME_FREEZE.md)。
> 本阶段只允许修改：**Pilot 企业数据边界文档**（及必要交叉引用）。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory / Runtime Freeze 边界。
>
> **不是开发 CRM。不是开发客户管理。不是扩展 ERP。不加功能。不新增 Agent。不引入库存 / 支付 / 财务。不改 Runtime / Confirm Gate。**
>
> 进摊条件见 [V1_SALES_CLERK_PILOT_CHECKLIST.md](V1_SALES_CLERK_PILOT_CHECKLIST.md)。观察表见 [V1_SALES_CLERK_PILOT_OBSERVATION.md](V1_SALES_CLERK_PILOT_OBSERVATION.md)。访问边界见 [V1_SALES_CLERK_PILOT_DATA_ACCESS.md](V1_SALES_CLERK_PILOT_DATA_ACCESS.md)。接入见 [V1_SALES_CLERK_PILOT_ONBOARDING.md](V1_SALES_CLERK_PILOT_ONBOARDING.md)。决策见 [ADR-032](ADR/ADR-032-v1-pilot-data-boundary.md)。

检查清单回答：能不能去摊前试。观察表回答：试的时候记什么。本文回答：**摊前要准备哪些企业事实，缺了怎么办。**

企业事实由人从纸本 / 旧系统 / ERP 抄进工作目录。AI 只用，不发明。

---

## 0. 结论

Pilot 需要的不是客户管理系统，而是 **开单员能认人、认货、不猜** 的最小事实切片。

```text
企业事实（ERP / 纸本 / 老板口述，人录入）
  → Catalog 工作目录（客户实体 + 商品树 + 别名）
  → Resolver 识别
  → Policy / Confirm Gate 确认
  → confirmed event
  → Memory（只这一条路）
```

ERP（或档口账本）提供事实。Runtime 使用事实完成理解和确认。AI 不负责创造企业事实。

---

## 1. Pilot 为什么需要企业事实

开单员听懂「李老板」「八十果」，靠的不是模型聪明，是目录里已经有人、有货。

| 角色 | 负责 | 不负责 |
| --- | --- | --- |
| **企业事实**（ERP / 纸本） | 谁是客户、货叫什么、规格、档口/电话 | 听懂口语、决定能不能「好了」 |
| **Runtime** | 用已有事实识别、消歧、确认 | 发明客户、发明 SKU、从聊天长画像 |
| **AI / LLM** | 把这句话抽成 SpeechAct | 选客户、选 SKU、写 Memory、改主数据 |

没有企业事实时，失败主因记 **数据不足**（见观察表），不是去加 CRM、不是让模型猜一个最近的王老板。

确认仍只走现有 Confirm Gate。数据边界不改变闸门。

---

## 2. Customer 数据边界

Resolver 消歧 **最小**需要：能把称呼变成 **唯一 `customer_id`**，或明确问不出唯一时停手。

称呼（name / alias）**不是**唯一键。现网种子已证明：两个「王老板」必须靠区分事实拆开。

### 2.1 允许进入工作目录的字段

| 字段 | Pilot 用途 | 对应现网 |
| --- | --- | --- |
| **customer_id** | 唯一身份；确认、入账、Memory 都挂这个 | `CustomerRecord.id` |
| **name** | 老板怎么喊；查列表 | `display_name` / `legal_name` |
| **alias** | 老李、王记、李老板 | `aliases[]` |
| **phone** | 同名消歧、复述 | `phones[]` / `phone_tail` |
| **address** | 口述区分（东门 / 某路） | 只当区分事实；**不为此改 Runtime 加地址簿** |
| **tags** | 档口号、摊位等消歧标签 | 必须能投影出 `stall_no`（或等价档口事实） |

`tags` 不是营销标签、信用分、客户画像。Pilot 里 tags 只承载 **认人** 需要的档口/摊位标记。

### 2.2 Resolver 消歧最小集合

对每一个会喊到的客户，上线前必须有：

1. **customer_id**
2. **至少一个可查找的称呼**（name 或 alias）
3. **至少一项区分事实**（phone **或** address **或** tags 里的档口号）

同名组：每一家都要有互不相同的区分事实。缺一项 → 现场必须问老板，禁止静默选最近一个。

`last_order_at` 可在问句里展示，**不是** Pilot 必导字段，也不得用来自动选人。

### 2.3 禁止

| 禁止 | 若做会变成 |
| --- | --- |
| **客户画像自动生成** | LLM 从聊天编「常拿 / 爱欠」 |
| **自动创建客户** | Pilot 主路径不靠冷启动长客户库；没有 id 就问老板，人补进目录后再开 |
| **自动修改客户资料** | 改名、改电话、改档口、合并同名 |

Runtime 已有的冷启动（有档口事实才 `create_candidate`）**不改**。Pilot **不把它当数据策略**：试班客户应人事先录入。现场新客：观察人记下，人补目录，不让 AI 建档交差。

不导入：欠款、账期、信用额度、结算方式、价格档。那些不是开单员认人所需，也不是本阶段财务。

---

## 3. Product 数据边界

商品理解需要把口语落到 **已有** 本体节点；确认仍要求行到 **sku**。

### 3.1 允许进入工作目录的字段

| 字段 | Pilot 用途 | 对应现网 |
| --- | --- | --- |
| **item_id** | 可履约叶节点；确认、入账、默认习惯都挂这个 | `ProductNode.id`（`level=sku`） |
| **product name** | 苹果、红富士、皇冠梨 | 树上 `name`（variety / cultivar / sku） |
| **spec** | 80 果、一级、烟台、箱装 | `attributes`（size / grade / origin / packing） |
| **alias** | 八十果、八零果、金边 | `aliases[]` |

品种/品类节点可以有，便于「苹果」先命中再按规格或档案落到 SKU。Pilot 统计「商品数量」时只计 **可确认的叶 SKU**，不计「水果」这种类目。

### 3.2 禁止

| 禁止 | 正确行为 |
| --- | --- |
| **AI 创建 SKU** | 树上没有的货：挂起、问老板，人补目录 |
| **AI 修改商品** | 不改名、不改规格、不合并节点、不从 ERP Item 反向同步进 Catalog |

Adapter 向 ERP 写 Draft SO / 必要时 ensure Item，是入账翻译，**不是** Runtime 建货。禁止 `item_code` 进入 Parser / OrderLine。

王记 +「苹果」无档案默认 → `product_ambiguous`，必须问规格。李老板 +「苹果」有预置默认 → 可落到红富士 80 果，口播须说按档案。这两条都是用已有事实，不是猜 SKU。

---

## 4. Memory 边界

长期记忆 **只能** 来自确认后的领域事件。与 [ADR-009](ADR/ADR-009-memory-from-confirm-events.md) 相同，Pilot 不另开写入口。

```text
order.confirmed
  → Extractor（客户 id、行 SKU、价源、品种节点）
  → Evidence
  → MemoryPolicy
  → Storage
```

### 4.1 只能来自

**confirmed event**（已过 Confirm Gate 的结构化草稿）。

Pilot 允许的习惯只有两类：

1. **人预置的 `product_default`**（主数据，上线前标好）
2. **确认证据累计达标后升级的默认**（同一客户+品种，净确认 ≥ 3）

### 4.2 不能来自

| 来源 | 为什么 |
| --- | --- |
| **用户聊天** | 原话不是企业事实；失败案例原话只进观察表 / 语言资产 |
| **LLM 猜测** | 模型不写 Memory、不编画像、不选默认 SKU |
| **未确认订单** | 改口、待确认草稿、作废重来都不进长期记忆 |

也不从：微信聊天记录、纸本抄单原文、观察表、Demo 口令映射。

价：`last_deal` 仅确认且该行明确单价；TBD 不写。读侧仍只 notice，**禁止静默改行价**。Pilot 不靠导入历史成交来自动报价。

---

## 5. Pilot 最小数据集

一个档口上线，准备 **当天会喊到的切片**，不是全市场客户库、不是全品类 ERP。

口径：人从企业事实抄进 Catalog。数量按 **会开口的** 计，不按 ERP 总行数。

| 项 | 下限（可进有监督 Pilot） | 建议（一个早市够用） | 不是 |
| --- | --- | --- | --- |
| **客户数量** | **≥ 5**，且 **至少 1 组同名**（两家不同区分事实） | **10–20** 当天熟客 | 全量 CRM；没有电话也没有档口的「名字列表」 |
| **商品数量** | **≥ 5** 个可履约 SKU（含 name / spec / alias） | **10–30** 当天货盘叶 SKU | 只导入「苹果」品种、不建 80 果这种可确认叶 |
| **历史订单** | **0 张即可上线** | 不导入。若要从成交长出默认，同一客户+品种 **≥ 3** 张已确认 | 微信聊天、未确认草稿、把旧 SO 当 Memory 灌进去 |
| **默认习惯** | 每个「喊品种就要落到某 SKU」的熟客 **1 条人标 `product_default`** | **3–8 条**（如李老板苹果→红富士 80 果） | 全客全品画像；LLM 生成「常拿清单」 |

现网 Demo 种子（3 客户 / 4 叶 SKU / 2 条苹果默认）只够金脚本，**不够**真实档口 Pilot。进摊前按上表补切片，仍用现有 Catalog 写入路径（种子或人工录入），不开发客户管理界面。

历史订单 **不是** 认人认货的前提。没有历史，习惯用人标默认；没有人标默认，现场问规格。

---

## 6. 数据缺失行为

没有数据：**不是猜。而是询问老板。**

| 缺什么 | Runtime / Pilot 行为 | 观察表主因 |
| --- | --- | --- |
| 称呼零命中 | 问这是谁、档口/电话；**不**自动建客户交差 | 数据不足 |
| 同名、区分事实不够 | 必须问哪一家；禁止最近一个 | 数据不足（若问了仍猜 → Runtime） |
| 货名不在树 / 未到 sku | 挂起、问规格或货名；**不**创建 SKU | 数据不足 |
| 有品种无默认（如王记苹果） | 问规格，不落到某 SKU | 正确行为，不算错误 |
| 无历史订单 | 照常开；不编「他上次拿过」 | — |
| 无默认习惯 | 问清楚再确认；不编常拿 | 数据不足（若静默套错货） |

人补目录之后再喊同一句。补的是企业事实，不是 Prompt，不是新 Agent。

---

## 7. Sales Employee V1 Pilot 所需最小企业事实集合

上线一个档口，工作目录里至少有下面这些 **已存在的事实**（不是 AI 生成物）：

```text
Customer（认人）
  customer_id
  name
  alias[]          # 可空，但建议有
  区分事实 ≥ 1：phone | address | tags.档口
  同名组：每家区分事实互不相同

Product（认货）
  item_id          # 叶 SKU
  product name
  spec             # 能把「八十果」落到该叶
  alias[]

Habit（可选，人标）
  (customer_id, 品种节点) → item_id     # product_default

Memory
  仅 order.confirmed 之后可写
  禁止：聊天 / LLM / 未确认单

不进入本集合
  欠款、账期、库存、支付、财务、客户画像、自动建档、自动建 SKU
```

数量下限见 §5：客户 ≥ 5（含同名组）、叶 SKU ≥ 5、历史订单 0、默认习惯按需人标。

准备齐这套切片，再按检查清单进摊，用观察表记账。缺事实就问老板、人补目录。不开发 CRM，不扩展 ERP，不改 Runtime。

---

## 评审六问

1. **哪一层？** Pilot 企业数据边界（Catalog 工作目录切片）。不改内核。
2. **改 LLM 权限？** 否。模型仍不选客户、不选 SKU、不写 Memory。
3. **改 Confirm Gate？** 否。
4. **污染 Memory？** 否。仍只从 confirmed event；失败原话与聊天不进 Memory。
5. **经 Event？** Memory 仍只消费确认事件。主数据不经 Event 由 AI 创造。
6. **Adapter 还是 Runtime？** 企业事实来自 ERP/纸本；Runtime 只读工作目录。不扩展 ERP 做客户管理。
