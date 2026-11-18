"""Routes for triggering test runs, fetching reports, webhooks, and WebSocket progress streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from arq.connections import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory, get_session
from app.models.test_models import RunStatus, TestRun, TestSuite
from app.schemas.test_schemas import (
    JUnitTestReport,
    TestCaseResult,
    TestRunCreate,
    TestRunOut,
    WebhookTriggerResponse,
)
from app.services.storage import StorageService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runs"])

# ── Redis pool (lazy singleton) ─────────────────────────────────────

_arq_pool: ArqRedis | None = None
_redis_available: bool | None = None


async def _get_arq_pool() -> ArqRedis | None:
    """Try to connect to Redis. Returns None if Redis is not available."""
    global _arq_pool, _redis_available
    if _redis_available is False:
        return None
    if _arq_pool is not None:
        return _arq_pool
    try:
        base_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        fast_settings = RedisSettings(
            host=base_settings.host,
            port=base_settings.port,
            database=base_settings.database,
            password=base_settings.password,
            conn_retries=1,
            conn_timeout=2,
        )
        _arq_pool = await create_pool(fast_settings)
        _redis_available = True
        return _arq_pool
    except Exception as exc:
        logger.warning("Redis not available (%s) — runs will execute in-process", exc)
        _redis_available = False
        return None


async def _run_in_process(run_id: str) -> None:
    """Execute a test run directly in the FastAPI process (no Redis needed)."""
    from app.workers.tasks import execute_test_run
    try:
        await execute_test_run({"redis": _FakeRedis()}, run_id)
    except Exception as exc:
        logger.exception("In-process run %s failed: %s", run_id, exc)


class _FakeRedis:
    """Minimal stub so the worker task doesn't crash when publishing to Redis."""
    async def publish(self, channel: str, message: str) -> None:
        pass  # silently discard pub/sub messages when Redis is absent


# ═══════════════════════════════════════════════════════════════════════
# Trigger runs
# ═══════════════════════════════════════════════════════════════════════


@router.post("/runs", response_model=TestRunOut, status_code=status.HTTP_201_CREATED)
async def trigger_run(
    body: TestRunCreate, session: AsyncSession = Depends(get_session)
) -> TestRunOut:
    """Create a new test run and queue it for execution.

    If Redis is available, the run is queued via ARQ for background execution.
    If Redis is NOT available, the run executes directly in an asyncio background task.
    """
    suite = await session.get(TestSuite, body.suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")

    run = TestRun(
        suite_id=body.suite_id,
        browser=body.browser.value,
        status=RunStatus.PENDING,
        trigger_source=body.trigger_source,
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)

    # Try Redis/ARQ first; fall back to in-process execution
    pool = await _get_arq_pool()
    if pool is not None:
        await pool.enqueue_job("execute_test_run", str(run.id))
        logger.info("Run %s enqueued via ARQ", run.id)
    else:
        asyncio.create_task(_run_in_process(str(run.id)))
        logger.info("Run %s started in-process (no Redis)", run.id)

    return TestRunOut.model_validate(run)


@router.get("/runs", response_model=list[TestRunOut])
async def list_runs(
    suite_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[TestRunOut]:
    """List test runs, optionally filtered by suite and status."""
    stmt = select(TestRun).order_by(TestRun.created_at.desc()).limit(limit)
    if suite_id:
        stmt = stmt.where(TestRun.suite_id == suite_id)
    if status_filter:
        stmt = stmt.where(TestRun.status == RunStatus(status_filter))
    result = await session.execute(stmt)
    return [TestRunOut.model_validate(r) for r in result.scalars().all()]


@router.get("/runs/{run_id}", response_model=TestRunOut)
async def get_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> TestRunOut:
    run = await session.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return TestRunOut.model_validate(run)


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    run = await session.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Clean up artefacts
    StorageService.delete_artefacts(run_id)
    await session.delete(run)


# ═══════════════════════════════════════════════════════════════════════
# Reports & Artefacts
# ═══════════════════════════════════════════════════════════════════════


@router.get("/runs/{run_id}/report", response_model=JUnitTestReport)
async def get_run_report(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> JUnitTestReport:
    """Return a structured JUnit-style JSON report for a completed run."""
    run = await session.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in (RunStatus.PENDING, RunStatus.RUNNING):
        raise HTTPException(status_code=409, detail="Run has not completed yet")

    # Try loading the saved report
    if run.report_path:
        report_data = await StorageService.load_json(Path(run.report_path))
        if report_data:
            return JUnitTestReport(**report_data)

    # Rebuild from stored results
    results = [TestCaseResult(**r) for r in (run.results or [])]
    suite = await session.get(TestSuite, run.suite_id)
    suite_name = suite.name if suite else "unknown"

    total = len(results)
    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    errors = sum(1 for r in results if r.status == "error")

    return JUnitTestReport(
        suite_name=suite_name,
        total=total,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=total - passed - failed - errors,
        duration_ms=run.duration_ms or 0,
        test_cases=results,
    )


@router.get("/runs/{run_id}/trace/{test_case_id}")
async def get_trace_file(run_id: uuid.UUID, test_case_id: uuid.UUID) -> FileResponse:
    """Serve a Playwright trace .zip file for a specific test case."""
    trace_path = StorageService.trace_path(run_id, test_case_id)
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail="Trace file not found")
    return FileResponse(
        path=str(trace_path),
        media_type="application/zip",
        filename=f"trace_{test_case_id}.zip",
    )


@router.get("/runs/{run_id}/screenshots/{test_case_id}")
async def list_screenshots(
    run_id: uuid.UUID,
    test_case_id: uuid.UUID,
) -> dict[str, Any]:
    """List all screenshots for a test case within a run."""
    base = settings.screenshots_dir / str(run_id) / str(test_case_id)
    if not base.exists():
        return {"screenshots": [], "count": 0}
    files = sorted(base.glob("*.png"))
    return {
        "screenshots": [
            {"name": f.name, "path": str(f), "size_bytes": f.stat().st_size}
            for f in files
        ],
        "count": len(files),
    }


@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(run_id: uuid.UUID) -> dict[str, Any]:
    """Return a summary of all available artifacts (traces, screenshots, videos) for a run."""
    run_id_str = str(run_id)

    # ── Traces ──
    traces: list[dict[str, str]] = []
    traces_dir = settings.traces_dir / run_id_str
    if traces_dir.exists():
        for f in sorted(traces_dir.glob("*.zip")):
            tc_id = f.stem  # filename without .zip extension
            traces.append({
                "test_case_id": tc_id,
                "filename": f.name,
                "url": f"/api/runs/{run_id_str}/trace/{tc_id}",
            })

    # ── Screenshots ──
    screenshots: dict[str, list[dict[str, Any]]] = {}
    screenshots_dir = settings.screenshots_dir / run_id_str
    if screenshots_dir.exists():
        for tc_dir in sorted(screenshots_dir.iterdir()):
            if tc_dir.is_dir():
                tc_id = tc_dir.name
                steps: list[dict[str, Any]] = []
                for img in sorted(tc_dir.glob("step_*.png")):
                    # Extract step index from filename like "step_0.png"
                    try:
                        step_index = int(img.stem.split("_", 1)[1])
                    except (IndexError, ValueError):
                        continue
                    steps.append({
                        "step_index": step_index,
                        "url": f"/api/runs/{run_id_str}/screenshots/{tc_id}/step/{step_index}",
                    })
                if steps:
                    screenshots[tc_id] = steps

    # ── Videos ──
    videos: list[dict[str, str]] = []
    videos_dir = settings.videos_dir / run_id_str
    if videos_dir.exists():
        for f in sorted(videos_dir.iterdir()):
            if f.is_file():
                videos.append({
                    "filename": f.name,
                    "url": f"/api/runs/{run_id_str}/video/{f.name}",
                })

    return {
        "run_id": run_id_str,
        "traces": traces,
        "screenshots": screenshots,
        "videos": videos,
    }


@router.get("/runs/{run_id}/screenshots/{test_case_id}/step/{step_index}")
async def get_screenshot_step(
    run_id: uuid.UUID,
    test_case_id: uuid.UUID,
    step_index: int,
) -> FileResponse:
    """Serve a specific step screenshot as a PNG image."""
    screenshot_path = (
        settings.screenshots_dir
        / str(run_id)
        / str(test_case_id)
        / f"step_{step_index}.png"
    )
    if not screenshot_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(
        path=str(screenshot_path),
        media_type="image/png",
        filename=f"step_{step_index}.png",
    )


@router.get("/runs/{run_id}/video/{filename}")
async def get_video_file(run_id: uuid.UUID, filename: str) -> FileResponse:
    """Serve a video file (e.g. .webm) for a run."""
    video_path = settings.videos_dir / str(run_id) / filename
    # Prevent path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(
        path=str(video_path),
        media_type="video/webm",
        filename=filename,
    )


# ═══════════════════════════════════════════════════════════════════════
# CI/CD Webhook
# ═══════════════════════════════════════════════════════════════════════


@router.post("/webhooks/trigger/{suite_id}", response_model=WebhookTriggerResponse)
async def webhook_trigger(
    suite_id: uuid.UUID,
    browser: str = Query(default="chromium"),
    session: AsyncSession = Depends(get_session),
) -> WebhookTriggerResponse:
    """CI/CD webhook endpoint: trigger a test suite run and return the run ID.

    Poll GET /runs/{run_id} or GET /runs/{run_id}/report for results.
    """
    suite = await session.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")

    from app.schemas.test_schemas import BrowserTypeEnum

    try:
        bt = BrowserTypeEnum(browser)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid browser: {browser}")

    run = TestRun(
        suite_id=suite_id,
        browser=bt.value,
        status=RunStatus.PENDING,
        trigger_source="webhook",
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)

    pool = await _get_arq_pool()
    if pool is not None:
        await pool.enqueue_job("execute_test_run", str(run.id))
    else:
        asyncio.create_task(_run_in_process(str(run.id)))

    return WebhookTriggerResponse(
        run_id=run.id,
        status="queued",
        message=f"Test run queued for suite '{suite.name}' on {browser}",
    )


# ═══════════════════════════════════════════════════════════════════════
# WebSocket: live run progress
# ═══════════════════════════════════════════════════════════════════════


@router.websocket("/ws/runs/{run_id}")
async def ws_run_progress(websocket: WebSocket, run_id: str) -> None:
    """Stream real-time step-by-step execution progress for a test run.

    If Redis is available, subscribes to pub/sub. Otherwise, polls the DB.
    """
    await websocket.accept()
    logger.info("WebSocket connected for run progress %s", run_id)

    pool = await _get_arq_pool()

    if pool is not None:
        # Redis available — use pub/sub
        import redis.asyncio as aioredis

        pubsub_channel = f"run:{run_id}:progress"
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(pubsub_channel)

        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    await websocket.send_text(message["data"])
                    try:
                        data = json.loads(message["data"])
                        if data.get("type") == "complete":
                            await websocket.close(code=1000, reason="Run completed")
                            break
                    except (json.JSONDecodeError, KeyError):
                        pass
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for run %s", run_id)
        except Exception as exc:
            logger.error("WebSocket error for run %s: %s", run_id, exc)
        finally:
            await pubsub.unsubscribe(pubsub_channel)
            await pubsub.close()
            await redis_client.close()
    else:
        # No Redis — poll the database for status changes
        try:
            last_status = None
            while True:
                async with async_session_factory() as db:
                    run = await db.get(TestRun, uuid.UUID(run_id))
                if run and run.status.value != last_status:
                    last_status = run.status.value
                    msg = json.dumps({
                        "type": "status_update",
                        "run_id": run_id,
                        "status": last_status,
                        "duration_ms": run.duration_ms,
                    })
                    await websocket.send_text(msg)
                    if last_status in ("passed", "failed", "error", "cancelled"):
                        complete_msg = json.dumps({
                            "type": "complete",
                            "run_id": run_id,
                            "status": last_status,
                            "duration_ms": run.duration_ms or 0,
                            "results": run.results or [],
                        }, default=str)
                        await websocket.send_text(complete_msg)
                        await websocket.close(code=1000, reason="Run completed")
                        break
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for run %s", run_id)
        except Exception as exc:
            logger.error("WebSocket error for run %s: %s", run_id, exc)
