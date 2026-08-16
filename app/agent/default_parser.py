from __future__ import annotations

from app.agent.llm_client import client_from_env
from app.agent.llm_parser import LLMTurnParser
from app.agent.parser import TurnParser
from app.agent.turn_parser import RuleTurnParser


def build_default_parser() -> TurnParser:
    """默认语言入口：LLM 外壳 + 规则兜底。无配置不发请求。"""
    return LLMTurnParser(client=client_from_env(), fallback=RuleTurnParser())
