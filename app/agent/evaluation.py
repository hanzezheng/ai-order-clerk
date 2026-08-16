from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.agent.parser import TurnParser
from app.entity.speech import SpeechAct


class ParserEvaluationCase(BaseModel):
    id: str | None = None
    text: str
    expected_acts: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None


class ParserEvaluationRecord(BaseModel):
    """单条 Parser 运行记录。评分字段预留，当前不打分。"""

    case_id: str | None = None
    text: str
    parser_name: str
    fallback: bool = False
    fallback_reason: str | None = None
    predicted_acts: list[SpeechAct] = Field(default_factory=list)
    expected_acts: list[dict[str, Any]] = Field(default_factory=list)
    match_count: int | None = None


class ParserEvaluationReport(BaseModel):
    records: list[ParserEvaluationRecord] = Field(default_factory=list)
    scored: bool = False
    score: float | None = None


class ParserEvaluator(Protocol):
    """预留：未来对 GPT / Claude / 本地模型评分。本阶段不实现。"""

    def evaluate(
        self,
        cases: list[ParserEvaluationCase],
        parser: TurnParser,
    ) -> ParserEvaluationReport: ...
