# ADR-010

标题：确认后的偏好修正走 Adaptive Memory，禁止原话改档案

- 状态：accepted
- 日期：2026-08-16

## 背景

Sprint 6B 已让长期记忆只从 `order.confirmed` 学习：`last_deal` 立即写，`product_default` 需同向确认证据 ≥ 3。熟客仍会在本单改规格（苹果本按红富士，今天拿青苹果）。若把改口写进档案，一次纠正会毁掉习惯；若完全忽略，本单会反复套错默认，且多次确认后的新习惯无法替换旧默认。

## 问题

如何让「这次不要档案默认」立刻影响本单，又让「多次确认后的新偏好」可替换长期默认，同时不允许用户原话或修正事件直接改 `product_default`？

## 决策

分三层，互不替代：

1. **Session 抑制（当前订单状态）**  
   行落地 SKU ≠ 档案该品种默认时，把该品种节点记入 `SalesSession.suppressed_default_node_ids`。`fill_sku` 对本 Session 跳过这些 default。只影响本单，不写长期记忆。

2. **`memory.preference_adjusted`（确认后才发）**  
   由 Runner 在 `confirm` 成功后发布（OrderService 不读 Profile，保持冻结）。仅当最终 SKU ≠ **档案**默认（不是 Session 抑制后的视图）。payload **只**含：

   `customer_id` / `node_id` / `from_sku_id` / `to_sku_id` / `order_id`

   禁止 `user_text`。未确认改口不发。最终仍等于默认不发。

3. **Evidence + MemoryPolicy**  
   `order.confirmed`：成交 SKU `observe` 正向。  
   `preference_adjusted`：对 `from_sku` `adjust(delta=-1)`。  
   净 `count = max(0, positive_count - negative_count)`，禁止为负。预留正负计数以便解释历史。  
   修正事件 **不得** 写 `product_default`。长期默认仍：该 SKU 的确认证据净 count ≥ 阈值。

纠错只来自确认后的结构化业务事实。Extractor 禁止读用户原话。

冲突恢复路径必须可测：旧默认 → 多次确认新偏好升级档案 → 再多次确认旧 SKU 恢复旧默认。

## 原因

本单对错是任务状态，习惯是跨单证据。确认后的草稿已经过 Policy 闸门，适合作为唯一修正信号。把负向从「直接覆盖档案」拆成证据调整，才能在来回改口时解释历史，而不是最后一单赢。

## 影响

- 好处：一次纠正不污染档案；多次同向确认可替换默认；旧习惯可被再确认拉回。
- 限制：未确认改口只抑制本单；证据低于阈值不会自动删掉已写入的 default，需对侧 SKU 达到阈值后覆盖。
- 冻结：Parser、Resolver 主流程、`Policy.confirm_gate`、OrderService、Response。`fill_sku` 允许增加抑制参数（用档，不是确认闸门）。
