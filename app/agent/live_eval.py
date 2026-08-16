"""可选 live 评测入口。真实模型只经 LLMTurnParser。默认不发请求。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.agent.evaluation import (
    LanguageBenchmark,
    build_eval_parser,
    live_llm_enabled,
    load_parser_cases,
    report_to_json,
)
from app.agent.llm_client import HttpLlmClient, client_from_env
from app.agent.prompts import PARSER_PROMPT_ID


def run_live_l1(*, out_dir: Path | None = None) -> Path:
    if not live_llm_enabled():
        raise RuntimeError("live eval requires RUN_LIVE_LLM=1 and LLM_API_KEY")
    client = client_from_env()
    if not isinstance(client, HttpLlmClient):
        raise RuntimeError("live eval requires HttpLlmClient")
    parser, capture = build_eval_parser(client)
    dataset_rev, cases = load_parser_cases()
    report = LanguageBenchmark().evaluate(
        cases,
        parser,
        mode="live",
        model=client.model,
        prompt_id=PARSER_PROMPT_ID,
        dataset_rev=dataset_rev,
        capture=capture,
    )
    target_dir = out_dir or Path("docs/eval/runs")
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = target_dir / f"{stamp}-{client.model}-{PARSER_PROMPT_ID}.json"
    path.write_text(json.dumps(report_to_json(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    path = run_live_l1()
    print(path)


if __name__ == "__main__":
    main()
