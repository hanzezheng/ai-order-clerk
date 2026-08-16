from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent.evaluation import live_llm_enabled
from app.agent.live_eval import run_live_l1
from app.agent.llm_client import HttpLlmClient, client_from_env
from app.agent.prompts import PARSER_PROMPT_ID

pytestmark = pytest.mark.live_llm


@pytest.mark.skipif(not live_llm_enabled(), reason="live LLM eval requires RUN_LIVE_LLM=1 and LLM_API_KEY")
def test_live_l1_writes_report_and_rejects_l0_veto(tmp_path: Path):
    client = client_from_env()
    assert isinstance(client, HttpLlmClient)
    path = run_live_l1(out_dir=tmp_path)
    blob = json.loads(path.read_text(encoding="utf-8"))
    assert blob["mode"] == "live"
    assert blob["scored"] is True
    assert blob["prompt_id"] == PARSER_PROMPT_ID
    assert blob["model"] == client.model
    assert blob["veto"] is False
    for row in blob["records"]:
        assert "fallback_reason" in row
        assert "taxonomy" in row
        assert "severity" in row
        assert row["severity"] != "veto"
