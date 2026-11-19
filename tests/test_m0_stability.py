"""Regression tests for M0 stability work.

Covers cancellation, retry subsets, paginated run listing, JUnit XML reports,
artifact URL hygiene, wait handling, and failure screenshot metadata.
"""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import routes_runs
from app.core.config import settings
from app.core.database import Base, get_session
from app.main import app
from app.models.test_models import (
    AuthProfile,
    Project,
    RunStatus,
    TestCase as Scenario,
    TestRun as RunRecord,
    TestRunOptions as RunOptions,
    TestSuite as SuiteRecord,
)
from app.schemas.test_schemas import (
    RecordedStep,
    StepAction,
    StepResult,
    TestCaseResult as CaseResult,
    TestRunOut as RunOut,
)
from app.services import cancellation
from app.services.runner import TestRunner as Runner


# ═══════════════════════════════════════════════════════════════════════
# Fixtures / helpers
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def api_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", tmp_path / "artifacts")

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = session_factory()
    await session.__aenter__()

    async def override_session():
        yield session

    async def no_redis():
        return None

    async def no_enqueue(_run_id):
        return None

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(routes_runs, "_get_arq_pool", no_redis)
    monkeypatch.setattr(routes_runs, "_enqueue_run", no_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session

    app.dependency_overrides.pop(get_session, None)
    await session.__aexit__(None, None, None)
    await engine.dispose()


async def _seed_suite(session, *, test_count=2):
    project = Project(name=f"Project {uuid.uuid4().hex[:6]}")
    session.add(project)
    await session.flush()

    suite = SuiteRecord(project_id=project.id, name="Suite")
    session.add(suite)
    await session.flush()

    test_cases = []
    for index in range(test_count):
        test_case = Scenario(
            suite_id=suite.id,
            name=f"Case {index}",
            steps=[],
            created_at=datetime.now(timezone.utc) + timedelta(seconds=index),
        )
        session.add(test_case)
        test_cases.append(test_case)

    await session.commit()
    return project, suite, test_cases


def _case_result(test_case: Scenario, status: str) -> dict:
    return CaseResult(
        test_case_id=test_case.id,
        test_case_name=test_case.name,
        status=status,
    ).model_dump(mode="json")


# ═══════════════════════════════════════════════════════════════════════
# API tests
# ═══════════════════════════════════════════════════════════════════════


async def test_list_runs_paginates_and_returns_total_header(api_env):
    client, session = api_env
    _, suite, _ = await _seed_suite(session)
    now = datetime.now(timezone.utc)

    for index, status in enumerate(
        [RunStatus.PASSED, RunStatus.FAILED, RunStatus.PASSED]
    ):
        session.add(
            RunRecord(
                suite_id=suite.id,
                status=status,
                created_at=now + timedelta(seconds=index),
            )
        )
    await session.commit()

    response = await client.get("/api/runs", params={"limit": 2, "offset": 1})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert response.headers["x-total-count"] == "3"
    assert response.headers["x-limit"] == "2"
    assert response.headers["x-offset"] == "1"

    failed_response = await client.get("/api/runs", params={"status": "failed"})
    assert failed_response.status_code == 200
    assert failed_response.headers["x-total-count"] == "1"
    assert failed_response.json()[0]["status"] == "failed"


async def test_auth_profile_never_exposes_storage_path(api_env):
    client, session = api_env
    project, _, _ = await _seed_suite(session)
    profile = AuthProfile(
        project_id=project.id,
        name="Saved session",
        storage_state_path="/srv/private/auth_states/secret.json",
    )
    session.add(profile)
    await session.commit()

    response = await client.get("/api/auth-profiles")

    assert response.status_code == 200
    payload = response.json()[0]
    assert "storage_state_path" not in payload
    assert payload["has_storage_state"] is True


async def test_cancel_pending_run_marks_it_cancelled(api_env):
    client, session = api_env
    _, suite, _ = await _seed_suite(session)
    run = RunRecord(suite_id=suite.id, status=RunStatus.PENDING)
    session.add(run)
    await session.commit()

    response = await client.post(f"/api/runs/{run.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    await session.refresh(run)
    assert run.status == RunStatus.CANCELLED
    assert run.finished_at is not None
    await cancellation.clear_cancel(run.id)


async def test_retry_failed_only_uses_stored_failed_case_ids(api_env):
    client, session = api_env
    _, suite, test_cases = await _seed_suite(session)
    failed_case, passed_case = test_cases
    source = RunRecord(
        suite_id=suite.id,
        status=RunStatus.FAILED,
        results=[
            _case_result(failed_case, "failed"),
            _case_result(passed_case, "passed"),
        ],
    )
    session.add(source)
    await session.commit()

    response = await client.post(f"/api/runs/{source.id}/retry?mode=failed")

    assert response.status_code == 201
    retried = response.json()
    assert retried["status"] == "pending"
    assert retried["trigger_source"] == "retry:failed"

    options = await session.get(RunOptions, uuid.UUID(retried["id"]))
    assert options is not None
    assert options.parent_run_id == source.id
    assert options.retry_mode == "failed"
    assert options.test_case_ids == [str(failed_case.id)]


async def test_report_xml_is_downloadable(api_env):
    client, session = api_env
    _, suite, test_cases = await _seed_suite(session)
    run = RunRecord(
        suite_id=suite.id,
        status=RunStatus.PASSED,
        duration_ms=1234,
        results=[
            _case_result(test_cases[0], "passed"),
            _case_result(test_cases[1], "passed"),
        ],
    )
    session.add(run)
    await session.commit()

    response = await client.get(f"/api/runs/{run.id}/report.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert f'run_{run.id}.xml' in response.headers["content-disposition"]
    root = ET.fromstring(response.text)
    suite_el = root.find("testsuite")
    assert suite_el is not None
    assert suite_el.attrib["tests"] == "2"
    assert suite_el.attrib["failures"] == "0"


async def test_artifacts_use_api_urls_and_never_expose_paths(api_env):
    client, _ = api_env
    run_id = uuid.uuid4()
    test_case_id = uuid.uuid4()
    step_dir = settings.screenshots_dir / str(run_id) / str(test_case_id)
    step_dir.mkdir(parents=True)
    (step_dir / "step_0.png").write_bytes(b"fake")
    (step_dir / "step_0_failure.png").write_bytes(b"fake")
    (step_dir / "step_0_diff.png").write_bytes(b"fake")

    response = await client.get(f"/api/runs/{run_id}/artifacts")

    assert response.status_code == 200
    payload = response.json()
    steps = payload["screenshots"][str(test_case_id)]
    assert steps[0]["url"] == (
        f"/api/runs/{run_id}/screenshots/{test_case_id}/step/0"
    )
    assert steps[0]["failure_url"].endswith("/failure")
    assert steps[0]["diff_url"].endswith("/diff")
    assert "path" not in steps[0]

    for key in ("url", "failure_url", "diff_url"):
        served = await client.get(steps[0][key])
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"

    listing = await client.get(f"/api/runs/{run_id}/screenshots/{test_case_id}")
    assert listing.status_code == 200
    assert listing.json()["count"] == 1
    assert "path" not in listing.json()["screenshots"][0]


# ═══════════════════════════════════════════════════════════════════════
# Runner / schema tests
# ═══════════════════════════════════════════════════════════════════════


def test_wait_duration_uses_step_value_with_clamp():
    assert Runner._wait_duration_ms(
        RecordedStep(action=StepAction.WAIT, value="250")
    ) == 250
    assert Runner._wait_duration_ms(
        RecordedStep(action=StepAction.WAIT, value="-5")
    ) == 0
    assert Runner._wait_duration_ms(
        RecordedStep(action=StepAction.WAIT, value="999999")
    ) == 60_000
    assert Runner._wait_duration_ms(
        RecordedStep(action=StepAction.WAIT, value="invalid")
    ) == 1000
    assert Runner._wait_duration_ms(RecordedStep(action=StepAction.WAIT)) == 1000


async def test_cancelled_run_skips_steps(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", tmp_path)
    steps = [
        RecordedStep(
            action=StepAction.NAVIGATE,
            url="data:text/html,<h1>Hello</h1>",
        )
    ]

    async with Runner(
        run_id=uuid.uuid4(), cancel_check=lambda: True
    ) as runner:
        result = await runner.run_test_case(
            test_case_id=uuid.uuid4(),
            test_case_name="cancelled",
            steps=steps,
        )

    assert result.status == "cancelled"
    assert [step.status for step in result.step_results] == ["skipped"]


async def test_failure_screenshot_is_captured_and_serialized_as_basename(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", tmp_path)
    run_id = uuid.uuid4()
    test_case_id = uuid.uuid4()
    steps = [
        RecordedStep(
            action=StepAction.NAVIGATE,
            url="data:text/html,<h1>Hello</h1>",
        ),
        RecordedStep(action=StepAction.CLICK, selector="#missing", timeout_ms=500),
    ]

    async with Runner(run_id=run_id) as runner:
        result = await runner.run_test_case(
            test_case_id=test_case_id,
            test_case_name="failure-screenshot",
            steps=steps,
        )

    failed_step = result.step_results[1]
    assert failed_step.status == "failed"
    assert failed_step.failure_screenshot_path == "step_1_failure.png"
    serialized = failed_step.model_dump()
    assert serialized["failure_screenshot_path"] == "step_1_failure.png"
    assert (
        settings.screenshots_dir
        / str(run_id)
        / str(test_case_id)
        / "step_1_failure.png"
    ).exists()


def test_artifact_paths_are_not_exposed_by_schemas():
    step = StepResult(
        step_index=0,
        action="click",
        status="passed",
        screenshot_path="/tmp/secret/run/step_0.png",
        failure_screenshot_path="/tmp/secret/run/step_0_failure.png",
        diff_screenshot_path="/tmp/secret/run/step_0_diff.png",
    )
    dumped = step.model_dump()
    assert dumped["screenshot_path"] == "step_0.png"
    assert dumped["failure_screenshot_path"] == "step_0_failure.png"
    assert dumped["diff_screenshot_path"] == "step_0_diff.png"
    assert "trace_path" not in RunOut.model_fields
    assert "video_path" not in RunOut.model_fields
    assert "report_path" not in RunOut.model_fields


async def test_cancellation_flag_round_trip():
    run_id = uuid.uuid4()
    await cancellation.request_cancel(run_id)
    try:
        assert await cancellation.is_cancelled(run_id) is True
    finally:
        await cancellation.clear_cancel(run_id)
    assert await cancellation.is_cancelled(run_id) is False
