"""Pydantic v2 schemas for requests, responses, steps, assertions, and configs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class BrowserTypeEnum(str, enum.Enum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class RunStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"


class StepAction(str, enum.Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT_OPTION = "selectOption"
    CHECK = "check"
    UNCHECK = "uncheck"
    PRESS = "press"
    FILE_UPLOAD = "fileUpload"
    IFRAME = "iframe"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    HOVER = "hover"
    DBLCLICK = "dblclick"


class AssertionType(str, enum.Enum):
    TO_BE_VISIBLE = "to_be_visible"
    TO_HAVE_TEXT = "to_have_text"
    TO_HAVE_URL = "to_have_url"
    TO_HAVE_COUNT = "to_have_count"
    TO_HAVE_VALUE = "to_have_value"
    TO_BE_CHECKED = "to_be_checked"
    TO_BE_ENABLED = "to_be_enabled"
    TO_BE_HIDDEN = "to_be_hidden"
    TO_HAVE_ATTRIBUTE = "to_have_attribute"
    TO_CONTAIN_TEXT = "to_contain_text"


class MockAction(str, enum.Enum):
    MOCK = "mock"
    ABORT = "abort"


class ColorScheme(str, enum.Enum):
    LIGHT = "light"
    DARK = "dark"
    NO_PREFERENCE = "no-preference"


# ═══════════════════════════════════════════════════════════════════════
# Step & Assertion schemas
# ═══════════════════════════════════════════════════════════════════════


class RecordedStep(BaseModel):
    """A single recorded user interaction."""

    model_config = ConfigDict(from_attributes=True)

    action: StepAction
    selector: str | None = None
    value: str | None = None
    url: str | None = None
    key: str | None = None  # for press events
    files: list[str] | None = None  # for file upload
    frame_selector: str | None = None  # for iframe targeting
    timeout_ms: int = 30000
    description: str | None = None
    timestamp: float | None = None  # epoch ms when recorded


class AssertionStep(BaseModel):
    """An assertion to verify after a step or at a checkpoint."""

    model_config = ConfigDict(from_attributes=True)

    assertion_type: AssertionType
    selector: str | None = None
    expected_value: str | None = None
    expected_count: int | None = None
    attribute_name: str | None = None  # for to_have_attribute
    timeout_ms: int = 10000
    negate: bool = False  # if True, assert the opposite


# ═══════════════════════════════════════════════════════════════════════
# Device & context configuration
# ═══════════════════════════════════════════════════════════════════════


class GeoLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = None


class ViewportSize(BaseModel):
    width: int = Field(ge=1, default=1280)
    height: int = Field(ge=1, default=720)


class DeviceConfig(BaseModel):
    """Full browser context configuration."""

    model_config = ConfigDict(from_attributes=True)

    device_name: str | None = None  # e.g. "iPhone 14", matches playwright.devices
    viewport: ViewportSize | None = None
    locale: str | None = None  # e.g. "en-US"
    timezone_id: str | None = None  # e.g. "America/New_York"
    geolocation: GeoLocation | None = None
    permissions: list[str] | None = None  # e.g. ["geolocation"]
    color_scheme: ColorScheme | None = None
    user_agent: str | None = None
    is_mobile: bool | None = None
    has_touch: bool | None = None
    device_scale_factor: float | None = None
    extra_http_headers: dict[str, str] | None = None


# ═══════════════════════════════════════════════════════════════════════
# Network mock rules
# ═══════════════════════════════════════════════════════════════════════


class MockRule(BaseModel):
    """Define a network interception / mock rule."""

    model_config = ConfigDict(from_attributes=True)

    url_pattern: str  # glob or regex pattern
    method: str | None = None  # GET, POST, etc.
    action: MockAction = MockAction.MOCK
    response_status: int = 200
    response_body: Any | None = None  # JSON-serialisable body for mocks
    response_headers: dict[str, str] | None = None
    description: str | None = None


# ═══════════════════════════════════════════════════════════════════════
# Project schemas
# ═══════════════════════════════════════════════════════════════════════


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════
# TestSuite schemas
# ═══════════════════════════════════════════════════════════════════════


class TestSuiteCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    tags: list[str] | None = None


class TestSuiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    tags: list[str] | None = None


class TestSuiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════
# TestCase schemas
# ═══════════════════════════════════════════════════════════════════════


class TestCaseCreate(BaseModel):
    suite_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    steps: list[RecordedStep] = Field(default_factory=list)
    assertions: list[AssertionStep] | None = None
    device_config: DeviceConfig | None = None
    mock_rules: list[MockRule] | None = None
    auth_profile_id: uuid.UUID | None = None
    baseline_screenshots: dict[str, str] | None = None


class TestCaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    steps: list[RecordedStep] | None = None
    assertions: list[AssertionStep] | None = None
    device_config: DeviceConfig | None = None
    mock_rules: list[MockRule] | None = None
    auth_profile_id: uuid.UUID | None = None
    baseline_screenshots: dict[str, str] | None = None


class TestCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    suite_id: uuid.UUID
    name: str
    description: str | None
    steps: list[RecordedStep]
    assertions: list[AssertionStep] | None
    device_config: DeviceConfig | None
    mock_rules: list[MockRule] | None
    auth_profile_id: uuid.UUID | None
    baseline_screenshots: dict[str, str] | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════
# AuthProfile schemas
# ═══════════════════════════════════════════════════════════════════════


class AuthProfileCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    storage_state: dict[str, Any] | None = None


class AuthProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    storage_state: dict[str, Any] | None = None


class AuthProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    has_storage_state: bool = False
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════
# TestRun schemas
# ═══════════════════════════════════════════════════════════════════════


class StepResult(BaseModel):
    """Result of a single step execution."""

    step_index: int
    action: str
    status: str  # passed | failed | skipped | cancelled
    duration_ms: int = 0
    error: str | None = None
    screenshot_path: str | None = None
    failure_screenshot_path: str | None = None
    diff_screenshot_path: str | None = None
    visual_diff_percent: float | None = None

    @field_serializer(
        "screenshot_path", "failure_screenshot_path", "diff_screenshot_path"
    )
    def _artifact_filename(self, value: str | None) -> str | None:
        """Never expose server-local filesystem paths in API payloads."""
        return Path(value).name if value else None


class TestCaseResult(BaseModel):
    """Aggregate result for one test case within a run."""

    test_case_id: uuid.UUID
    test_case_name: str
    status: str  # passed | failed | error | skipped | cancelled
    duration_ms: int = 0
    step_results: list[StepResult] = Field(default_factory=list)
    error: str | None = None


class TestRunCreate(BaseModel):
    suite_id: uuid.UUID
    browser: BrowserTypeEnum = BrowserTypeEnum.CHROMIUM
    trigger_source: str | None = None


class TestRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    suite_id: uuid.UUID
    status: RunStatusEnum
    browser: BrowserTypeEnum
    results: list[TestCaseResult] | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    trigger_source: str | None
    created_at: datetime


class CancelRunResponse(BaseModel):
    run_id: uuid.UUID
    status: str
    message: str


# ═══════════════════════════════════════════════════════════════════════
# Recorder session schemas
# ═══════════════════════════════════════════════════════════════════════


class RecorderStartRequest(BaseModel):
    url: str
    browser: BrowserTypeEnum = BrowserTypeEnum.CHROMIUM
    device_config: DeviceConfig | None = None
    headless: bool = False


class RecorderStartResponse(BaseModel):
    session_id: str
    ws_url: str  # WebSocket URL for live step streaming


class RecorderStopResponse(BaseModel):
    session_id: str
    steps: list[RecordedStep]
    duration_ms: int


class InjectAssertionRequest(BaseModel):
    """Add an assertion mid-recording."""

    assertion: AssertionStep


# ═══════════════════════════════════════════════════════════════════════
# Code export schemas
# ═══════════════════════════════════════════════════════════════════════


class CodeExportResponse(BaseModel):
    language: str
    code: str
    filename: str


# ═══════════════════════════════════════════════════════════════════════
# Webhook schemas
# ═══════════════════════════════════════════════════════════════════════


class WebhookTriggerResponse(BaseModel):
    run_id: uuid.UUID
    status: str
    message: str


class JUnitTestReport(BaseModel):
    """Minimal JUnit-style test report."""

    suite_name: str
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_ms: int
    test_cases: list[TestCaseResult]


# ═══════════════════════════════════════════════════════════════════════
# WebSocket message schemas
# ═══════════════════════════════════════════════════════════════════════


class WSStepMessage(BaseModel):
    """WebSocket message for a recorded step."""

    type: Literal["step"] = "step"
    session_id: str
    step: RecordedStep


class WSRunProgress(BaseModel):
    """WebSocket message for run progress."""

    type: Literal["progress"] = "progress"
    run_id: str
    test_case_id: str
    step_index: int
    status: str
    duration_ms: int = 0
    error: str | None = None


class WSRunComplete(BaseModel):
    """WebSocket message when a run finishes."""

    type: Literal["complete"] = "complete"
    run_id: str
    status: str
    duration_ms: int
    results: list[TestCaseResult]
