from __future__ import annotations

from typing import Any
from uuid import UUID

from app.entity.session import SalesSession
from app.entity.workbench import WorkbenchShift, project_task
from app.services.ports import WorkbenchRepository


class WorkbenchService:
    """当日销售任务索引。不解析语言，不写 Memory。"""

    def __init__(self, repo: WorkbenchRepository) -> None:
        self._repo = repo

    def snapshot(self) -> dict[str, Any]:
        shift = self._repo.get_shift()
        return {
            "business_date": shift.business_date.isoformat(),
            "current_session_id": str(shift.current_session_id) if shift.current_session_id else None,
            "tasks": [item.model_dump(mode="json") for item in shift.tasks],
        }

    def register(self, session: SalesSession, *, make_current: bool = False) -> None:
        shift = self._repo.get_shift()
        if any(item.session_id == session.session_id for item in shift.tasks):
            self._sync_shift(shift, session)
        else:
            shift.tasks.append(project_task(session))
        if make_current or shift.current_session_id is None:
            shift.current_session_id = session.session_id
        self._repo.save_shift(shift)

    def sync(self, session: SalesSession) -> None:
        shift = self._repo.get_shift()
        self._sync_shift(shift, session)
        self._repo.save_shift(shift)

    def set_current(self, session_id: UUID) -> None:
        shift = self._repo.get_shift()
        if not any(item.session_id == session_id for item in shift.tasks):
            raise KeyError("task_not_found")
        shift.current_session_id = session_id
        self._repo.save_shift(shift)

    def _sync_shift(self, shift: WorkbenchShift, session: SalesSession) -> None:
        updated = []
        found = False
        for item in shift.tasks:
            if item.session_id != session.session_id:
                updated.append(item)
                continue
            found = True
            updated.append(project_task(session, previous=item))
        if not found:
            updated.append(project_task(session))
        shift.tasks = updated
