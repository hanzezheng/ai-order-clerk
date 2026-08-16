运行产物目录。评测 JSON 与 `runtime_admission_report.md` 不进 git。

- L1：`RUN_LIVE_LLM=1` 且配置 `LLM_API_KEY` 后执行 `python3 -m app.agent.live_eval`
- L4：同一环境执行 `python3 -m app.agent.runtime_admission`
