"""ARQ Redis worker tasks for parallel test execution and scheduling."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from arq import cron
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.test_models import RunStatus, TestCase, TestRun, TestSuite
from app.schemas.test_schemas import (
    AssertionStep,
    BrowserTypeEnum,
    DeviceConfig,
    JUnitTestReport,
    MockRule,
    RecordedStep,
    StepResult,
    TestCaseResult,
)
from app.services.runner import TestRunner
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Task: Execute a full test suite run
# ═══════════════════════════════════════════════════════════════════════


async def execute_test_run(ctx: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Execute all test cases in a suite as a background ARQ task.

    This task:
    1. Loads the TestRun and its related TestSuite + TestCases from the DB.
    2. Spins up a Playwright browser matching the run configuration.
    3. Executes every test case sequentially (parallelism at the suite level).
    4. Publishes step-by-step progress to Redis pub/sub for WebSocket streaming.
    5. Saves aggregated results back to the DB.
    """
    redis: ArqRedis = ctx["redis"]
    run_uuid = uuid.UUID(run_id)
    pubsub_channel = f"run:{run_id}:progress"

    async with async_session_factory() as session:
        # Fetch the run
        run = await session.get(TestRun, run_uuid)
        if not run:
            logger.error("TestRun %s not found", run_id)
            return {"error": "Run not found"}

        # Mark as running
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await session.commit()

        # Fetch associated suite and test cases
        suite = await session.get(TestSuite, run.suite_id)
        if not suite:
            run.status = RunStatus.ERROR
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return {"error": "Suite not found"}

        stmt = select(TestCase).where(TestCase.suite_id == suite.id).order_by(TestCase.created_at)
        result = await session.execute(stmt)
        test_cases = list(result.scalars().all())

        if not test_cases:
            run.status = RunStatus.PASSED
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = 0
            run.results = []
            await session.commit()
            return {"status": "passed", "message": "No test cases to run"}

    # ── Execute ─────────────────────────────────────────────────────
    browser_type = BrowserTypeEnum(run.browser.value if hasattr(run.browser, 'value') else run.browser)
    all_results: list[TestCaseResult] = []
    overall_status = RunStatus.PASSED
    start_time = time.monotonic()

    async def publish_progress(**kwargs: Any) -> None:
        """Publish step progress to Redis for WebSocket consumption."""
        message = json.dumps(kwargs, default=str)
        await redis.publish(pubsub_channel, message)

    try:
        async with TestRunner(
            run_id=run_uuid,
            browser_type=browser_type,
            on_progress=publish_progress,
        ) as runner:
            for tc in test_cases:
                steps = [RecordedStep(**s) for s in (tc.steps or [])]
                assertions_data = tc.assertions or []
                assertions = [AssertionStep(**a) for a in assertions_data] if assertions_data else None

                device_cfg = DeviceConfig(**tc.device_config) if tc.device_config else None
                mock_rules_data = tc.mock_rules or []
                mock_rules = [MockRule(**m) for m in mock_rules_data] if mock_rules_data else None

                baseline_ss: dict[str, str] | None = tc.baseline_screenshots

                tc_result = await runner.run_test_case(
                    test_case_id=tc.id,
                    test_case_name=tc.name,
                    steps=steps,
                    assertions=assertions,
                    device_config=device_cfg,
                    mock_rules=mock_rules,
                    auth_profile_id=tc.auth_profile_id,
                    baseline_screenshots=baseline_ss,
                )
                all_results.append(tc_result)

                if tc_result.status in ("failed", "error"):
                    overall_status = RunStatus.FAILED

    except Exception as exc:
        overall_status = RunStatus.ERROR
        logger.exception("Test run %s failed: %s", run_id, exc)
        all_results.append(
            TestCaseResult(
                test_case_id=uuid.uuid4(),
                test_case_name="RUNNER_ERROR",
                status="error",
                error=str(exc),
            )
        )

    duration_ms = int((time.monotonic() - start_time) * 1000)

    # ── Save results ────────────────────────────────────────────────
    async with async_session_factory() as session:
        run = await session.get(TestRun, run_uuid)
        if run:
            run.status = overall_status
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = duration_ms
            run.results = [r.model_dump(mode="json") for r in all_results]

            # Set artifact paths
            trace_dir = StorageService.trace_dir_for_run(run_uuid)
            run.trace_path = str(trace_dir)
            run.video_path = str(StorageService.video_dir(run_uuid))

            # Generate report
            report = _build_junit_report(suite.name, all_results, duration_ms)
            report_path = settings.ARTIFACTS_DIR / "reports" / f"{run_id}.json"
            await StorageService.save_json(report_path, report.model_dump(mode="json"))
            run.report_path = str(report_path)

            await session.commit()

    # Publish completion event
    completion_msg = json.dumps(
        {
            "type": "complete",
            "run_id": run_id,
            "status": overall_status.value,
            "duration_ms": duration_ms,
            "results": [r.model_dump(mode="json") for r in all_results],
        },
        default=str,
    )
    await redis.publish(pubsub_channel, completion_msg)

    return {
        "run_id": run_id,
        "status": overall_status.value,
        "duration_ms": duration_ms,
        "total_cases": len(all_results),
        "passed": sum(1 for r in all_results if r.status == "passed"),
        "failed": sum(1 for r in all_results if r.status in ("failed", "error")),
    }


# ═══════════════════════════════════════════════════════════════════════
# Task: Execute a single test case (for parallel fan-out)
# ═══════════════════════════════════════════════════════════════════════


async def execute_single_test(
    ctx: dict[str, Any],
    run_id: str,
    test_case_id: str,
    browser_type: str = "chromium",
) -> dict[str, Any]:
    """Execute a single test case — used for parallel fan-out within a suite."""
    run_uuid = uuid.UUID(run_id)
    tc_uuid = uuid.UUID(test_case_id)

    async with async_session_factory() as session:
        tc = await session.get(TestCase, tc_uuid)
        if not tc:
            return {"error": f"TestCase {test_case_id} not found"}

        steps = [RecordedStep(**s) for s in (tc.steps or [])]
        assertions_data = tc.assertions or []
        assertions = [AssertionStep(**a) for a in assertions_data] if assertions_data else None
        device_cfg = DeviceConfig(**tc.device_config) if tc.device_config else None
        mock_rules_data = tc.mock_rules or []
        mock_rules = [MockRule(**m) for m in mock_rules_data] if mock_rules_data else None

    async with TestRunner(
        run_id=run_uuid, browser_type=BrowserTypeEnum(browser_type)
    ) as runner:
        result = await runner.run_test_case(
            test_case_id=tc_uuid,
            test_case_name=tc.name if tc else "unknown",
            steps=steps,
            assertions=assertions,
            device_config=device_cfg,
            mock_rules=mock_rules,
            auth_profile_id=tc.auth_profile_id if tc else None,
            baseline_screenshots=tc.baseline_screenshots if tc else None,
        )

    return result.model_dump(mode="json")


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _build_junit_report(
    suite_name: str,
    results: list[TestCaseResult],
    duration_ms: int,
) -> JUnitTestReport:
    total = len(results)
    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    errors = sum(1 for r in results if r.status == "error")
    skipped = total - passed - failed - errors

    return JUnitTestReport(
        suite_name=suite_name,
        total=total,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        duration_ms=duration_ms,
        test_cases=results,
    )


# ═══════════════════════════════════════════════════════════════════════
# ARQ Worker Settings
# ═══════════════════════════════════════════════════════════════════════


async def startup(ctx: dict[str, Any]) -> None:
    """Worker startup hook."""
    logger.info("ARQ worker starting up")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown hook."""
    logger.info("ARQ worker shutting down")


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [execute_test_run, execute_single_test]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 600  # 10 minutes max per job
    keep_result = 3600  # keep results for 1 hour
    health_check_interval = 30
