from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.api.routers import health, sessions, workbench
from app.bootstrap import AppWorld, build_app_world

STATIC_DIR = Path(__file__).resolve().parent / "api" / "static"
DEMO_PAGE = STATIC_DIR / "index.html"


def create_app(world: AppWorld | None = None) -> FastAPI:
    app = FastAPI(title="ai-order-clerk", version="0.1.0")
    app.state.world = world or build_app_world()
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(workbench.router)

    @app.get("/")
    def demo_shell() -> FileResponse:
        return FileResponse(DEMO_PAGE, media_type="text/html; charset=utf-8")

    @app.get("/static/{path:path}")
    def demo_static(path: str) -> FileResponse:
        target = (STATIC_DIR / path).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            raise HTTPException(status_code=404)
        if not target.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(target)

    return app


app = create_app()
