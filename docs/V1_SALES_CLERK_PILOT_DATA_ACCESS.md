# 农批 AI 销售开单员 V1 — Pilot 数据访问边界

> 当前遵守 [AI_EMPLOYEE_ARCHITECTURE.md](AI_EMPLOYEE_ARCHITECTURE.md)、[RUNTIME_FREEZE.md](RUNTIME_FREEZE.md)。
> 本阶段只允许修改：**Pilot 数据访问边界文档**（及必要交叉引用）。
> 禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate / OrderService / Memory / Runtime Freeze 边界。
>
> **不是做 CRM。不是做 ERP 替代。不是新增业务能力。不新增 Agent。不引入库存 / 支付 / 财务。不改 Runtime 核心 / Confirm Gate。**
>
> 要哪些事实见 [V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md](V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md)。投递状态读路径见 [V06_ERPNEXT_READ_ADAPTER.md](V06_ERPNEXT_READ_ADAPTER.md)。决策见 [ADR-033](ADR/ADR-033-v1-pilot-data-access.md)。

数据边界回答：摊前准备哪些企业事实。本文回答：**这些事实怎样进入 AI Employee Runtime。**

不是每一句喊单都去打 ERP。不是让账本指挥开单。

---

## 0. 结论

企业事实只经 **Read Adapter 投影** 进入工作目录。Runtime **只消费投影**。

```text
ERP Customer / 现有档案     ─┐
ERP Item / 商品目录         ─┤
                              ▼
                         Read Adapter
                         （读 + 投影成领域切片）
                              ▼
                         Catalog 工作目录
                         （customer_id / item_id / 别名 / 档口）
                              ▼
                         Runtime Resolver
                         （只看投影，决定问还是继续）
                              ▼
                         Policy / Confirm Gate
                         （ERP 碰不到）
```

V0.6 Read Adapter 已经把 **入账投递状态** 投影到工作台。Pilot 访问边界把同一原则用到 **认人认货主数据**：Adapter 投影切片，Runtime 不直连 DocType。

禁止：ERP 直接控制 Resolver / Confirm / Policy。禁止 Resolver 按 `customer_name` / `item_name` 模糊搜 ERP。

---

## 1. 数据来源

事实在企业侧，不在模型里。Pilot 只声明来源，不开发客户管理、不替代 ERP。

| 事实 | 来源 | 进入 Runtime 之后是什么 |
| --- | --- | --- |
| **Customer** | **ERP Customer**，或档口 **现有档案**（纸本/旧系统，人核对后视同企业事实） | Catalog 客户实体：`customer_id`、name、alias、phone、档口 tags |
| **Product** | **ERP Item**，或档口 **商品目录**（货盘可履约叶，不是「水果」类目） | Catalog 本体叶：`item_id`、name、spec、alias |

写路径仍是 V0.5：`order.confirmed → Outbox → Write Adapter → Draft Sales Order`。本文只管 **主数据怎么进来**，不管确认之后怎么出去。

入账「排队中 / 已进草稿 / 看不见」仍走 V0.6 投递查询，不走本切片，不进 Confirm Gate。

不作为来源：微信聊天、LLM 编的客户、未确认草稿、库存仓位、欠款、科目。

---

## 2. Adapter 边界

三层各做一件事：

| 层 | 做什么 | 不做什么 |
| --- | --- | --- |
| **ERP** | **提供事实**（Customer / Item 主数据；纸本档案经人录入后同等） | 不选哪一个王老板、不决定能不能「好了」 |
| **Read Adapter** | **读取和投影**：剥掉 DocType / `item_code`，变成领域切片写入 Catalog | 不解析口语、不改订单、不写 Memory |
| **Runtime** | **只消费投影**：Resolver 认人认货；Policy 问或继续；Confirm Gate 照旧 | 不 `frappe.get_doc`、不拼 SQL、不按名称搜 ERP |

```text
ERP:          提供事实
Read Adapter: 读取和投影
Runtime:      只消费投影
```

### 2.1 两个时刻

| 时刻 | 谁读 ERP | Runtime 看见什么 |
| --- | --- | --- |
| **开门 / 上线初始化** | Read Adapter | 把客户切片、商品切片投影进 Catalog |
| **喊单回合** | **没有人** | Resolver 只查 Catalog 投影；候选已是领域对象 |

回合中「Read Adapter 返回王老板 A/B」指的是：**候选来自 Adapter 已经投影好的切片**，不是 Resolver 当场 GET `tabCustomer`。

V0.6 禁令仍在：Parser / Resolver / Policy / Confirm Gate / OrderService / Memory **不得 import** Read Adapter。装配层可在开门时触发投影刷新。

### 2.2 禁止 ERP 直接控制

ERP 不得直接控制：

- **Resolver** — 不按 ERP 搜索结果点选客户/SKU
- **Confirm** — 库存、欠款、Item 是否存在不得改 `confirm_ok`
- **Policy** — 投影不进 `BusinessContext`；不把 ERP 失败变成 `session_block` 以外的「账本说了算」（认人失败仍是目录里没有唯一候选，由 Runtime 询问，不是 ERP 拒单）

Adapter 内部可以认识 `item_code`。Runtime 实体不行。

---

## 3. Customer 查询流程

老板说：

> 王老板苹果 20 箱

认人只走投影，不走 ERP 模糊搜。

```text
Input（语音/文本）
  ↓
Parser → SpeechAct（start_order / add_line …）
  ↓
Resolver 请求候选
  （对称呼「王老板」查 Catalog 投影，不是查 ERP）
  ↓
投影中的候选：
  王老板 A   customer_id=…  档口 3 / 电话尾号 0003
  王老板 B   customer_id=…  档口 8 / 电话尾号 0008
  ↓
Runtime 决定：
  询问老板「是 3 号档还是 8 号档？」
  货行可进 buffer，禁止套任何一家的档案默认
```

| 投影结果 | Runtime |
| --- | --- |
| **一个**匹配 | 绑定该 `customer_id`，继续开行 |
| **多个**匹配 | **询问**；禁止最近一个、禁止 ERP「主客户」覆盖 |
| **零个** | **询问**这是谁；不自动建客户（Pilot 主路径，见数据边界） |
| **读取失败**（开门投影失败） | 当目录不可用：**不能猜**；询问并记下同步失败 |

LLM 不参与选哪一个王老板。

---

## 4. Product 查询流程

老板说：

> 苹果 20 箱

（客户已唯一，或本句同时带客。）

```text
Input
  ↓
Parser → product_mention = 苹果
  ↓
Resolver 请求候选
  （查 Catalog 商品投影：名称 / spec / alias）
  ↓
Runtime：
```

| 投影结果 | Runtime |
| --- | --- |
| **一个匹配** | **继续**（落到该节点；未到 sku 仍走现有档案默认或追问规格） |
| **多个匹配** | **询问**（王记 + 苹果无默认 → 规格歧义，挂起问规格） |
| **没有** | **挂起**；不创建 SKU；问老板货名/规格，人补目录后再喊 |
| **读取失败** | **不能猜** SKU；当目录不可用，询问 |

李老板有人标默认「苹果 → 红富士 80 果」：一个可履约匹配来自 **已投影的习惯 + 商品切片**，口播须说按档案。这不是 ERP 定价单，也不是模型猜的。

禁止：按 `item_name like '%苹果%'` 搜 ERP Item 来填 Resolver。那是账本取代 Catalog。

---

## 5. Pilot 最小初始化流程

一个新档口上线：人触发一次（或早市开门一次）**切片投影**，不是同步全公司 ERP。

```text
1. 选定档口
2. Read Adapter 读取来源
     Customer ← ERP Customer / 现有档案
     Product  ← ERP Item / 商品目录
3. 投影进 Catalog（字段以数据边界为准）
4. 抽查：同名能问出两家；主货能落到叶 SKU
5. 开始有监督试班
```

| 需要导入 | 不需要 |
| --- | --- |
| **客户切片**（≥ 5，含 1 组同名；有区分事实） | **库存**（仓位、可用量） |
| **商品切片**（≥ 5 个可履约叶 SKU + spec/alias） | **欠款** / 应收账款 / 账期 |
| 按需：人标 `product_default` | **财务**（科目、发票、收款） |
| | 全量历史 SO、价格表写回行价、submit 单据 |
| | 客户画像、自动建档界面、CRM |

Demo 种子可当 Fake 投影，只够金脚本。真实 Pilot 用本切片替换/补齐，仍经 Adapter 或等价人工导入 Catalog，不开发 ERP 替代界面。

开门刷新失败 → 用上一份投影或停手询问，不带着空目录猜熟客。

---

## 6. 数据同步失败行为

读取是 Adapter 的事。失败不得变成「AI 更聪明」。

| 情况 | 行为 |
| --- | --- |
| **读取失败**（超时、5xx、未配置 ERP、纸本未录入） | **不能猜**。投影标不可用；开单不编一个王老板/一个 SKU。询问老板，或等投影恢复。不改 `confirm_ok`。 |
| **数据缺失**（称呼或货名在投影里没有 / 不唯一） | **询问**。零命中问是谁、什么货；多命中问哪一家、哪一种规格。 |
| 投影过期（ERP 新增客户尚未同步） | 当缺失：**询问**；人补来源后再投影。不让 Resolver 直查 ERP 救场。 |

失败记观察表主因 **数据不足**（同步失败）或 **Runtime**（有投影却猜了）。不要为此做 CRM，不要新增 Agent。

与 V0.6 投递读取一致：ERP 失败 → `unavailable`，Runtime 单仍按闸门走。主数据读取失败同样 **不指挥确认**，只让认人认货停在询问。

---

## 7. Sales Employee V1 的企业事实进入边界

```text
来源
  Customer: ERP Customer / 现有档案
  Product:  ERP Item / 商品目录

进入
  Read Adapter 读取 → 领域切片投影 → Catalog 工作目录

消费
  喊单回合：Resolver 只读投影
    1 个匹配 → 继续
    多个匹配 → 询问
    没有     → 询问 / 挂起
  确认：现有 Confirm Gate（ERP 不参与）
  入账：Write Adapter（确认之后）
  看见投递：V0.6 Read 投影（不进闸门）

禁止
  ERP 直接控制 Resolver / Confirm / Policy
  回合中按名称搜 ERP
  库存 / 欠款 / 财务进入切片
  读取失败时猜测
```

一句话：ERP 提供事实，Adapter 投影事实，Runtime 只用投影认人认货；认不准就问老板。

---

## 评审六问

1. **哪一层？** Adapter 投影 + Catalog 工作目录。不改 Runtime 核心。
2. **改 LLM 权限？** 否。模型仍不选客户、不选 SKU。
3. **改 Confirm Gate？** 否。ERP 读失败不改 `confirm_ok`。
4. **污染 Memory？** 否。投影不是 confirmed event。
5. **经 Event？** 写仍经 Outbox。主数据读是初始化/开门投影，不是第二套 Outbox。
6. **Adapter 还是 Runtime？** 读 ERP 只在 Adapter。Runtime 只消费投影。
