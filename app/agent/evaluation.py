from __future__ import annotations

import json
import re
import subprocess
import time
from os import environ
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.agent.llm_client import FakeLlmClient, HttpLlmClient, LlmClient
from app.agent.llm_parser import LLMTurnParser
from app.agent.parser import TurnParser
from app.agent.prompts import PARSER_PROMPT_ID, PARSER_SYSTEM_PROMPT
from app.agent.turn_parser import RuleTurnParser
from app.entity.speech import SpeechAct, TurnParse

EvalMode = Literal["unconfigured", "fake", "live"]
Severity = Literal["veto", "fail", "recovered", "pass"]

PARSER_CASES_PATH = Path(__file__).resolve().parents[2] / "docs" / "dataset" / "sales_parser_cases.json"
_RAW_LIMIT = 4000
_ID_KEYS = ("sku_id", "product_id", "customer_id", "node_id", "line_id", "target_line_id")
_SKU_GUESSES = ("红富士80果一级烟台箱装", "红富士80", "烟台箱装", "皇冠梨箱装", "青苹果统货")
_CUSTOMER_GUESSES = ("王强水果店", "王记水果店", "李记果行")
_CONFIRM_PHRASES = ("好了", "就这些", "结了")


class ParserEvaluationCase(BaseModel):
    id: str | None = None
    text: str
    expected_acts: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None
    tag: str | None = None


class ParserEvaluationRecord(BaseModel):
    """单条 Parser 运行记录。"""

    case_id: str | None = None
    text: str
    parser_name: str
    fallback: bool = False
    fallback_reason: str | None = None
    predicted_acts: list[SpeechAct] = Field(default_factory=list)
    expected_acts: list[dict[str, Any]] = Field(default_factory=list)
    match_count: int | None = None
    tag: str | None = None
    taxonomy: str | None = None
    severity: Severity = "pass"
    model_pass: bool = False
    l0_violated: bool = False
    raw: str | None = None


class ParserEvaluationReport(BaseModel):
    records: list[ParserEvaluationRecord] = Field(default_factory=list)
    scored: bool = False
    score: float | None = None
    mode: EvalMode = "unconfigured"
    model: str = ""
    prompt_id: str = PARSER_PROMPT_ID
    dataset_rev: str | None = None
    git_sha: str | None = None
    base_host: str | None = None
    veto: bool = False
    stall_oral_pass_rate: float | None = None
    stall_oral_fallback_rate: float | None = None
    must_not_guess_pass_rate: float | None = None


class CaptureLlmClient:
    """只记录 complete 入参/原文。禁止改 Prompt、禁止附加 Catalog。"""

    def __init__(self, inner: LlmClient) -> None:
        self.inner = inner
        self.last_raw: Any = None
        self.last_system: str | None = None
        self.last_user: str | None = None

    def available(self) -> bool:
        return self.inner.available()

    def complete(self, *, system: str, user: str) -> Any:
        if system != PARSER_SYSTEM_PROMPT:
            raise RuntimeError("eval_prompt_mismatch")
        self.last_system = system
        self.last_user = user
        try:
            raw = self.inner.complete(system=system, user=user)
        except Exception as exc:
            self.last_raw = str(exc)[:_RAW_LIMIT]
            raise
        self.last_raw = raw
        return raw


def live_llm_enabled() -> bool:
    flag = (environ.get("RUN_LIVE_LLM") or "").strip().lower()
    key = (environ.get("LLM_API_KEY") or "").strip()
    return flag in {"1", "true", "yes"} and bool(key)


def load_parser_cases(path: Path | None = None) -> tuple[str, list[ParserEvaluationCase]]:
    payload = json.loads((path or PARSER_CASES_PATH).read_text(encoding="utf-8"))
    cases = [ParserEvaluationCase.model_validate(item) for item in payload["cases"]]
    return str(payload.get("version", "")), cases


def fake_client_from_cases(cases: list[ParserEvaluationCase]) -> FakeLlmClient:
    responses = {case.text: {"acts": case.expected_acts} for case in cases}
    return FakeLlmClient(responses=responses)


class LanguageBenchmark:
    """L1 + L0。走 LLMTurnParser，不进 Resolver / Policy / Memory。"""

    def evaluate(
        self,
        cases: list[ParserEvaluationCase],
        parser: TurnParser,
        *,
        mode: EvalMode,
        model: str = "",
        prompt_id: str = PARSER_PROMPT_ID,
        dataset_rev: str | None = None,
        capture: CaptureLlmClient | None = None,
    ) -> ParserEvaluationReport:
        records: list[ParserEvaluationRecord] = []
        pause = _live_http_pause(mode, capture)
        for index, case in enumerate(cases):
            if pause > 0 and index > 0:
                time.sleep(pause)
            parsed = parser.parse(case.text)
            raw = _stringify_raw(capture.last_raw) if capture is not None else None
            if capture is not None:
                capture.last_raw = None
            records.append(_score_case(case, parsed, raw=raw, mode=mode))
        stall = [row for row in records if row.tag == "stall_oral"]
        guess = [row for row in records if row.tag == "must_not_guess"]
        stall_pass = [row for row in stall if row.model_pass]
        stall_fb = [row for row in stall if row.fallback]
        guess_ok = [row for row in guess if not row.l0_violated and row.model_pass]
        veto = any(row.severity == "veto" for row in records)
        scored = mode == "live"
        score = None
        if scored and stall:
            score = len(stall_pass) / len(stall)
        return ParserEvaluationReport(
            records=records,
            scored=scored,
            score=score,
            mode=mode,
            model=model,
            prompt_id=prompt_id,
            dataset_rev=dataset_rev,
            git_sha=_git_sha(),
            base_host=_base_host(parser, capture),
            veto=veto,
            stall_oral_pass_rate=(len(stall_pass) / len(stall)) if stall else None,
            stall_oral_fallback_rate=(len(stall_fb) / len(stall)) if stall else None,
            must_not_guess_pass_rate=(len(guess_ok) / len(guess)) if guess else None,
        )


def build_eval_parser(client: LlmClient) -> tuple[LLMTurnParser, CaptureLlmClient]:
    capture = CaptureLlmClient(client)
    return LLMTurnParser(client=capture, fallback=RuleTurnParser()), capture


def report_to_json(report: ParserEvaluationReport) -> dict[str, Any]:
    return report.model_dump(mode="json")


def _score_case(
    case: ParserEvaluationCase,
    parsed: TurnParse,
    *,
    raw: str | None,
    mode: EvalMode,
) -> ParserEvaluationRecord:
    predicted = list(parsed.acts)
    expected = list(case.expected_acts)
    matched = _acts_match(predicted, expected)
    l0, l0_tax = _l0_scan(case.text, predicted, raw)
    taxonomy, severity, model_pass = _classify(
        case,
        parsed,
        matched=matched,
        l0=l0,
        l0_tax=l0_tax,
        mode=mode,
        predicted=predicted,
        expected=expected,
    )
    return ParserEvaluationRecord(
        case_id=case.id,
        text=case.text,
        parser_name=parsed.parser_name,
        fallback=parsed.fallback,
        fallback_reason=parsed.fallback_reason,
        predicted_acts=predicted,
        expected_acts=expected,
        match_count=sum(
            1
            for got, exp in zip(predicted, expected)
            if _types_compatible(got.type, exp.get("type"))
        )
        if expected
        else 0,
        tag=case.tag,
        taxonomy=taxonomy,
        severity=severity,
        model_pass=model_pass,
        l0_violated=l0,
        raw=(raw[:_RAW_LIMIT] if raw else None),
    )


def _classify(
    case: ParserEvaluationCase,
    parsed: TurnParse,
    *,
    matched: bool,
    l0: bool,
    l0_tax: str | None,
    mode: EvalMode,
    predicted: list[SpeechAct],
    expected: list[dict[str, Any]],
) -> tuple[str | None, Severity, bool]:
    tag = case.tag or ""
    if l0:
        return l0_tax or "l0_violation", "veto", False
    if parsed.fallback:
        if tag == "canonical" and matched:
            return "fallback_recovered", "recovered", False
        return "fallback_to_rule", "fail", False
    if not matched:
        tax = _mismatch_taxonomy(case, predicted, expected)
        return tax, "fail", False
    model_pass = parsed.parser_name == "llm" and not parsed.fallback
    return None, "pass", model_pass


def _mismatch_taxonomy(
    case: ParserEvaluationCase,
    predicted: list[SpeechAct],
    expected: list[dict[str, Any]],
) -> str:
    if len(predicted) < len(expected):
        return "dropped_act"
    if len(predicted) > len(expected):
        if any(act.type == "confirm_order" for act in predicted) and not any(
            item.get("type") == "confirm_order" for item in expected
        ):
            return "judged_confirm"
        return "extra_act"
    for got, exp in zip(predicted, expected):
        exp_slots = exp.get("slots") or {}
        if exp.get("type") == "refine_spec" and exp_slots.get("spec_mention"):
            if got.slots.get("product_mention") and not got.slots.get("spec_mention"):
                return "spec_as_product"
        if not _types_compatible(got.type, exp.get("type")):
            if got.type == "confirm_order":
                return "judged_confirm"
            return "dropped_act"
    return "dropped_act"


_LINE_WRITE_TYPES = frozenset({"set_line", "add_line"})


def _types_compatible(got: str, expected: object) -> bool:
    if got == expected:
        return True
    return {got, expected} <= _LINE_WRITE_TYPES


def _acts_match(predicted: list[SpeechAct], expected: list[dict[str, Any]]) -> bool:
    if len(predicted) != len(expected):
        return False
    for got, exp in zip(predicted, expected):
        if not _types_compatible(got.type, exp.get("type")):
            return False
        for key, value in (exp.get("slots") or {}).items():
            if got.slots.get(key) != value:
                return False
    return True


def _l0_scan(text: str, predicted: list[SpeechAct], raw: str | None) -> tuple[bool, str | None]:
    blob = " ".join(_slot_blob(act) for act in predicted)
    raw_text = raw or ""
    haystack = f"{blob}\n{raw_text}"
    for key in _ID_KEYS:
        if re.search(rf'"{key}"\s*:', raw_text) or any(key in act.slots for act in predicted):
            return True, "l0_violation"
    for name in _SKU_GUESSES:
        if name in haystack:
            return True, "guessed_sku"
    for name in _CUSTOMER_GUESSES:
        if name in haystack:
            return True, "guessed_customer"
    if _invented_number(text, predicted):
        return True, "invented_number"
    if any(act.type == "confirm_order" for act in predicted) and not any(p in text for p in _CONFIRM_PHRASES):
        return True, "judged_confirm"
    return False, None


def _invented_number(text: str, predicted: list[SpeechAct]) -> bool:
    for act in predicted:
        for key in ("qty", "unit_price"):
            value = act.slots.get(key)
            if value is None:
                continue
            token = str(value)
            if token in text:
                continue
            if _cn_contains_number(text, value):
                continue
            return True
    return False


_CN_NUM = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _cn_contains_number(text: str, value: object) -> bool:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if number == 60 and ("六十" in text or "60" in text):
        return True
    if number == 2 and ("两" in text or "二" in text or "2" in text):
        return True
    if number == 3 and ("三" in text or "3" in text):
        return True
    for char, digit in _CN_NUM.items():
        if digit == number and char in text:
            return True
    return False


def _slot_blob(act: SpeechAct) -> str:
    return json.dumps(act.slots, ensure_ascii=False)


def _stringify_raw(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    return json.dumps(raw, ensure_ascii=False)


def _live_http_pause(mode: EvalMode, capture: CaptureLlmClient | None) -> float:
    if mode != "live" or capture is None:
        return 0.0
    client = capture.inner
    if isinstance(client, CaptureLlmClient):
        client = client.inner
    if not isinstance(client, HttpLlmClient):
        return 0.0
    raw = (environ.get("LLM_EVAL_PAUSE") or "0.25").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.25


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _base_host(parser: TurnParser, capture: CaptureLlmClient | None) -> str | None:
    client: LlmClient | None = None
    if capture is not None:
        client = capture.inner
    elif isinstance(parser, LLMTurnParser):
        client = getattr(parser, "_client", None)
    if isinstance(client, CaptureLlmClient):
        client = client.inner
    if isinstance(client, HttpLlmClient):
        return urlparse(client.base_url).netloc or None
    return None
