# ai-order-clerk

Voice-first 农批开单员：老板连续自然语言开单，Agent 维护客户、商品、价格与订单任务上下文。

第一阶段做 Agent 后端核心 + POC 开单壳。Runtime 收口后的可雇版本见 [docs/V1_SALES_CLERK.md](docs/V1_SALES_CLERK.md)：农批 AI 销售开单员 V1。禁止做成 ERP 前端。

需要 **Python 3.12+**（3.9 无法安装）。

电脑上双击 `启动开单.bat`。浏览器会打开今日开单本；手机打开「今日开单」App，会自动连上这台电脑（同一 Wi-Fi）。

开发安装：

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

默认测试走 InMemory。设置 `DATABASE_URL` 后启用 PostgreSQL（同一套 Repository Port，可 Kill & Restart）。测试库可用 `TEST_DATABASE_URL`。

```bash
# DATABASE_URL=postgresql://ubuntu@/ai_clerk?host=/var/run/postgresql
```

打开 http://127.0.0.1:8000/ 。今日开单本：按住说话（或点例子）开李老板的单、改量、好了。口播只展示后端 `reply_text`。自然语言只走 `POST /v1/sessions/{id}/turns`。调试时间线：`http://127.0.0.1:8000/?dev=1`。

老板手机端在 `mobile/`（Flutter 今日开单本）。只调现有 HTTP，不改 Runtime。规格见 [docs/V1_SALES_CLERK_FLUTTER_APP.md](docs/V1_SALES_CLERK_FLUTTER_APP.md)。

## 文档

| 文件 | 说明 |
| --- | --- |
| [docs/AI_EMPLOYEE_ARCHITECTURE.md](docs/AI_EMPLOYEE_ARCHITECTURE.md) | 最高架构约束（分层、冻结、ERP Adapter、Sprint 开场） |
| [docs/DESIGN.md](docs/DESIGN.md) | 农批开单员产品设计细则 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 产品路线 |
| [docs/DOMAIN.md](docs/DOMAIN.md) | 农批业务知识 |
| [docs/AI_RULES.md](docs/AI_RULES.md) | Agent 行为规范 |
| [docs/AI_DEVELOPMENT_GUIDE.md](docs/AI_DEVELOPMENT_GUIDE.md) | Cursor 正式开发 Master Prompt |
| [docs/VALIDATION.md](docs/VALIDATION.md) | 行为迁移实验与 6B 进入条件 |
| [docs/V04_VOICE_ADAPTER.md](docs/V04_VOICE_ADAPTER.md) | V0.4 语音壳设计（Adapter，不改内核） |
| [docs/V05_ERPNEXT_ADAPTER.md](docs/V05_ERPNEXT_ADAPTER.md) | V0.5 ERPNext Write Adapter（Outbox → ERP，不改内核） |
| [docs/V06_ERPNEXT_READ_ADAPTER.md](docs/V06_ERPNEXT_READ_ADAPTER.md) | V0.6 ERPNext Read Adapter 设计（领域查询 → 投影，不改内核） |
| [docs/RUNTIME_FREEZE.md](docs/RUNTIME_FREEZE.md) | v0.x Runtime 冻结清单（Phase 1.5 收口） |
| [docs/SALES_EMPLOYEE_CAPABILITY.md](docs/SALES_EMPLOYEE_CAPABILITY.md) | 第一个商业员工（开单员）能力与三阶段路线 |
| [docs/V1_SALES_CLERK.md](docs/V1_SALES_CLERK.md) | 农批 AI 销售开单员 V1 产品规格（一天六步、必须产品化 / 明确不做） |
| [docs/V1_SALES_CLERK_USER_JOURNEY.md](docs/V1_SALES_CLERK_USER_JOURNEY.md) | 开单员 V1 用户旅程（开门到收摊、今日开单本、产品边界） |
| [docs/V1_SALES_CLERK_WORKBENCH.md](docs/V1_SALES_CLERK_WORKBENCH.md) | 开单员 V1 今日开单本原型（工作台、当前单五态、5 分钟验收） |
| [docs/V1_SALES_CLERK_VERTICAL_SLICE.md](docs/V1_SALES_CLERK_VERTICAL_SLICE.md) | 开单员 V1 垂直切片（一分钟闭环、P0/P1/P2） |
| [docs/V1_SALES_CLERK_PILOT_CHECKLIST.md](docs/V1_SALES_CLERK_PILOT_CHECKLIST.md) | 开单员 V1 Pilot 检查（可靠性、异常、能否进档口） |
| [docs/V1_SALES_CLERK_PILOT_OBSERVATION.md](docs/V1_SALES_CLERK_PILOT_OBSERVATION.md) | 开单员 V1 Pilot 观察（每日记录、失败案例、结束判断） |
| [docs/V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md](docs/V1_SALES_CLERK_PILOT_DATA_BOUNDARY.md) | 开单员 V1 Pilot 数据边界（企业事实切片、缺数据问老板） |
| [docs/V1_SALES_CLERK_PILOT_DATA_ACCESS.md](docs/V1_SALES_CLERK_PILOT_DATA_ACCESS.md) | 开单员 V1 Pilot 数据访问（Adapter 投影进 Runtime，不直查 ERP） |
| [docs/V1_SALES_CLERK_PILOT_ONBOARDING.md](docs/V1_SALES_CLERK_PILOT_ONBOARDING.md) | 开单员 V1 Pilot 接入（空白档口到第一单、扩大或暂停） |
| [docs/V1_SALES_CLERK_PILOT_FEEDBACK_LOOP.md](docs/V1_SALES_CLERK_PILOT_FEEDBACK_LOOP.md) | 开单员 V1 Pilot 反馈闭环（分类、失败模板、V1.1 或继续观察） |
| [docs/V1_SALES_CLERK_PILOT_RUNBOOK.md](docs/V1_SALES_CLERK_PILOT_RUNBOOK.md) | 开单员 V1 Pilot 执行手册（第一档口当天、陪跑、扩大/观察/暂停） |
| [docs/V1_SALES_CLERK_FLUTTER_APP.md](docs/V1_SALES_CLERK_FLUTTER_APP.md) | 开单员 V1 Flutter App（今日开单本、Voice First、档口绑定） |
| [docs/V1_SALES_CLERK_CHINA_ASR.md](docs/V1_SALES_CLERK_CHINA_ASR.md) | 开单员 V1 端侧听写（SenseVoice，不依赖系统听写） |
| [docs/ADR/](docs/ADR/) | 架构决策记录 |
| [.cursorrules](.cursorrules) | AI 辅助开发强制规则 |
