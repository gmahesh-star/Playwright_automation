"""CRUD routes for projects, test suites, test cases, auth profiles, and mock rules."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.test_models import AuthProfile, Project, TestCase, TestSuite
from app.schemas.test_schemas import (
    AssertionStep,
    AuthProfileCreate,
    AuthProfileOut,
    AuthProfileUpdate,
    CodeExportResponse,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    RecordedStep,
    TestCaseCreate,
    TestCaseOut,
    TestCaseUpdate,
    TestSuiteCreate,
    TestSuiteOut,
    TestSuiteUpdate,
)
from app.services.codegen import CodeGenerator
from app.services.selectors import canonicalize_selector
from app.services.storage import StorageService

router = APIRouter(tags=["tests"])


def _canonicalize_steps(
    steps: list[RecordedStep | dict[str, Any]],
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for step in steps:
        data = RecordedStep.model_validate(step).model_dump(mode="json")
        if data.get("selector"):
            data["selector"] = canonicalize_selector(data["selector"])
        payload.append(data)
    return payload


def _canonicalize_assertions(
    assertions: list[AssertionStep | dict[str, Any]],
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for assertion in assertions:
        data = AssertionStep.model_validate(assertion).model_dump(mode="json")
        if data.get("selector"):
            data["selector"] = canonicalize_selector(data["selector"])
        payload.append(data)
    return payload


# ═══════════════════════════════════════════════════════════════════════
# Projects
# ═══════════════════════════════════════════════════════════════════════


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate, session: AsyncSession = Depends(get_session)
) -> ProjectOut:
    project = Project(name=body.name, description=body.description)
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return ProjectOut.model_validate(project)


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectOut]:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ProjectOut:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectOut.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    await session.flush()
    await session.refresh(project)
    return ProjectOut.model_validate(project)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_project(
    project_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await session.delete(project)


# ═══════════════════════════════════════════════════════════════════════
# Test Suites
# ═══════════════════════════════════════════════════════════════════════


@router.post("/suites", response_model=TestSuiteOut, status_code=status.HTTP_201_CREATED)
async def create_suite(
    body: TestSuiteCreate, session: AsyncSession = Depends(get_session)
) -> TestSuiteOut:
    project = await session.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    suite = TestSuite(
        project_id=body.project_id, name=body.name, tags=body.tags or []
    )
    session.add(suite)
    await session.flush()
    await session.refresh(suite)
    return TestSuiteOut.model_validate(suite)


@router.get("/suites", response_model=list[TestSuiteOut])
async def list_suites(
    project_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[TestSuiteOut]:
    stmt = select(TestSuite).order_by(TestSuite.created_at.desc())
    if project_id:
        stmt = stmt.where(TestSuite.project_id == project_id)
    result = await session.execute(stmt)
    return [TestSuiteOut.model_validate(s) for s in result.scalars().all()]


@router.get("/suites/{suite_id}", response_model=TestSuiteOut)
async def get_suite(
    suite_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> TestSuiteOut:
    suite = await session.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    return TestSuiteOut.model_validate(suite)


@router.patch("/suites/{suite_id}", response_model=TestSuiteOut)
async def update_suite(
    suite_id: uuid.UUID,
    body: TestSuiteUpdate,
    session: AsyncSession = Depends(get_session),
) -> TestSuiteOut:
    suite = await session.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(suite, field, value)
    await session.flush()
    await session.refresh(suite)
    return TestSuiteOut.model_validate(suite)


@router.delete("/suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_suite(
    suite_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    suite = await session.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    await session.delete(suite)


# ═══════════════════════════════════════════════════════════════════════
# Test Cases
# ═══════════════════════════════════════════════════════════════════════


@router.post("/tests", response_model=TestCaseOut, status_code=status.HTTP_201_CREATED)
async def create_test_case(
    body: TestCaseCreate, session: AsyncSession = Depends(get_session)
) -> TestCaseOut:
    suite = await session.get(TestSuite, body.suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")

    tc = TestCase(
        suite_id=body.suite_id,
        name=body.name,
        description=body.description,
        steps=_canonicalize_steps(body.steps),
        assertions=_canonicalize_assertions(body.assertions) if body.assertions else [],
        device_config=body.device_config.model_dump(mode="json") if body.device_config else None,
        mock_rules=[m.model_dump(mode="json") for m in body.mock_rules] if body.mock_rules else [],
        auth_profile_id=body.auth_profile_id,
        baseline_screenshots=body.baseline_screenshots,
    )
    session.add(tc)
    await session.flush()
    await session.refresh(tc)
    return TestCaseOut.model_validate(tc)


@router.get("/tests", response_model=list[TestCaseOut])
async def list_test_cases(
    suite_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[TestCaseOut]:
    stmt = select(TestCase).order_by(TestCase.created_at.desc())
    if suite_id:
        stmt = stmt.where(TestCase.suite_id == suite_id)
    result = await session.execute(stmt)
    return [TestCaseOut.model_validate(tc) for tc in result.scalars().all()]


@router.get("/tests/{test_id}", response_model=TestCaseOut)
async def get_test_case(
    test_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> TestCaseOut:
    tc = await session.get(TestCase, test_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    return TestCaseOut.model_validate(tc)


@router.patch("/tests/{test_id}", response_model=TestCaseOut)
async def update_test_case(
    test_id: uuid.UUID,
    body: TestCaseUpdate,
    session: AsyncSession = Depends(get_session),
) -> TestCaseOut:
    tc = await session.get(TestCase, test_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "steps" and value is not None:
            setattr(tc, field, _canonicalize_steps(value))
        elif field == "assertions" and value is not None:
            setattr(tc, field, _canonicalize_assertions(value))
        elif field == "device_config" and value is not None:
            setattr(tc, field, value.model_dump(mode="json"))
        elif field == "mock_rules" and value is not None:
            setattr(tc, field, [m.model_dump(mode="json") for m in value])
        else:
            setattr(tc, field, value)
    await session.flush()
    await session.refresh(tc)
    return TestCaseOut.model_validate(tc)


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_test_case(
    test_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    tc = await session.get(TestCase, test_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    await session.delete(tc)


# ═══════════════════════════════════════════════════════════════════════
# Code Export
# ═══════════════════════════════════════════════════════════════════════


@router.get("/tests/{test_id}/export", response_model=CodeExportResponse)
async def export_test_code(
    test_id: uuid.UUID,
    lang: str = Query(default="python", description="Export language (currently: python)"),
    session: AsyncSession = Depends(get_session),
) -> CodeExportResponse:
    """Export a test case as runnable pytest-playwright code."""
    tc = await session.get(TestCase, test_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    if lang != "python":
        raise HTTPException(status_code=400, detail=f"Unsupported language: {lang}")

    from app.schemas.test_schemas import RecordedStep, AssertionStep, DeviceConfig, MockRule

    steps = [RecordedStep(**s) for s in (tc.steps or [])]
    assertions_data = tc.assertions or []
    assertions = [AssertionStep(**a) for a in assertions_data] if assertions_data else None
    device_cfg = DeviceConfig(**tc.device_config) if tc.device_config else None
    mock_rules_data = tc.mock_rules or []
    mock_rules = [MockRule(**m) for m in mock_rules_data] if mock_rules_data else None

    # Resolve auth state path
    auth_path: str | None = None
    if tc.auth_profile_id:
        auth_profile = await session.get(AuthProfile, tc.auth_profile_id)
        if auth_profile and auth_profile.storage_state_path:
            auth_path = auth_profile.storage_state_path

    code = CodeGenerator.export_python(
        test_name=tc.name,
        steps=steps,
        assertions=assertions,
        device_config=device_cfg,
        mock_rules=mock_rules,
        auth_storage_state_path=auth_path,
    )

    safe_name = tc.name.lower().replace(" ", "_")[:50]
    return CodeExportResponse(
        language="python",
        code=code,
        filename=f"test_{safe_name}.py",
    )


# ═══════════════════════════════════════════════════════════════════════
# Auth Profiles
# ═══════════════════════════════════════════════════════════════════════


@router.post("/auth-profiles", response_model=AuthProfileOut, status_code=status.HTTP_201_CREATED)
async def create_auth_profile(
    body: AuthProfileCreate, session: AsyncSession = Depends(get_session)
) -> AuthProfileOut:
    project = await session.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    profile = AuthProfile(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        storage_state=body.storage_state,
    )

    # Save storage state to disk if provided
    if body.storage_state:
        session.add(profile)
        await session.flush()
        path = await StorageService.save_auth_state(profile.id, body.storage_state)
        profile.storage_state_path = str(path)
    else:
        session.add(profile)
        await session.flush()

    await session.refresh(profile)
    return AuthProfileOut.model_validate(profile)


@router.get("/auth-profiles", response_model=list[AuthProfileOut])
async def list_auth_profiles(
    project_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[AuthProfileOut]:
    stmt = select(AuthProfile).order_by(AuthProfile.created_at.desc())
    if project_id:
        stmt = stmt.where(AuthProfile.project_id == project_id)
    result = await session.execute(stmt)
    return [AuthProfileOut.model_validate(p) for p in result.scalars().all()]


@router.get("/auth-profiles/{profile_id}", response_model=AuthProfileOut)
async def get_auth_profile(
    profile_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> AuthProfileOut:
    profile = await session.get(AuthProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Auth profile not found")
    return AuthProfileOut.model_validate(profile)


@router.patch("/auth-profiles/{profile_id}", response_model=AuthProfileOut)
async def update_auth_profile(
    profile_id: uuid.UUID,
    body: AuthProfileUpdate,
    session: AsyncSession = Depends(get_session),
) -> AuthProfileOut:
    profile = await session.get(AuthProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Auth profile not found")

    update_data = body.model_dump(exclude_unset=True)
    if "storage_state" in update_data and update_data["storage_state"] is not None:
        path = await StorageService.save_auth_state(profile_id, update_data["storage_state"])
        profile.storage_state = update_data.pop("storage_state")
        profile.storage_state_path = str(path)

    for field, value in update_data.items():
        setattr(profile, field, value)
    await session.flush()
    await session.refresh(profile)
    return AuthProfileOut.model_validate(profile)


@router.delete("/auth-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_auth_profile(
    profile_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    profile = await session.get(AuthProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Auth profile not found")
    await session.delete(profile)
