"""Browser tests for recorder selector generation and step compaction."""

import json

import pytest
from playwright.async_api import async_playwright

from app.schemas.test_schemas import RecordedStep, StepAction
from app.services.recorder import RECORDER_JS, RecorderSession

HTML = """
<!doctype html>
<style>
  .menu a { text-transform: uppercase; }
</style>
<nav class="menu">
  <a href="#">Practice</a>
  <a href="#">Courses</a>
</nav>
<label for="username">Username</label>
<input id="username">
<button aria-label="Send form">Go</button>
"""


async def _record_steps(actions) -> list[dict]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        captured: list[dict] = []

        async def on_step(raw_json: str) -> None:
            captured.append(json.loads(raw_json))

        await page.expose_function("__pw_on_step", on_step)
        await page.set_content(HTML)
        await page.evaluate(RECORDER_JS)
        await actions(page)
        await page.wait_for_timeout(800)
        await browser.close()
        return captured


async def test_css_uppercase_text_does_not_leak_into_selector():
    steps = await _record_steps(lambda page: page.click("text=Practice"))

    assert steps
    assert steps[0]["selector"] == 'role=link[name="Practice"i]'


async def test_aria_label_is_used_for_accessible_name():
    steps = await _record_steps(lambda page: page.click("text=Go"))

    assert steps
    assert steps[0]["selector"] == 'role=button[name="Send form"i]'


async def test_label_selector_is_recorded_for_inputs():
    steps = await _record_steps(lambda page: page.fill("#username", "student"))

    assert steps
    assert steps[0]["selector"] == 'internal:label="Username"i'


def test_compaction_keeps_only_last_fill_for_same_selector():
    steps = [
        RecordedStep(action=StepAction.CLICK, selector='internal:label="Username"i'),
        RecordedStep(action=StepAction.FILL, selector='internal:label="Username"i', value="s"),
        RecordedStep(action=StepAction.FILL, selector='internal:label="Username"i', value="student"),
        RecordedStep(action=StepAction.FILL, selector='internal:label="Password"i', value="P"),
        RecordedStep(action=StepAction.FILL, selector='internal:label="Password"i', value="Password123"),
    ]

    compacted = RecorderSession._compact_steps(steps)

    assert [step.action for step in compacted] == [
        StepAction.CLICK,
        StepAction.FILL,
        StepAction.FILL,
    ]
    assert compacted[1].value == "student"
    assert compacted[2].value == "Password123"


def test_compaction_does_not_merge_different_selectors():
    steps = [
        RecordedStep(action=StepAction.FILL, selector="#a", value="1"),
        RecordedStep(action=StepAction.FILL, selector="#b", value="2"),
    ]

    assert RecorderSession._compact_steps(steps) == steps
