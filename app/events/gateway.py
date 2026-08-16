from __future__ import annotations

from app.entity.session import SalesSession, TurnResult
from app.events.dispatcher import EventDispatcher
from app.session.runner import SalesSessionRunner


class TurnGateway:
    """装配层：事务 A 提交后 drain。不是 Policy / Parser。"""

    def __init__(self, runner: SalesSessionRunner, dispatcher: EventDispatcher) -> None:
        self._runner = runner
        self._dispatcher = dispatcher

    def handle(self, session: SalesSession, text: str, *, expect_more: bool = False) -> TurnResult:
        self._dispatcher.begin_turn(session)
        try:
            result = self._runner.handle(session, text, expect_more=expect_more)
            self._dispatcher.finish_turn(result.session)
            return result
        except Exception:
            self._dispatcher.abort_turn()
            raise

    def __getattr__(self, name: str):
        return getattr(self._runner, name)
