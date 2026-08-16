from __future__ import annotations

from typing import Any
from uuid import UUID

from app.entity.session import SalesSession
from app.entity.workbench import WorkbenchShift, project_task


class WorkbenchService:
    """当日销售任务索引。不解析语言，不写 Memory。"""

    def __init__(self) -> None:
        self._shift = WorkbenchShift()

    def snapshot(self) -> dict[str, Any]:
        return {
            "business_date": self._shift.business_date.isoformat(),
            "current_session_id": str(self._shift.current_session_id)
            if self._shift.current_session_id
            else None,
            "tasks": [item.model_dump(mode="json") for item in self._shift.tasks],
        }

    def register(self, session: SalesSession, *, make_current: bool = False) -> None:
        if any(item.session_id == session.session_id for item in self._shift.tasks):
            self.sync(session)
        else:
            self._shift.tasks.append(project_task(session))
        if make_current or self._shift.current_session_id is None:
            self._shift.current_session_id = session.session_id

    def sync(self, session: SalesSession) -> None:
        updated = []
        found = False
        for item in self._shift.tasks:
            if item.session_id != session.session_id:
                updated.append(item)
                continue
            found = True
            updated.append(project_task(session, previous=item))
        if not found:
            updated.append(project_task(session))
        self._shift.tasks = updated

    def set_current(self, session_id: UUID) -> None:
        if not any(item.session_id == session_id for item in self._shift.tasks):
            raise KeyError("task_not_found")
        self._shift.current_session_id = session_id
