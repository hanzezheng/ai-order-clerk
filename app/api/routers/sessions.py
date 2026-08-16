from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_world
from app.api.schemas import TurnIn
from app.bootstrap import AppWorld
from app.session.intake import IntakeError, TurnCommand

router = APIRouter(prefix="/v1", tags=["sessions"])


@router.post("/sessions", status_code=201)
def create_session(world: AppWorld = Depends(get_world)) -> dict:
    session = world.intake.create_session()
    return world.intake.snapshot(session)


@router.get("/sessions/{session_id}")
def get_session(session_id: UUID, world: AppWorld = Depends(get_world)) -> dict:
    try:
        session = world.intake.get_session(session_id)
    except IntakeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    return world.intake.snapshot(session)


@router.post("/sessions/{session_id}/turns")
def post_turn(session_id: UUID, body: TurnIn, world: AppWorld = Depends(get_world)) -> dict:
    command = TurnCommand(
        text=body.text,
        source=body.source,
        utterance_id=body.utterance_id,
        seq=body.seq,
        is_final=body.is_final,
        expect_more=body.expect_more,
    )
    try:
        return world.intake.handle(session_id, command)
    except IntakeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
