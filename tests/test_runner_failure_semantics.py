"""Runner tests for fail-fast execution and selector normalization."""

import uuid

from app.core.config import settings
from app.schemas.test_schemas import (
    AssertionStep,
    AssertionType,
    RecordedStep,
    StepAction,
)
from app.services.runner import TestRunner as Runner


async def test_remaining_steps_are_skipped_after_first_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", tmp_path)

    steps = [
        RecordedStep(
            action=StepAction.NAVIGATE,
            url='data:text/html,<button id="ok">OK</button>',
            timeout_ms=5000,
        ),
        RecordedStep(action=StepAction.CLICK, selector="#missing", timeout_ms=500),
        RecordedStep(action=StepAction.CLICK, selector="#ok", timeout_ms=5000),
    ]

    async with Runner(run_id=uuid.uuid4()) as runner:
        result = await runner.run_test_case(
            test_case_id=uuid.uuid4(),
            test_case_name="fail-fast",
            steps=steps,
        )

    assert result.status == "failed"
    assert [step.status for step in result.step_results] == ["passed", "failed", "skipped"]
    assert result.step_results[2].error == "Not executed: previous step failed"


async def test_case_insensitive_role_selector_is_normalized(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", tmp_path)

    html = (
        'data:text/html,<style>.menu a{text-transform:uppercase}</style>'
        '<nav class="menu"><a href="/x">Practice</a></nav>'
    )
    steps = [
        RecordedStep(action=StepAction.NAVIGATE, url=html, timeout_ms=5000),
        RecordedStep(
            action=StepAction.CLICK,
            selector='role=link[name="PRACTICE"]',
            timeout_ms=5000,
        ),
    ]

    async with Runner(run_id=uuid.uuid4()) as runner:
        result = await runner.run_test_case(
            test_case_id=uuid.uuid4(),
            test_case_name="role-normalization",
            steps=steps,
        )

    assert result.status == "passed"
    assert [step.status for step in result.step_results] == ["passed", "passed"]


async def test_assertions_are_skipped_after_failed_step(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", tmp_path)

    steps = [
        RecordedStep(
            action=StepAction.NAVIGATE,
            url="data:text/html,<h1>Hello</h1>",
            timeout_ms=5000,
        ),
        RecordedStep(action=StepAction.CLICK, selector="#missing", timeout_ms=500),
    ]
    assertions = [
        AssertionStep(
            assertion_type=AssertionType.TO_BE_VISIBLE,
            selector="h1",
        )
    ]

    async with Runner(run_id=uuid.uuid4()) as runner:
        result = await runner.run_test_case(
            test_case_id=uuid.uuid4(),
            test_case_name="assertions-skipped",
            steps=steps,
            assertions=assertions,
        )

    assert [step.status for step in result.step_results] == ["passed", "failed", "skipped"]
    assert result.step_results[2].action == "assert_to_be_visible"
