from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.evaluation import live_llm_enabled
from app.agent.prompts import PARSER_PROMPT_ID
from app.agent.runtime_admission import decide, render_report, run_admission, write_report
from app.database.memory import FUJI80, WANG_JI


def test_fake_g1_g4_pass_and_decision_is_not_a():
    report = run_admission(mode="fake", repeats=1)
    latest = {item.script_id: item for item in report.latest}
    assert latest["G1"].passed
    assert latest["G2"].passed
    assert latest["G3"].passed
    assert all(item.passed for key, item in latest.items() if key.startswith("G4"))
    apple = latest["G1"].semantic["lines"][0]
    assert apple["sku_id"] == str(FUJI80)
    assert latest["G1"].semantic["customer_id"] == str(WANG_JI)
    assert latest["G1"].semantic["confirm_ok"] is True
    assert latest["G3"].semantic["confirm_ok"] is False
    assert report.decision == "B"
    assert report.prompt_id == PARSER_PROMPT_ID
    assert "未跑 live" in report.decision_reason


def test_fake_three_repeats_are_stable():
    report = run_admission(mode="fake", repeats=3)
    first = {item.script_id: item.semantic for item in report.scripts[0]}
    for batch in report.scripts[1:]:
        assert {item.script_id: item.semantic for item in batch} == first
    assert decide("fake", report.scripts)[0] == "B"


def test_report_lists_g_results_and_writes_markdown(tmp_path: Path):
    report = run_admission(mode="fake", repeats=1)
    text = render_report(report)
    assert "G1: pass" in text
    assert "G2: pass" in text
    assert "G3: pass" in text
    assert "G4: pass" in text
    assert "Decision" in text
    path = write_report(report, out_dir=tmp_path)
    assert path.name == "runtime_admission_report.md"
    assert "parser.v4" in path.read_text(encoding="utf-8")


def test_live_admission_requires_explicit_switch(monkeypatch):
    monkeypatch.delenv("RUN_LIVE_LLM", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert live_llm_enabled() is False
    with pytest.raises(RuntimeError, match="live admission"):
        run_admission(mode="live")


def test_admission_does_not_redefine_confirm_gate():
    text = Path(__file__).resolve().parents[1].joinpath("agent/runtime_admission.py").read_text(encoding="utf-8")
    scripts = Path(__file__).resolve().parents[1].joinpath("agent/admission_scripts.py").read_text(encoding="utf-8")
    assert "def confirm_gate" not in text + scripts


def test_bootstrap_does_not_import_sqlalchemy_at_module_level():
    bootstrap = Path(__file__).resolve().parents[1].joinpath("bootstrap.py").read_text(encoding="utf-8")
    admission = Path(__file__).resolve().parents[1].joinpath("agent/runtime_admission.py").read_text(encoding="utf-8")
    assert "from sqlalchemy" not in bootstrap
    assert "import sqlalchemy" not in bootstrap
    assert "build_world" not in admission
    assert "build_app_world" not in admission


def test_admission_stays_in_memory_even_if_database_url_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/ai_clerk")
    report = run_admission(mode="fake", repeats=1)
    latest = {item.script_id: item for item in report.latest}
    assert latest["G1"].passed
    assert latest["G1"].semantic["customer_id"] == str(WANG_JI)
