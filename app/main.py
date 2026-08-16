from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routers import health, sessions
from app.bootstrap import AppWorld, build_app_world

DEMO_PAGE = Path(__file__).resolve().parent / "api" / "static" / "index.html"


def create_app(world: AppWorld | None = None) -> FastAPI:
    app = FastAPI(title="ai-order-clerk", version="0.1.0")
    app.state.world = world or build_app_world()
    app.include_router(health.router)
    app.include_router(sessions.router)

    @app.get("/")
    def demo_shell() -> FileResponse:
        return FileResponse(DEMO_PAGE, media_type="text/html; charset=utf-8")

    return app


app = create_app()
