from __future__ import annotations

from os import environ

from fastapi import APIRouter

from app.api.presence import presence_doc

router = APIRouter(prefix="/v1", tags=["presence"])


@router.get("/presence")
def presence() -> dict:
    port = int(environ.get("CLERK_HTTP_PORT", "8000"))
    return presence_doc(http_port=port)
