"""V0.3D Runtime Admission 入口。只驱动现网 Runtime，不改 Prompt / Resolver / Policy / Memory。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from os import environ
from pathlib import Path
from typing import Any, Literal

from app.agent.admission_scripts import (
    ScriptSpec,
    StepContext,
    StepFailure,
    admission_scripts,
    fail_fallback,
    fail_l0,
    fake_responses,
    queries_from_acts,
)
from app.agent.evaluation import CaptureLlmClient, _git_sha, _stringify_raw, live_llm_enabled
from app.agent.llm_client import FakeLlmClient, HttpLlmClient, LlmClient, client_from_env
from app.agent.llm_parser import LLMTurnParser
from app.agent.parser import TurnParser
from app.agent.prompts import PARSER_PROMPT_ID
from app.agent.turn_parser import RuleTurnParser
from app.bootstrap import build_world, new_session
from app.entity.speech import SpeechAct, TurnParse

EvalMode = Literal["fake", "live"]
Decision = Literal["A", "B", "C"]
RUNS_DIR = Path("docs/eval/runs")
REPORT_NAME = "runtime_admission_report.md"


class RecordingParser:
    def __init__(self, inner: TurnParser) -> None:
        self.inner = inner
        self.last: TurnParse | None = None

    def parse(self, text: str) -> TurnParse:
        self.last = self.inner.parse(text)
        return self.last


@dataclass
class StepRecord:
    script_id: str
    step: int
    text: str
    parser_name: str
    fallback: bool
    fallback_reason: str | None
    acts: list[dict[str, Any]]
    queries: list[dict[str, Any]]
    issues: list[str]
    confirm_ok: bool
    draft: dict[str, Any]
    raw: str | None
    failures: list[StepFailure] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass
class ScriptResult:
    script_id: str
    title: str
    records: list[StepRecord]
    semantic: dict[str, Any]

    @property
    def passed(self) -> bool:
        return all(row.passed for row in self.records)


@dataclass
class AdmissionReport:
    mode: EvalMode
    model: str
    prompt_id: str
    dataset_rev: str
    git_sha: str | None
    repeats: int
    scripts: list[list[ScriptResult]]
    decision: Decision
    decision_reason: str

    @property
    def latest(self) -> list[ScriptResult]:
        return self.scripts[-1] if self.scripts else []


def _act_dump(act: SpeechAct) -> dict[str, Any]:
    return {"type": act.type, "slots": dict(act.slots)}


def _draft_snapshot(session: Any) -> dict[str, Any]:
    customer = session.draft.customer
    return {
        "customer_id": str(customer.id) if customer and customer.id else None,
        "customer_name": customer.name if customer else None,
        "status": session.draft.status,
        "lines": [
            {
                "line_id": str(line.line_id),
                "sku_id": str(line.product_sku_id) if line.product_sku_id else None,
                "node": line.mention.matched_node.name if line.mention.matched_node else None,
                "raw": line.mention.raw,
                "qty": str(line.qty.value),
                "uom": line.qty.uom,
                "filled_from": line.mention.filled_from,
            }
            for line in session.draft.lines
        ],
    }


def _semantic_snapshot(session: Any, *, confirm_ok: bool) -> dict[str, Any]:
    customer = session.draft.customer
    return {
        "customer_id": str(customer.id) if customer and customer.id else None,
        "confirm_ok": confirm_ok,
        "status": session.draft.status,
        "lines": [
            {
                "sku_id": str(line.product_sku_id) if line.product_sku_id else None,
                "node": line.mention.matched_node.name if line.mention.matched_node else None,
                "qty": str(line.qty.value),
                "uom": line.qty.uom,
            }
            for line in session.draft.lines
        ],
    }


def _build_parser(mode: EvalMode, client: LlmClient) -> tuple[RecordingParser, CaptureLlmClient | None]:
    capture: CaptureLlmClient | None = None
    inner: TurnParser
    if mode == "live":
        capture = CaptureLlmClient(client)
        inner = LLMTurnParser(client=capture, fallback=RuleTurnParser())
    else:
        inner = LLMTurnParser(client=client, fallback=RuleTurnParser())
    return RecordingParser(inner), capture


def run_script(
    spec: ScriptSpec,
    parser: RecordingParser,
    catalog: Any,
    runner: Any,
    *,
    capture: CaptureLlmClient | None,
) -> ScriptResult:
    session = new_session()
    nodes_before = {node.id for node in catalog.list_nodes()}
    aliases_before = list(catalog.aliases.snapshot())
    markers: dict[str, Any] = {}
    records: list[StepRecord] = []
    last_confirm = False
    for index, step in enumerate(spec.steps, start=1):
        result = runner.handle(session, step.text, expect_more=step.expect_more)
        parsed = parser.last or TurnParse(raw_text=step.text, acts=list(result.acts), parser_name="unknown")
        raw = _stringify_raw(capture.last_raw) if capture is not None else None
        if capture is not None:
            capture.last_raw = None
        ctx = StepContext(
            session=session,
            result=result,
            parsed=parsed,
            catalog=catalog,
            nodes_before=nodes_before,
            aliases_before=aliases_before,
            markers=markers,
        )
        failures = fail_l0(ctx) + fail_fallback(ctx)
        for check in step.checks:
            failures.extend(check(ctx))
        last_confirm = bool(result.verdict.confirm_ok)
        records.append(
            StepRecord(
                script_id=spec.script_id,
                step=index,
                text=step.text,
                parser_name=parsed.parser_name,
                fallback=parsed.fallback,
                fallback_reason=parsed.fallback_reason,
                acts=[_act_dump(act) for act in parsed.acts],
                queries=queries_from_acts(list(parsed.acts)),
                issues=[item.code for item in result.verdict.issues],
                confirm_ok=last_confirm,
                draft=_draft_snapshot(session),
                raw=(raw[:2000] if raw else None),
                failures=failures,
            )
        )
    return ScriptResult(spec.script_id, spec.title, records, _semantic_snapshot(session, confirm_ok=last_confirm))


def run_admission(*, mode: EvalMode, repeats: int = 1, client: LlmClient | None = None) -> AdmissionReport:
    if mode == "live":
        if not live_llm_enabled():
            raise RuntimeError("live admission requires RUN_LIVE_LLM=1 and LLM_API_KEY")
        llm = client or client_from_env()
        if not isinstance(llm, HttpLlmClient):
            raise RuntimeError("live admission requires HttpLlmClient")
        model = llm.model
    else:
        llm = client or FakeLlmClient(responses=fake_responses())
        model = "fake"
    runs: list[list[ScriptResult]] = []
    pause = 0.0
    if mode == "live":
        try:
            pause = max(0.0, float((environ.get("LLM_EVAL_PAUSE") or "0.25").strip()))
        except ValueError:
            pause = 0.25
    for _repeat in range(repeats):
        parser, capture = _build_parser(mode, llm)
        runner, _events, catalog = build_world(parser=parser)
        batch: list[ScriptResult] = []
        for spec in admission_scripts():
            if pause and batch:
                time.sleep(pause)
            batch.append(run_script(spec, parser, catalog, runner, capture=capture))
        runs.append(batch)
    decision, reason = decide(mode, runs)
    return AdmissionReport(
        mode=mode,
        model=model,
        prompt_id=PARSER_PROMPT_ID,
        dataset_rev="g1-g4.v1",
        git_sha=_git_sha(),
        repeats=repeats,
        scripts=runs,
        decision=decision,
        decision_reason=reason,
    )


def _named(batch: list[ScriptResult], script_id: str) -> ScriptResult | None:
    return next((item for item in batch if item.script_id == script_id), None)


def g4_passed(batch: list[ScriptResult]) -> bool:
    return all(item.passed for item in batch if item.script_id.startswith("G4"))


def decide(mode: EvalMode, runs: list[list[ScriptResult]]) -> tuple[Decision, str]:
    if not runs:
        return "B", "没有跑出任何脚本"
    latest = runs[-1]
    taxonomies = [fail.taxonomy for script in latest for row in script.records for fail in row.failures]
    g1, g2, g3 = _named(latest, "G1"), _named(latest, "G2"), _named(latest, "G3")
    all_pass = bool(g1 and g1.passed and g2 and g2.passed and g3 and g3.passed and g4_passed(latest))
    stable = True
    if len(runs) >= 2:
        first = {item.script_id: item.semantic for item in runs[0]}
        stable = all({item.script_id: item.semantic for item in batch} == first for batch in runs[1:])
    if any(tax in {"guessed_sku", "guessed_customer", "confirm_violation"} for tax in taxonomies):
        return "B", "出现危险行为（猜 SKU/客户或确认闸门被绕过），LLM 不能作为默认入口"
    if mode != "live":
        if all_pass and stable:
            return "B", "Fake 金脚本绿，只证明 Runtime 在正确 SpeechAct 下安全；未跑 live 不得选 A"
        return "B", "Fake 金脚本未全绿"
    if not all_pass:
        if any(tax in {"wrong_act", "fallback", "spec_lost", "lost_focus"} for tax in taxonomies):
            return "C", "真模型驱动失败主要在语言抽取或落行，需改 Prompt 后重评；本阶段不改 Prompt"
        return "B", "真模型未能稳定驱动 Runtime"
    if not stable:
        return "B", "三轮草稿快照不一致"
    return "A", "G1–G4 真 Parser 驱动 Runtime 通过，且三轮快照一致"


def render_report(report: AdmissionReport) -> str:
    latest = report.latest
    g1, g2, g3 = _named(latest, "G1"), _named(latest, "G2"), _named(latest, "G3")
    lines = [
        "# Runtime Admission Report",
        "",
        "## 环境",
        "",
        f"mode: {report.mode}",
        f"model: {report.model}",
        f"prompt_id: {report.prompt_id}",
        f"dataset_rev: {report.dataset_rev}",
        f"git_sha: {report.git_sha or ''}",
        f"repeats: {report.repeats}",
        "",
        "## L1结果",
        "",
        "已有 live：qwen3.7-plus + parser.v4，veto=false，must_not_guess=1.0，stall_oral=1.0，fallback_rate=0。",
        "",
        "## Runtime结果",
        "",
        f"G1: {'pass' if g1 and g1.passed else 'fail'}",
        f"G2: {'pass' if g2 and g2.passed else 'fail'}",
        f"G3: {'pass' if g3 and g3.passed else 'fail'}",
        f"G4: {'pass' if g4_passed(latest) else 'fail'}",
        "",
        "## Failure taxonomy",
        "",
    ]
    failures = [
        f"- {row.script_id} step{row.step} `{row.text}` [{fail.taxonomy}] {fail.message}"
        for script in latest
        for row in script.records
        for fail in row.failures
    ]
    lines.extend(failures or ["- （无）"])
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"{report.decision}: {report.decision_reason}",
            "",
            "A: LLM Parser 可进入默认运行路径",
            "B: LLM仅实验，不作为默认",
            "C: 需要调整prompt后重新评估",
            "",
            "## 逐步记录",
            "",
        ]
    )
    for script in latest:
        lines.append(f"### {script.script_id} {script.title} ({'pass' if script.passed else 'fail'})")
        lines.append("")
        for row in script.records:
            status = "pass" if row.passed else "fail"
            lines.append(
                f"- step {row.step} `{row.text}` parser={row.parser_name} fallback={row.fallback} confirm_ok={row.confirm_ok} {status}"
            )
            lines.append(f"  acts: {json.dumps(row.acts, ensure_ascii=False)}")
            if row.queries:
                lines.append(f"  queries: {json.dumps(row.queries, ensure_ascii=False)}")
            lines.append(f"  issues: {row.issues}")
            lines.append(f"  draft: {json.dumps(row.draft, ensure_ascii=False)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(report: AdmissionReport, *, out_dir: Path | None = None) -> Path:
    target = out_dir or RUNS_DIR
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stamped = target / f"{stamp}-{report.mode}-{report.model}-{report.prompt_id}-runtime-admission.md"
    body = render_report(report)
    stamped.write_text(body, encoding="utf-8")
    latest = target / REPORT_NAME
    latest.write_text(body, encoding="utf-8")
    return latest


def main() -> None:
    mode: EvalMode = "live" if live_llm_enabled() else "fake"
    repeats = 3 if mode == "live" else 1
    report = run_admission(mode=mode, repeats=repeats)
    path = write_report(report)
    print(path)
    print(report.decision, report.decision_reason)


if __name__ == "__main__":
    main()
