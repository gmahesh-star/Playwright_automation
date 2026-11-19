"""Tests for save-time selector canonicalization in the API layer."""

from app.api.routes_tests import _canonicalize_assertions, _canonicalize_steps
from app.schemas.test_schemas import (
    AssertionStep,
    AssertionType,
    RecordedStep,
    StepAction,
)


def test_canonicalize_steps_accepts_models_and_dicts():
    model = RecordedStep(
        action=StepAction.CLICK,
        selector='role=link[name="PRACTICE"]',
    )
    as_dict = model.model_dump()

    for step in (model, as_dict):
        payload = _canonicalize_steps([step])
        assert payload[0]["selector"] == 'role=link[name="PRACTICE"i]'


def test_canonicalize_assertions_accepts_models_and_dicts():
    model = AssertionStep(
        assertion_type=AssertionType.TO_BE_VISIBLE,
        selector='role=link[name="COURSES"]',
    )
    as_dict = model.model_dump()

    for assertion in (model, as_dict):
        payload = _canonicalize_assertions([assertion])
        assert payload[0]["selector"] == 'role=link[name="COURSES"i]'
