"""Routes for triggering test runs, fetching reports, webhooks, and WebSocket progress streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from arq.connections import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory, get_session
from app.models.test_models import (
    BrowserType,
    RunStatus,
    TestCase,
    TestRun,
    TestRunOptions,
    TestSuite,
)
from app.schemas.test_schemas import (
    CancelRunResponse,
    JUnitTestReport,
    TestCaseResult,
    TestRunCreate,
    TestRunOut,
    WebhookTriggerResponse,
)
from app.services.cancellation import request_cancel
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
        await execute_test_run({"redis": _FakeRedis(run_id)}, run_id)
    except Exception as exc:
        logger.exception("In-process run %s failed: %s", run_id, exc)
    finally:
        # Clean up progress store after a delay (let WebSocket clients read final state)
        await asyncio.sleep(5)
        _progress_store.pop(run_id, None)


async def _enqueue_run(run_id: uuid.UUID) -> None:
    """Queue a run via ARQ, or execute in-process when Redis is unavailable."""
    pool = await _get_arq_pool()
    if pool is not None:
        await pool.enqueue_job(
            "execute_test_run", str(run_id), _job_id=f"run:{run_id}"
        )
        logger.info("Run %s enqueued via ARQ", run_id)
    else:
        asyncio.create_task(_run_in_process(str(run_id)))
        logger.info("Run %s started in-process (no Redis)", run_id)


# ── In-memory progress store (no-Redis fallback) ───────────────────

_progress_store: dict[str, list[dict]] = {}


class _FakeRedis:
    """Stub that stores progress in-memory when Redis is absent."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        _progress_store[run_id] = []

    async def publish(self, channel: str, message: str) -> None:
        _progress_store.setdefault(self._run_id, []).append(message)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        return True

    async def exists(self, key: str) -> int:
        return 0

    async def delete(self, key: str) -> int:
        return 0


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

    # Reject empty suites — nothing to run
    tc_count = await session.execute(
        select(TestCase).where(TestCase.suite_id == body.suite_id).limit(1)
    )
    if not tc_count.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Suite has no test cases. Add at least one test case before running.",
        )

    run = TestRun(
        suite_id=body.suite_id,
        browser=BrowserType(body.browser.value),
        status=RunStatus.PENDING,
        trigger_source=body.trigger_source,
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)

    # Commit NOW so the background task can see the run in its own session
    await session.commit()

    await _enqueue_run(run.id)

    return TestRunOut.model_validate(run)


@router.get("/runs", response_model=list[TestRunOut])
async def list_runs(
    response: Response,
    suite_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    status_filter: RunStatus | None = Query(default=None, alias="status"),
    trigger_source: str | None = Query(default=None),
    created_after: datetime | None = Query(default=None),
    created_before: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[TestRunOut]:
    """List test runs with filtering and pagination.

    The total count is returned in the ``X-Total-Count`` response header so
    existing clients that expect a plain JSON array keep working.
    """
    conditions = []
    if suite_id:
        conditions.append(TestRun.suite_id == suite_id)
    if status_filter:
        conditions.append(TestRun.status == status_filter)
    if trigger_source:
        conditions.append(TestRun.trigger_source == trigger_source)
    if created_after:
        conditions.append(TestRun.created_at >= created_after)
    if created_before:
        conditions.append(TestRun.created_at <= created_before)

    stmt = select(TestRun)
    count_stmt = select(func.count()).select_from(TestRun)
    if project_id:
        stmt = stmt.join(TestSuite, TestRun.suite_id == TestSuite.id)
        count_stmt = count_stmt.join(TestSuite, TestRun.suite_id == TestSuite.id)
        conditions.append(TestSuite.project_id == project_id)

    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = (await session.execute(count_stmt)).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)

    stmt = (
        stmt.order_by(TestRun.created_at.desc(), TestRun.id.desc())
        .limit(limit)
        .offset(offset)
    )
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


@router.post("/runs/{run_id}/cancel", response_model=CancelRunResponse)
async def cancel_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> CancelRunResponse:
    """Cancel a pending run or request cooperative cancellation of a running run."""
    run = await session.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status in (
        RunStatus.PASSED,
        RunStatus.FAILED,
        RunStatus.ERROR,
        RunStatus.CANCELLED,
    ):
        raise HTTPException(status_code=409, detail="Run has already finished")

    await request_cancel(run_id, await _get_arq_pool())

    if run.status == RunStatus.PENDING:
        run.status = RunStatus.CANCELLED
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = 0
        await session.commit()
        return CancelRunResponse(
            run_id=run.id,
            status="cancelled",
            message="Run cancelled before execution",
        )

    return CancelRunResponse(
        run_id=run.id,
        status="cancelling",
        message="Cancellation requested; the worker will stop after the current step",
    )


@router.post(
    "/runs/{run_id}/retry",
    response_model=TestRunOut,
    status_code=status.HTTP_201_CREATED,
)
async def retry_run(
    run_id: uuid.UUID,
    mode: Literal["all", "failed"] = Query(default="all"),
    session: AsyncSession = Depends(get_session),
) -> TestRunOut:
    """Create a new run for all test cases or only the failed ones."""
    source = await session.get(TestRun, run_id)
    if not source:
        raise HTTPException(status_code=404, detail="Run not found")
    if source.status in (RunStatus.PENDING, RunStatus.RUNNING):
        raise HTTPException(status_code=409, detail="Run is still in progress")

    suite = await session.get(TestSuite, source.suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")

    result = await session.execute(
        select(TestCase)
        .where(TestCase.suite_id == source.suite_id)
        .order_by(TestCase.created_at)
    )
    test_cases = list(result.scalars().all())
    if not test_cases:
        raise HTTPException(
            status_code=400, detail="Suite has no test cases to retry"
        )

    test_case_ids = [str(tc.id) for tc in test_cases]
    if mode == "failed":
        failed_ids = {
            str(item.get("test_case_id"))
            for item in (source.results or [])
            if item.get("status") in ("failed", "error")
        }
        test_case_ids = [tc_id for tc_id in test_case_ids if tc_id in failed_ids]
        if not test_case_ids:
            raise HTTPException(
                status_code=400, detail="Run has no failed test cases to retry"
            )

    run = TestRun(
        suite_id=source.suite_id,
        browser=source.browser,
        status=RunStatus.PENDING,
        trigger_source=f"retry:{mode}",
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)

    session.add(
        TestRunOptions(
            run_id=run.id,
            parent_run_id=source.id,
            retry_mode=mode,
            test_case_ids=test_case_ids,
        )
    )
    await session.commit()

    await _enqueue_run(run.id)
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


async def _load_run_report(
    run: TestRun, session: AsyncSession
) -> JUnitTestReport:
    """Load a saved report or rebuild it from the stored results."""
    if run.report_path:
        report_data = await StorageService.load_json(Path(run.report_path))
        if report_data:
            return JUnitTestReport(**report_data)

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


def _report_to_junit_xml(report: JUnitTestReport) -> str:
    """Render a JUnit XML document from the structured report."""
    root = ET.Element("testsuites")
    testsuite = ET.SubElement(
        root,
        "testsuite",
        name=report.suite_name,
        tests=str(report.total),
        failures=str(report.failed),
        errors=str(report.errors),
        skipped=str(report.skipped),
        time=f"{report.duration_ms / 1000:.3f}",
    )
    for tc in report.test_cases:
        tc_el = ET.SubElement(
            testsuite,
            "testcase",
            name=tc.test_case_name,
            classname=report.suite_name,
            time=f"{tc.duration_ms / 1000:.3f}",
        )
        if tc.status == "failed":
            failure = ET.SubElement(
                tc_el, "failure", message=tc.error or "Test failed"
            )
            failure.text = tc.error or ""
        elif tc.status == "error":
            error = ET.SubElement(tc_el, "error", message=tc.error or "Test error")
            error.text = tc.error or ""
        elif tc.status in ("skipped", "cancelled"):
            ET.SubElement(tc_el, "skipped", message=tc.error or tc.status)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


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
    return await _load_run_report(run, session)


@router.get("/runs/{run_id}/report.xml")
async def get_run_report_xml(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """Download a JUnit XML report for a completed run."""
    run = await session.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in (RunStatus.PENDING, RunStatus.RUNNING):
        raise HTTPException(status_code=409, detail="Run has not completed yet")

    report = await _load_run_report(run, session)
    xml = _report_to_junit_xml(report)
    return Response(
        content=xml,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="run_{run_id}.xml"'
        },
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


def _collect_screenshot_artifacts(
    run_id: uuid.UUID, test_case_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Return per-step screenshot URLs without exposing filesystem paths."""
    base = settings.screenshots_dir / str(run_id) / str(test_case_id)
    if not base.exists():
        return []

    entries: dict[int, dict[str, Any]] = {}
    for img in sorted(base.glob("step_*.png")):
        stem = img.stem
        kind = "step"
        if stem.endswith("_failure"):
            kind = "failure"
            stem = stem[: -len("_failure")]
        elif stem.endswith("_diff"):
            kind = "diff"
            stem = stem[: -len("_diff")]

        try:
            step_index = int(stem.split("_", 1)[1])
        except (IndexError, ValueError):
            continue

        entry = entries.setdefault(step_index, {"step_index": step_index})
        url = (
            f"/api/runs/{run_id}/screenshots/{test_case_id}/step/{step_index}"
        )
        if kind == "step":
            entry["url"] = url
            entry["size_bytes"] = img.stat().st_size
        elif kind == "failure":
            entry["failure_url"] = f"{url}/failure"
            entry["failure_size_bytes"] = img.stat().st_size
        else:
            entry["diff_url"] = f"{url}/diff"
            entry["diff_size_bytes"] = img.stat().st_size

    return [entries[index] for index in sorted(entries)]


@router.get("/runs/{run_id}/screenshots/{test_case_id}")
async def list_screenshots(
    run_id: uuid.UUID,
    test_case_id: uuid.UUID,
) -> dict[str, Any]:
    """List all screenshots for a test case within a run."""
    screenshots = _collect_screenshot_artifacts(run_id, test_case_id)
    return {"screenshots": screenshots, "count": len(screenshots)}


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
            traces.append(
                {
                    "test_case_id": tc_id,
                    "filename": f.name,
                    "url": f"/api/runs/{run_id_str}/trace/{tc_id}",
                }
            )

    # ── Screenshots ──
    screenshots: dict[str, list[dict[str, Any]]] = {}
    screenshots_dir = settings.screenshots_dir / run_id_str
    if screenshots_dir.exists():
        for tc_dir in sorted(screenshots_dir.iterdir()):
            if not tc_dir.is_dir():
                continue
            try:
                test_case_id = uuid.UUID(tc_dir.name)
            except ValueError:
                continue
            steps = _collect_screenshot_artifacts(run_id, test_case_id)
            if steps:
                screenshots[tc_dir.name] = steps

    # ── Videos ──
    videos: list[dict[str, str]] = []
    videos_dir = settings.videos_dir / run_id_str
    if videos_dir.exists():
        for f in sorted(videos_dir.iterdir()):
            if f.is_file():
                videos.append(
                    {
                        "filename": f.name,
                        "url": f"/api/runs/{run_id_str}/video/{f.name}",
                    }
                )

    return {
        "run_id": run_id_str,
        "traces": traces,
        "screenshots": screenshots,
        "videos": videos,
    }


async def _screenshot_response(
    run_id: uuid.UUID,
    test_case_id: uuid.UUID,
    step_index: int,
    kind: str,
) -> FileResponse:
    path = StorageService.screenshot_file(
        run_id, test_case_id, step_index, kind=kind
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(
        path=str(path),
        media_type="image/png",
        filename=path.name,
    )


@router.get("/runs/{run_id}/screenshots/{test_case_id}/step/{step_index}")
async def get_screenshot_step(
    run_id: uuid.UUID,
    test_case_id: uuid.UUID,
    step_index: int,
) -> FileResponse:
    """Serve a specific step screenshot as a PNG image."""
    return await _screenshot_response(run_id, test_case_id, step_index, "step")


@router.get("/runs/{run_id}/screenshots/{test_case_id}/step/{step_index}/failure")
async def get_screenshot_failure(
    run_id: uuid.UUID,
    test_case_id: uuid.UUID,
    step_index: int,
) -> FileResponse:
    """Serve the failure screenshot for a step."""
    return await _screenshot_response(run_id, test_case_id, step_index, "failure")


@router.get("/runs/{run_id}/screenshots/{test_case_id}/step/{step_index}/diff")
async def get_screenshot_diff(
    run_id: uuid.UUID,
    test_case_id: uuid.UUID,
    step_index: int,
) -> FileResponse:
    """Serve the visual-diff image for a step."""
    return await _screenshot_response(run_id, test_case_id, step_index, "diff")


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

    # Reject empty suites
    tc_count = await session.execute(
        select(TestCase).where(TestCase.suite_id == suite_id).limit(1)
    )
    if not tc_count.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Suite has no test cases. Add at least one test case before running.",
        )

    from app.schemas.test_schemas import BrowserTypeEnum

    try:
        bt = BrowserTypeEnum(browser)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid browser: {browser}")

    run = TestRun(
        suite_id=suite_id,
        browser=BrowserType(bt.value),
        status=RunStatus.PENDING,
        trigger_source="webhook",
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)

    # Commit NOW so the background task can see the run in its own session
    await session.commit()

    await _enqueue_run(run.id)

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
        # No Redis — read from in-memory progress store + poll DB
        try:
            last_status = None
            progress_cursor = 0  # tracks how many messages we've sent
            while True:
                # Send any new step-progress messages from the in-memory store
                messages = _progress_store.get(run_id, [])
                while progress_cursor < len(messages):
                    await websocket.send_text(messages[progress_cursor])
                    try:
                        data = json.loads(messages[progress_cursor])
                        if data.get("type") == "complete":
                            await websocket.close(code=1000, reason="Run completed")
                            return
                    except (json.JSONDecodeError, KeyError):
                        pass
                    progress_cursor += 1

                # Also poll DB for status changes (catches completion if store was cleaned)
                async with async_session_factory() as db:
                    run = await db.get(TestRun, uuid.UUID(run_id))
                if run:
                    current_status = run.status.value if hasattr(run.status, 'value') else str(run.status)
                    if current_status != last_status:
                        last_status = current_status
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
                    await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected for run %s", run_id)
        except Exception as exc:
            logger.error("WebSocket error for run %s: %s", run_id, exc)
