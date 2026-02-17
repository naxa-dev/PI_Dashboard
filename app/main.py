"""
Entry point for the FastAPI application using sqlite backend.

Initialises the database and registers routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from .db import init_db
from .routers import admin_router, dashboard_router, projects_router, events_router


def create_app() -> FastAPI:
    # Initialize the SQLite database schema
    init_db()
    app = FastAPI(title="AX Dashboard", description="AX 과제 관리/대시보드")

    # -----------------------------------------------------
    # CORS (for HTML/JS frontends on a different origin)
    # - Same-origin에서는 영향 없음
    # - 운영 환경에서는 AX_DASHBOARD_CORS_ORIGINS를 명시 권장
    #   예) "https://ax.company.com,https://intranet.company.com"
    # -----------------------------------------------------
    raw = os.getenv("AX_DASHBOARD_CORS_ORIGINS", "*")
    allow_origins = [o.strip() for o in raw.split(",") if o.strip()] if raw != "*" else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Determine the base directory of this file (app directory)
    base_dir = Path(__file__).resolve().parent
    # Mount static assets using absolute path
    static_path = base_dir / "static"
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    # Include routers
    app.include_router(dashboard_router)
    app.include_router(admin_router)
    app.include_router(projects_router)
    app.include_router(events_router)
    app.include_router(events_router)

    @app.get("/.well-known/appspecific/com.chrome.devtools.json")
    def chrome_devtools_manifest():
        return {}

    return app


app = create_app()