# AI Employee Runtime — 全局架构约束

> 后续所有开发决策的**最高架构约束**。产品细则仍见 [DESIGN.md](DESIGN.md)；二者冲突时：**先守本文件的分层与权限，再改 DESIGN**。
>
> 这不是普通订单系统，也不是聊天机器人。

目标：构建一个基于 ERPNext 的 **AI 原生员工层**。

当前第一个员工：农批档口 AI 开单员。

未来可以扩展其他业务 Agent，当前只验证销售开单。

---

## 1. 总体架构

最终目标：

- **ERPNext** 是企业业务事实系统。
- **AI Runtime** 是自然语言业务执行层。

```text
老板
  |
  |  文本 / 语音
  v
AI Employee Runtime
  |
  v
ERPNext Adapter
  |
  v
ERPNext
```

禁止：

- 把 AI 做成 ERP 页面上的聊天框。
- 把 ERP 逻辑塞进 AI Runtime。

---

## 2. AI Runtime 分层

固定流水线。新能力必须能回答「属于哪一层」。

```text
Input Adapter（text / voice）
        |
        v
Turn Intake（幂等、seq、final）
        |
        v
LLM Parser（text → SpeechAct[]）
        |
        v
Product Understanding
        |
        v
Resolver
        |
        v
Policy（含 Confirm Gate）
        |
        v
Domain Service（开单 / 改单 / 确认）
        |
        v
Domain Event
        |
        v
Outbox
        |
        +----------------+
        |                |
        v                v
     Memory         ERPNext Adapter
     （学习）         （业务系统）
```

| 层 | 职责 | 禁止 |
| --- | --- | --- |
| Input Adapter | 只替换 text 来源与 `reply_text` 播出 | 解析商品、选客户、改口播语义 |
| Turn Intake | 幂等、`seq`、丢弃 non-final | 直连 Runner 绕过字段契约 |
| Parser | **理解语言** → `SpeechAct[]` | 选客户、选 SKU、定价、写 Memory、判断 Confirm |
| Product Understanding | **理解行业货语**（如 八零果 → size=80） | 直接输出 SKU |
| Resolver | 根据**已有 Catalog** 识别实体 | 猜、创建 SKU、写 Memory |
| Policy | **业务裁决**：客户/商品歧义、Confirm Gate、是否询问 | 被 LLM 替代或绕过 |
| Domain Service | 执行开单、改单、确认 | 直接调 ERP API |
| Memory | 从确认后的结构化事件学习 | `user_text` 学习、LLM 直接写 |
| ERPNext Adapter | 消费 Outbox，写入 ERP | 反向把 ERP 表结构泄漏进 Runtime |

Policy 是业务安全边界。**LLM 不能替代 Policy。**

---

## 3. 已完成能力

当前 Runtime 已具备：

- SpeechAct 语言契约
- LLM Parser 默认入口
- ProductUnderstanding
- Resolver
- Policy
- Confirm Gate
- OrderService
- Memory Learning
- Adaptive Memory
- Customer Cold Start
- Workbench
- PostgreSQL Persistence
- Durable Outbox
- Voice Adapter（Input Adapter：ASR final → turns → TTS 念 `reply_text`）

---

## 4. 永久冻结边界

任何新功能不得破坏下列边界。

### Parser

只能理解语言。不能直接生成订单。

### Resolver

只能识别。不能猜。

### Policy

负责裁决。不能被 LLM 绕过。

### Memory

只能从确认后的结构化事件学习。

禁止：

- `user_text` 学习
- LLM 直接写 Memory

### Session

`SalesSession` = 一张订单。

禁止：

- 聊天记录
- 跨订单上下文

### Workbench

管理当天任务。不是 Memory，不是 Agent。

---

## 5. ERPNext 关系

未来接 ERPNext。

正确：

```text
Domain Event → Outbox → ERPNext Adapter → ERPNext
```

错误：

```text
OrderService → 直接调用 ERP API
```

AI Runtime **不依赖** ERPNext 表结构。

当前阶段：**不做 ERP**。Adapter 尚未落地；Outbox 已为它留口。

---

## 6. 当前阶段

当前不是做 ERP。

当前不是做多 Agent。

当前不是做平台。

当前目标：打造一个可靠的行业 AI 员工。

第一个员工：农批 AI 开单员。

---

## 7. 后续所有设计评审必须回答

1. 这个能力属于哪一层？
2. 是否改变 LLM 权限？
3. 是否绕过 Policy？
4. 是否污染 Memory？
5. 是否应该通过 Event 连接？
6. 是否属于 ERPNext Adapter，而不是 Runtime？

如果不确定，**优先保持 Runtime 冻结**。

---

## 8. Sprint 开场模板

禁止只说「做 Sprint X」。

每个 Sprint / PR 开头必须写：

```text
当前遵守 docs/AI_EMPLOYEE_ARCHITECTURE.md。
本 Sprint 只允许修改：<层名>。
禁止修改：<冻结层列表>。
评审六问：见 §7。
```

示例（V0.4 Voice Adapter）：

```text
当前遵守 docs/AI_EMPLOYEE_ARCHITECTURE.md。
本 Sprint 只允许修改：Input Adapter。
禁止修改：Parser / ProductUnderstanding / Resolver / Policy / Confirm Gate /
         OrderService / Memory / Response / Outbox。
```

这样避免：局部功能不断增加，整体架构方向慢慢漂移。
