"""Tests that exported pytest code uses resilient selectors."""

from app.schemas.test_schemas import (
    AssertionStep,
    AssertionType,
    RecordedStep,
    StepAction,
)
from app.services.codegen import CodeGenerator


def test_exported_code_uses_case_insensitive_role_selectors():
    steps = [
        RecordedStep(action=StepAction.CLICK, selector='role=link[name="PRACTICE"]'),
        RecordedStep(action=StepAction.CLICK, selector='role=button[name="Submit"]'),
    ]
    code = CodeGenerator.export_python("recorded test", steps)

    assert 'role=link[name=\\"PRACTICE\\"i]' in code
    assert 'role=button[name=\\"Submit\\"i]' in code


def test_exported_code_uses_get_by_label_for_label_selectors():
    steps = [
        RecordedStep(
            action=StepAction.FILL,
            selector='internal:label="Username"i',
            value="student",
        )
    ]
    code = CodeGenerator.export_python("login", steps)

    assert 'await page.get_by_label("Username").fill("student")' in code


def test_exported_assertions_use_case_insensitive_role_selectors():
    assertions = [
        AssertionStep(
            assertion_type=AssertionType.TO_BE_VISIBLE,
            selector='role=link[name="COURSES"]',
        )
    ]
    code = CodeGenerator.export_python("assert", [], assertions)

    assert 'role=link[name=\\"COURSES\\"i]' in code
