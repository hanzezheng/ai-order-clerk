# ADR-018

标题：语言能力用分层 Benchmark 衡量，不新增 Agent

- 状态：accepted
- 日期：2026-08-16

## 背景

V0.3A 让 LLM 成为默认语言入口；V0.3B 用确定性 Understanding 把规格口语约束到已有商品树。两者都禁止 LLM 选 SKU、禁止改 `confirm_gate`。若下一步做商品 Agent、上语音或接 ERP，会在「档口话是否真能开完复杂单」未经测量时把错误放大。

## 问题

如何证明农批语言能力已经够格进入 V0.4，同时不推翻 Parser / Understanding / Policy 边界？

## 决策

V0.3C 只建设**分层语言与订单链路评测**，不新增 Agent，不上 ASR/TTS。

- 六层分开：L0 安全不变式、L1 SpeechAct、L2 ProductQuery、L3 Mention 候选、L4 Session 金脚本、L5 口播义务。禁止混层期望。
- 金脚本测草稿事实与闸门，不拿 `reply_text` 当 SKU 断言。
- `focus_line_id` / `focus_node_id` 仍只来自 Session。光杆规格打最后一行；改指定行必须带品名。
- 规则 Parser 对「八/八十」的切词失败登记为豁免，不得用规则路径冒充八零果已通。
- 评测可加稳定种子 SKU，禁止运行时建 SKU、学 Ontology、Vector DB、ERP。

细则见 [LANGUAGE_BENCHMARK.md](../LANGUAGE_BENCHMARK.md)。

## 原因

语言抽取、规格归一、候选过滤、确认闸门是四件不同的事。混在一个「准确率」里，会让 LLM 靠猜 SKU 刷分，或让口播修辞掩盖未履约行。

## 影响

- 好处：V0.4 有可重复的准入门；缺口（合取属性、红富士合行、focus 契约、未执行 SpeechAct）被写死。
- 限制：无密钥 CI 不能代表真模型 L1 分；`replace_product` / `cancel_order` / `use_old_price` 仍是执行债，不在本阶段假装完成。
