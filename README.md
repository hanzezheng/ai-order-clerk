# ai-order-clerk

Voice-first 农批开单员：老板连续自然语言开单，Agent 维护客户、商品、价格与订单任务上下文。

第一阶段做 Agent 后端核心 + V1 最小开单壳：不接 ERP，禁止做成 ERP 前端。

需要 **Python 3.12+**（3.9 无法安装）。

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开 http://127.0.0.1:8000/ 。先说「开李老板的单」，再报货，最后说「好了」。口播只展示后端 `reply_text`。自然语言只走 `POST /v1/sessions/{id}/turns`。调试时间线：`http://127.0.0.1:8000/?dev=1`。

## 文档

| 文件 | 说明 |
| --- | --- |
| [docs/DESIGN.md](docs/DESIGN.md) | 最高设计依据 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 产品路线 |
| [docs/DOMAIN.md](docs/DOMAIN.md) | 农批业务知识 |
| [docs/AI_RULES.md](docs/AI_RULES.md) | Agent 行为规范 |
| [docs/AI_DEVELOPMENT_GUIDE.md](docs/AI_DEVELOPMENT_GUIDE.md) | Cursor 正式开发 Master Prompt |
| [docs/ADR/](docs/ADR/) | 架构决策记录 |
| [.cursorrules](.cursorrules) | AI 辅助开发强制规则 |
