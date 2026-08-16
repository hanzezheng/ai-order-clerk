# 农批语言能力评测（V0.3C）

> 验证的不是「再做一个 Agent」，而是：**现有 Parser → SpeechAct → ProductUnderstanding → Resolver → Policy → Service 是否听得懂档口话，并在复杂订单链路上不破坏闸门。**
>
> 本文件是评测分层、覆盖缺口、金脚本与 V0.4 准入。最高设计依据仍是 [DESIGN.md](DESIGN.md) §14.14 与 [ADR-018](ADR/ADR-018-language-capability-benchmark.md)。
>
> 冻结：不改 `confirm_gate`；不自动建 SKU；不做 ASR/TTS、ERP、Vector DB；不新增商品智能 Agent。

与 [VALIDATION.md](VALIDATION.md) 分工：VALIDATION 观察老板会不会改习惯；本文观察系统会不会把农批话落到正确草稿。

---

## 0. 评测什么 / 不评测什么

| 要评 | 不要评 |
| --- | --- |
| 一段话能否抽出正确 `SpeechAct[]` | 模型文采、回复是否像人 |
| 规格口语能否变成 `ProductQuery.attributes` | LLM 是否选对 SKU |
| 过滤后唯一命中是否提升已有节点 | 树上没有的规格能否长出新品 |
| 多回合改口是否保持 `line_id` | ASR 准不准、TTS 好不好听 |
| `confirm_ok` 是否仍只认 `product_sku_id` | ERP 能否同步、向量能否检索 |

输入永远是**文本**（模拟连报）。有 `LLM_API_KEY` 时 LLM Parser 走真模型；无配置时外壳直接规则 Parser。金脚本必须同时声明：走 LLM 夹具、走规则兜底、或两者都要。

---

## 1. 分层 Benchmark

禁止混层。Parser 用例不得期望 `sku_id`；Resolver 用例不得改 Parser Schema；会话金脚本不得用口播字符串当 SKU 断言。

```text
L0 安全不变式     永远 100%。失败则整层红，禁止用准确率稀释。
L1 语言抽取       Text → SpeechAct[]（现有 sales_parser_cases.json）
L2 规格理解       SpeechAct → ProductQuery（无业务 id）
L3 解析结果       ProductQuery → ProductMention（不写 resolved_sku）
L4 订单链路       多回合 Session 草稿事实（line_id / sku / qty / confirm）
L5 口播义务       ReplyPlan 可见事实（现有 sales_conversation_cases.json）
```

现有 `ParserEvaluator`（`scored=false`）只覆盖 L1 记录。V0.3C 把它扩成**分层报告**，仍禁止用 LLM 当 SKU 裁判。

### 1.1 L0 安全不变式

任何夹具、任何 Parser 路径都必须成立：

| ID | 不变式 |
| --- | --- |
| S1 | Parser / ProductQuery 输出不得含 `sku_id` / `product_id` / `customer_id` |
| S2 | Understanding / Resolver 不得写 Catalog 节点或 Alias |
| S3 | Resolver 不得写 `resolved_sku`；不得把金枕落到金边 |
| S4 | `confirm_gate` 仍：无最终 `product_sku_id` 则 `confirm_ok=false` |
| S5 | 未消歧客户不得套档案默认 SKU / 价 |
| S6 | 缺价只 `notice`，不得 `session_block`；不得编造行情数字 |

### 1.2 L1 语言抽取

数据：`docs/dataset/sales_parser_cases.json`。

只比 `type` + 语言槽（`customer_mention` / `product_mention` / `spec_mention` / `qty` / `uom` / `unit_price` / `mention`）。期望里禁止店名全称、SKU 全称、业务 id。

标签：

| tag | 用途 |
| --- | --- |
| `canonical` | 口令句；无配置规则路径必须绿 |
| `stall_oral` | 档口口语；LLM 夹具必须绿；规则路径可登记豁免 |
| `must_not_guess` | 负例；猜 SKU / 补规格全称即失败 |

评分（有真模型时才打）：act 类型一致、槽位字符串不擅自改写、不新增原句没有的数字。无模型时只跑规则路径 + 夹具回归，不算模型分。

### 1.3 L2 规格理解

输入：语言槽 + 可选 `focus_node_id`（测试夹具从 Session 行注入，禁止从 LLM 注入）。

断言：`lookup_text`、`attributes` 只含 `size|grade|origin|packing`、`extra=forbid`。

### 1.4 L3 解析结果

断言：`matched_node` 层级与 id、`resolution_candidates`、`resolved_sku is None`。需要 SKU 履约时再单独调 `Policy.fill_sku`（L3 与 Policy 分开记）。

三种合法结局：唯一提升已有 sku 节点 / 多候选 `line_hold` / 零命中保持未履约且 Catalog 不变。

### 1.5 L4 订单链路

见 §3 金脚本。只断言草稿与闸门，不断言口播修辞。

### 1.6 L5 口播义务

数据：`docs/dataset/sales_conversation_cases.json`。连报不问价、同名客户必须问、TBD 可见、未消歧不泄漏档案 SKU。

---

## 2. 当前商品理解覆盖缺口

对照 V0.3B：封闭词典 + 属性过滤 + 唯一提升。种子树只有红富士80 / 青苹果统货 / 皇冠梨箱装 / 金边榴莲一档 SKU。

### 2.1 已覆盖（必须保持）

| 现象 | 现状 |
| --- | --- |
| 王记+苹果无规格 | variety 挂起，确认失败 |
| 李老板+苹果无规格 | 档案默认 FUJI80 |
| LLM `spec_mention=八零果` | 属性 `size=80`，唯一提升 FUJI80 |
| `统货` / `烟台` / `箱装` / `一级` | 四键各有至少一词 |
| 复合品名「苹果八十果」 | Understanding 剥离 lookup=苹果 |
| 九十果、金枕 | 不建 SKU、不替品 |
| refine 打在 focus 行 | 合行不裂行（属性能归一且唯一时） |

### 2.2 词典与属性缺口

| 缺口 | 例子 | 风险 | V0.4 前 |
| --- | --- | --- | --- |
| 规格词与数量切分冲突 | 「八十果」「苹果八十果六十件」 | 规则 Parser 把「八/八十」切成 qty，规则兜底丢规格 | 登记豁免；LLM 夹具必须绿 |
| 多属性合取 | 「烟台八十果一级」 | 只命中部分键则可能错升或升不了 | **必须**：两键合取有测 |
| 规格同义未入表 | 80号 / 八零的 / 大果 / 二级 / 散装 / 陕西 | 当未知规格：不建 SKU，行挂起 | 种子树上有的同义要收；没有的保持挂起 |
| 件重 / 产季 | 「18斤件」「早熟」 | V0.3B 明确不做 | **不做**（仍禁止建 SKU） |
| 单位 vs 包装 | 「来一箱」vs「箱装」 | 可能把 uom 误当 packing | L1 抽 uom；packing 只来自规格词 |

### 2.3 本体层级缺口（不是属性）

「红富士」是 cultivar 节点，不是 `attributes`。V0.3B 词典不管它。Runner 若把它当 `product_mention` 走节点匹配，**可能**已能合行（`related` / `same_variety` + 唯一子 SKU），但**没有链测**。

| 缺口 | 例子 | V0.4 前 |
| --- | --- | --- |
| 品种名 refine | 苹果60件 →「红富士」 | **必须**同一 `line_id`，且不得新 SKU |
| 颜色/外观指代 | 「那个红的」 | L1 保持原词、禁止猜 SKU；不要求理解成红富士 |
| 别名品种 | 蛇果 / 嘎拉 | 树上无节点则 unknown；禁止替到红富士 |
| 过滤后仍 ≥2 候选 | 若有 80 与 90 两个红富士 SKU | 必须 `line_hold`，不得提升 | 评测夹具允许加**种子** SKU，禁止运行时创建 |

### 2.4 指代与 focus

`focus_node_id` / `focus_line_id` 来自 Session，默认最近落地行。连报「苹果60件梨40件」后光杆「烟台的」会打在**梨**上。

V0.3C **禁止**让 LLM 选行号。金脚本要么同句带品名（「苹果要烟台的」），要么接受 focus=最后一行并写进期望。这是语言契约，不是缺陷补丁。

「刚才那个 / 那个不要了」：L1 已有；L4 必须有链测（改 qty / 删行打在 focus）。

### 2.5 SpeechAct 已定义、Runner 未执行

| Act | L1 | Runner |
| --- | --- | --- |
| `replace_product` | Schema 有，数据集几乎无 | 落 `unknown_act` |
| `use_old_price` | 口语用例有 | 落 `unknown_act`；且 ADR-007 默认不静默套价 |
| `cancel_order` | canonical「这单作废」 | 落 `unknown_act` |

这些是**执行债**，不是商品理解债。V0.3C 评测要把它们标成红/跳过，禁止假装已会。V0.4 开工前：L1 必须能抽；执行落地属 V0.4 内核（仍不改 `confirm_gate`），不阻塞「语言分层评测可跑」。

### 2.6 种子树对评测的限制

当前苹果下两个 SKU 属性正交（80+一级+烟台+箱装 vs 统货）。「箱装」能唯一到 FUJI80，是因为青苹果没有 packing 键，不是包装语义真的唯一。

V0.3C 允许为评测增加**稳定 UUID 种子节点**（例如红富士 90 果），以便测「过滤后仍歧义」。禁止用测试去「学会」新 Ontology。

---

## 3. 复杂订单链路测试方案

每条金脚本固定：客户种子、Parser 路径、逐回合用户文本、草稿期望、Catalog 快照、闸门。一条失败不得靠改口播蒙混。

夹具优先级：

1. **Fake LLM 按句给槽**（测 Understanding → Resolver → Policy，避开规则切词）。
2. **无配置规则路径**（测 Demo 无密钥仍能开的口令与非数字规格）。
3. 真模型（可选，不作为 CI 门禁，除非环境有密钥且分数只记 L1）。

### 3.1 G1 王记规格闭环（无档案默认）

目标：无默认客户靠规格落到已有 SKU，确认成功。

| 回合 | 用户 | 期望 |
| --- | --- | --- |
| 1 | 开王老板的单 | `customer_ambiguous`，未开单 |
| 2 | 王记水果店 / 8号档 | 绑定王记 |
| 3 | 苹果60件梨40件加两个金边榴莲 | 三行都在；苹果无 sku；梨可唯一子节点；金边可唯一子节点；不问价 |
| 4 | 苹果要烟台的八零果 | **同一苹果 `line_id`**；`product_sku_id=FUJI80`；行数仍为 3 |
| 5 | 不对榴莲改三个 | 金边 qty=3，不裂行 |
| 6 | 好了 | `confirm_ok=true`；价未定；节点数不变 |

禁止：第 4 步光杆「八零果」作为唯一期望路径（focus 可能在榴莲）。允许另做负例：连报后光杆规格打在最后一行。

### 3.2 G2 李老板档案 + 改口 + TBD

| 回合 | 用户 | 期望 |
| --- | --- | --- |
| 1 | 开李老板的单 | 绑定李记 |
| 2 | 苹果60件 | 档案默认 FUJI80，回复可见红富士/按档案 |
| 3 | 统货 | 若 unique 到青苹果统货：本单抑制红富士默认；同一 `line_id` |
| 4 | 再加20件 | qty=80（或统货行累加），不新开苹果行 |
| 5 | 好了 | 可确认；价未定；不写错档案（确认证据规则仍按 Sprint 7） |

### 3.3 G3 连报歧义不中断

| 回合 | 用户 | 期望 |
| --- | --- | --- |
| 1–2 | 开王老板的单 → 王记 | 绑定 |
| 3 | 苹果60件梨60件 | `expect_more` 时 ack；苹果 hang、梨写入；不得停图 |
| 4 | 好了 | `confirm_ok=false`（苹果无 sku） |
| 5 | 烟台 | 若 focus=梨且梨无烟台属性：梨仍履约或 hang，**苹果不得被偷偷改掉**；Catalog 不变 |

第 5 步用来锁 focus 契约，不是为了「猜用户想改苹果」。

### 3.4 G4 失败保持

| 脚本 | 期望 |
| --- | --- |
| 王记 + 苹果九十果 + 好了 | 无 sku；确认失败；节点/别名快照不变 |
| 王记 + 金枕 | 不落到金边；不建节点 |
| 开王老板的单 + 苹果60件（未消歧） | 不出现红富士；货行 buffer |
| 紫麒麟 | mention candidate；不改 Ontology |

### 3.5 单回合压力（可与 G1 并行）

一条文本多 act，顺序执行：

> 开王记的单苹果六十件要八零果梨四十件统货加两个金边不对榴莲改三个好了

期望：客户若能唯一到王记则开单；苹果 FUJI80；梨 GREEN 或梨 SKU（按过滤）；金边 3；可确认。客户「王记」与「王老板」消歧规则不得被这条抄近路破坏——若 Parser 抽成王老板，必须仍问哪一个。

### 3.6 链测断言清单（每步）

- `line_id` 集合：升级不新增、删行才减少
- `product_sku_id` / `matched_node_id` / `filled_from`
- `qty` 与 `merge_op`
- `verdict.issues[].code`（`product_ambiguous` / `line_unresolved` / `customer_ambiguous`）
- `confirm_ok`
- `catalog.list_nodes()` id 集合与 `aliases.snapshot()`
- 禁止用 `reply_text` 代替 SKU 断言

---

## 4. V0.4 之前必须达到的能力标准

V0.4 指下一阶段产品增量（无论是 ASR 外壳、ERP 适配还是 LangGraph）。下列未绿，不得开工 V0.4。

### 4.1 必须绿

1. **L0 全绿**（S1–S6），旧回归（含王记歧义、李老板默认、紫麒麟、confirm 缺 sku）全绿。
2. **分层评测可重复跑**：L1 数据集 + L2/L3 单测 + L4 金脚本 G1–G4 + L5 口播义务。CI 默认：无密钥路径 + Fake LLM 夹具。
3. **规格四键**：size / grade / origin / packing 在种子树上各有「唯一命中」与「零命中不建 SKU」。
4. **两属性合取**：例如 origin+size 仍只提升已有 FUJI80；合取后 0 命中则不确认、不建 SKU。
5. **§13.4 合行**：苹果 +「红富士」同一 `line_id`；苹果 + 规格 refine 同一 `line_id`。
6. **连报不中断**：一条或多条 turn 中，一行 `line_hold` 不丢其他行。
7. **focus 契约写进金脚本**：光杆规格打最后一行；改指定行必须带品名。禁止用 LLM 填 `target_line_id`。
8. **规则路径豁免表公开**：`八十`/`八零果` 类切词失败不得假装通过；LLM 夹具覆盖同一业务结局。
9. **`confirm_gate` 语义零漂移**：只有最终 `product_sku_id` 可确认；缺价仍可确认。

### 4.2 必须登记、不阻塞评测Harness、但不得宣传为已会

- `replace_product` / `cancel_order` 执行
- `use_old_price` 填价（默认仍不静默套上周价）
- 颜色指代消解成品种
- 件重 / 产季属性
- 真模型 L1 分数门槛（预留 `ParserEvaluator.scored`）

### 4.3 明确不做（V0.4 前也不做）

ASR / TTS / ERP 商品同步 / Vector DB / 自动创建 SKU / Ontology 学习 / 商品智能 Agent / 改 `confirm_gate` / LLM 返回 sku_id。

---

## 5. 执行顺序（设计批准后）

```text
本文件 + DESIGN §14.14 + ADR-018
  → L0/L4 金脚本测试（先写）
  → 分层报告夹具（扩 ParserEvaluator，仍可 unscored）
  → 按缺口补：评测种子 SKU、合取用例、红富士合行链测
  → 词典只收「种子树上已有属性的同义口语」
```

先测后补。补词典不得变成补 Ontology。
