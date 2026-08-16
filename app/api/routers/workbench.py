from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_world
from app.bootstrap import AppWorld

router = APIRouter(prefix="/v1", tags=["workbench"])


class CurrentTaskIn(BaseModel):
    session_id: UUID


@router.get("/workbench")
def get_workbench(world: AppWorld = Depends(get_world)) -> dict:
    return world.workbench.snapshot()


@router.post("/workbench/tasks", status_code=201)
def create_task(world: AppWorld = Depends(get_world)) -> dict:
    session = world.intake.create_session()
    world.workbench.register(session, make_current=True)
    return world.workbench.snapshot()


@router.post("/workbench/current")
def set_current(body: CurrentTaskIn, world: AppWorld = Depends(get_world)) -> dict:
    try:
        world.workbench.set_current(body.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task_not_found") from exc
    return world.workbench.snapshot()
