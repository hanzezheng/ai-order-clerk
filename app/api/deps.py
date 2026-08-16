from __future__ import annotations

from fastapi import Request

from app.bootstrap import AppWorld


def get_world(request: Request) -> AppWorld:
    return request.app.state.world
