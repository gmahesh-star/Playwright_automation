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
from app.models.test_models import (
    RunStatus,
    TestCase,
    TestRun,
    TestRunOptions,
    TestSuite,
)
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
from app.services.cancellation import clear_cancel, is_cancelled
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

    async def publish_complete(
        status_value: RunStatus, duration_ms: int, results: list[TestCaseResult]
    ) -> None:
        await redis.publish(
            pubsub_channel,
            json.dumps(
                {
                    "type": "complete",
                    "run_id": run_id,
                    "status": status_value.value,
                    "duration_ms": duration_ms,
                    "results": [r.model_dump(mode="json") for r in results],
                },
                default=str,
            ),
        )

    async with async_session_factory() as session:
        # Fetch the run
        run = await session.get(TestRun, run_uuid)
        if not run:
            logger.error("TestRun %s not found", run_id)
            return {"error": "Run not found"}

        if run.status == RunStatus.CANCELLED or await is_cancelled(run_id, redis):
            run.status = RunStatus.CANCELLED
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = 0
            run.results = []
            await session.commit()
            await publish_complete(RunStatus.CANCELLED, 0, [])
            await clear_cancel(run_id, redis)
            return {
                "run_id": run_id,
                "status": "cancelled",
                "duration_ms": 0,
                "total_cases": 0,
                "passed": 0,
                "failed": 0,
            }

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

        # Retry/rerun runs may target only a subset of the suite.
        options = await session.get(TestRunOptions, run_uuid)
        selected_ids: set[uuid.UUID] = set()
        for raw_id in (options.test_case_ids or []) if options else []:
            try:
                selected_ids.add(uuid.UUID(str(raw_id)))
            except (TypeError, ValueError):
                continue
        if selected_ids:
            stmt = stmt.where(TestCase.id.in_(selected_ids))

        result = await session.execute(stmt)
        test_cases = list(result.scalars().all())

        if not test_cases:
            run.status = RunStatus.ERROR
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = 0
            run.results = []
            await session.commit()
            return {"status": "error", "message": "Suite has no test cases"}

        if await is_cancelled(run_id, redis):
            skipped_results = [
                TestCaseResult(
                    test_case_id=tc.id,
                    test_case_name=tc.name,
                    status="skipped",
                    error="Run cancelled",
                )
                for tc in test_cases
            ]
            run.status = RunStatus.CANCELLED
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = 0
            run.results = [r.model_dump(mode="json") for r in skipped_results]
            await session.commit()
            await publish_complete(RunStatus.CANCELLED, 0, skipped_results)
            await clear_cancel(run_id, redis)
            return {
                "run_id": run_id,
                "status": "cancelled",
                "duration_ms": 0,
                "total_cases": len(test_cases),
                "passed": 0,
                "failed": 0,
            }

    # ── Execute ─────────────────────────────────────────────────────
    browser_type = BrowserTypeEnum(run.browser.value if hasattr(run.browser, 'value') else run.browser)
    all_results: list[TestCaseResult] = []
    overall_status = RunStatus.PASSED
    cancelled = False
    start_time = time.monotonic()

    async def publish_progress(**kwargs: Any) -> None:
        """Publish step progress to Redis for WebSocket consumption."""
        message = json.dumps(kwargs, default=str)
        await redis.publish(pubsub_channel, message)

    async def cancel_requested() -> bool:
        return await is_cancelled(run_id, redis)

    try:
        async with TestRunner(
            run_id=run_uuid,
            browser_type=browser_type,
            on_progress=publish_progress,
            cancel_check=cancel_requested,
        ) as runner:
            for tc_index, tc in enumerate(test_cases):
                if await cancel_requested():
                    cancelled = True
                    for remaining in test_cases[tc_index:]:
                        all_results.append(
                            TestCaseResult(
                                test_case_id=remaining.id,
                                test_case_name=remaining.name,
                                status="skipped",
                                error="Run cancelled",
                            )
                        )
                    break

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

                if tc_result.status == "cancelled":
                    cancelled = True
                    for remaining in test_cases[tc_index + 1:]:
                        all_results.append(
                            TestCaseResult(
                                test_case_id=remaining.id,
                                test_case_name=remaining.name,
                                status="skipped",
                                error="Run cancelled",
                            )
                        )
                    break

                if tc_result.status in ("failed", "error"):
                    overall_status = RunStatus.FAILED

            if cancelled:
                overall_status = RunStatus.CANCELLED

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

    # Publish completion event and clear any cancellation flag
    await publish_complete(overall_status, duration_ms, all_results)
    await clear_cancel(run_id, redis)

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
