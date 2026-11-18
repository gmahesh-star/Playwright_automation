"""FastAPI application — lifespan events, CORS, routers, and health check."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import close_db, init_db
from app.api.routes_recorder import router as recorder_router
from app.api.routes_tests import router as tests_router
from app.api.routes_runs import router as runs_router

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Lifespan
# ═══════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown lifecycle."""
    logger.info("Starting Playwright Platform API")
    logger.info("Database: %s", settings.DATABASE_URL.split("@")[-1])
    logger.info("Redis: %s", settings.REDIS_URL)
    logger.info("Artifacts: %s", settings.ARTIFACTS_DIR.resolve())

    # Create tables (dev convenience — use Alembic migrations in prod)
    await init_db()
    logger.info("Database tables ensured")

    yield

    logger.info("Shutting down Playwright Platform API")
    await close_db()


# ═══════════════════════════════════════════════════════════════════════
# App
# ═══════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Playwright Testing Platform",
    description=(
        "Production-grade Web Automation Testing & Recorder Platform. "
        "Record browser interactions, run cross-browser tests, generate code, "
        "and get structured reports — all via a clean async API."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────

app.include_router(recorder_router, prefix="/api")
app.include_router(tests_router, prefix="/api")
app.include_router(runs_router, prefix="/api")

# ── WebSocket routes (mounted at root, NOT under /api prefix) ───────

from app.api.routes_recorder import ws_recorder
from app.api.routes_runs import ws_run_progress

app.websocket("/ws/recorder/{session_id}")(ws_recorder)
app.websocket("/ws/runs/{run_id}")(ws_run_progress)

# ── Static files for artefacts ──────────────────────────────────────

settings.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/artifacts",
    StaticFiles(directory=str(settings.ARTIFACTS_DIR)),
    name="artifacts",
)

# ── Frontend static files (CSS, JS) ────────────────────────────────

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static",
)


# ── Health check ────────────────────────────────────────────────────


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "playwright-platform"}


@app.get("/", tags=["system"])
async def root() -> FileResponse:
    """Serve the frontend SPA."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))
