"""Code exporter — transpiles JSON test steps into idiomatic pytest-playwright code."""

from __future__ import annotations

import textwrap
from typing import Any

from app.schemas.test_schemas import (
    AssertionStep,
    AssertionType,
    DeviceConfig,
    MockAction,
    MockRule,
    RecordedStep,
    StepAction,
)


class CodeGenerator:
    """Converts structured test definitions into runnable Python test code."""

    @staticmethod
    def export_python(
        test_name: str,
        steps: list[RecordedStep],
        assertions: list[AssertionStep] | None = None,
        device_config: DeviceConfig | None = None,
        mock_rules: list[MockRule] | None = None,
        auth_storage_state_path: str | None = None,
    ) -> str:
        """Generate a complete, standalone pytest-playwright async test file."""
        lines: list[str] = []

        # ── Imports ─────────────────────────────────────────────────
        lines.append('"""Auto-generated Playwright test — do not edit manually."""')
        lines.append("")
        lines.append("import json")
        lines.append("import re")
        lines.append("")
        lines.append("import pytest")
        lines.append("from playwright.async_api import Page, BrowserContext, expect")
        lines.append("")
        lines.append("")

        # ── Fixture for browser context ─────────────────────────────
        lines.append("@pytest.fixture")
        lines.append("async def context(browser):")
        lines.append('    """Create a browser context with the configured options."""')

        ctx_args: list[str] = []
        if device_config:
            if device_config.viewport:
                ctx_args.append(
                    f'    viewport={{"width": {device_config.viewport.width}, "height": {device_config.viewport.height}}}'
                )
            if device_config.locale:
                ctx_args.append(f'    locale="{device_config.locale}"')
            if device_config.timezone_id:
                ctx_args.append(f'    timezone_id="{device_config.timezone_id}"')
            if device_config.geolocation:
                ctx_args.append(
                    f"    geolocation={{\"latitude\": {device_config.geolocation.latitude}, "
                    f'"longitude": {device_config.geolocation.longitude}}}'
                )
            if device_config.permissions:
                ctx_args.append(f"    permissions={device_config.permissions}")
            if device_config.color_scheme:
                ctx_args.append(f'    color_scheme="{device_config.color_scheme.value}"')
            if device_config.user_agent:
                ctx_args.append(f'    user_agent="{device_config.user_agent}"')
            if device_config.is_mobile is not None:
                ctx_args.append(f"    is_mobile={device_config.is_mobile}")
            if device_config.has_touch is not None:
                ctx_args.append(f"    has_touch={device_config.has_touch}")
            if device_config.device_scale_factor is not None:
                ctx_args.append(f"    device_scale_factor={device_config.device_scale_factor}")

        if auth_storage_state_path:
            ctx_args.append(f'    storage_state="{auth_storage_state_path}"')

        if ctx_args:
            lines.append("    ctx = await browser.new_context(")
            for arg in ctx_args:
                lines.append(f"    {arg},")
            lines.append("    )")
        else:
            lines.append("    ctx = await browser.new_context()")

        lines.append("    yield ctx")
        lines.append("    await ctx.close()")
        lines.append("")
        lines.append("")

        # ── Fixture for page ────────────────────────────────────────
        lines.append("@pytest.fixture")
        lines.append("async def page(context: BrowserContext):")
        lines.append('    """Create a new page from the context."""')
        lines.append("    page = await context.new_page()")

        # Network mocking in fixture
        if mock_rules:
            lines.append("")
            lines.append("    # Network mocking rules")
            for rule in mock_rules:
                lines.extend(_generate_mock_rule_code(rule, indent=4))

        lines.append("    yield page")
        lines.append("    await page.close()")
        lines.append("")
        lines.append("")

        # ── Test function ───────────────────────────────────────────
        safe_name = _safe_function_name(test_name)
        lines.append(f"@pytest.mark.asyncio")
        lines.append(f"async def test_{safe_name}(page: Page):")
        lines.append(f'    """Test: {test_name}"""')
        lines.append("")

        for idx, step in enumerate(steps):
            comment = f"    # Step {idx + 1}: {step.action.value}"
            if step.description:
                comment += f" — {step.description}"
            lines.append(comment)
            lines.extend(_generate_step_code(step, indent=4))
            lines.append("")

        # Assertions
        if assertions:
            lines.append("    # ── Assertions ──────────────────────────────────")
            for a_idx, assertion in enumerate(assertions):
                lines.append(f"    # Assertion {a_idx + 1}: {assertion.assertion_type.value}")
                lines.extend(_generate_assertion_code(assertion, indent=4))
                lines.append("")

        # Ensure the test body is not empty
        if not steps and not assertions:
            lines.append("    pass")

        lines.append("")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Private helper functions
# ═══════════════════════════════════════════════════════════════════════


def _safe_function_name(name: str) -> str:
    """Convert an arbitrary test name into a valid Python identifier."""
    import re

    name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower().strip())
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "unnamed"
    if name[0].isdigit():
        name = f"t_{name}"
    return name


def _esc(value: str) -> str:
    """Escape a string for safe embedding in Python source code."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _generate_step_code(step: RecordedStep, indent: int = 4) -> list[str]:
    """Generate Python code lines for a single step."""
    pad = " " * indent
    lines: list[str] = []

    match step.action:
        case StepAction.NAVIGATE:
            url = _esc(step.url or "")
            lines.append(f'{pad}await page.goto("{url}", wait_until="domcontentloaded")')

        case StepAction.CLICK:
            sel = _esc(step.selector or "")
            lines.append(f'{pad}await page.click("{sel}")')

        case StepAction.FILL:
            sel = _esc(step.selector or "")
            val = _esc(step.value or "")
            lines.append(f'{pad}await page.fill("{sel}", "{val}")')

        case StepAction.SELECT_OPTION:
            sel = _esc(step.selector or "")
            val = _esc(step.value or "")
            lines.append(f'{pad}await page.select_option("{sel}", "{val}")')

        case StepAction.CHECK:
            sel = _esc(step.selector or "")
            lines.append(f'{pad}await page.check("{sel}")')

        case StepAction.UNCHECK:
            sel = _esc(step.selector or "")
            lines.append(f'{pad}await page.uncheck("{sel}")')

        case StepAction.PRESS:
            sel = _esc(step.selector or "")
            key = _esc(step.key or "")
            lines.append(f'{pad}await page.press("{sel}", "{key}")')

        case StepAction.FILE_UPLOAD:
            sel = _esc(step.selector or "")
            files = step.files or []
            files_repr = repr(files)
            lines.append(f'{pad}await page.set_input_files("{sel}", {files_repr})')

        case StepAction.HOVER:
            sel = _esc(step.selector or "")
            lines.append(f'{pad}await page.hover("{sel}")')

        case StepAction.DBLCLICK:
            sel = _esc(step.selector or "")
            lines.append(f'{pad}await page.dblclick("{sel}")')

        case StepAction.WAIT:
            lines.append(f"{pad}await page.wait_for_timeout(1000)")

        case StepAction.SCREENSHOT:
            lines.append(f'{pad}await page.screenshot(path="screenshot_step.png", full_page=True)')

        case StepAction.IFRAME:
            if step.frame_selector:
                sel = _esc(step.frame_selector)
                lines.append(f'{pad}frame_element = await page.query_selector("{sel}")')
                lines.append(f"{pad}frame = await frame_element.content_frame()")
                lines.append(f"{pad}# Use `frame` for subsequent iframe actions")

    return lines


def _generate_assertion_code(assertion: AssertionStep, indent: int = 4) -> list[str]:
    """Generate Python code for a single assertion."""
    pad = " " * indent
    lines: list[str] = []
    sel = _esc(assertion.selector or "")
    negate = ".not_" if assertion.negate else ""

    match assertion.assertion_type:
        case AssertionType.TO_BE_VISIBLE:
            lines.append(f'{pad}await expect(page.locator("{sel}")){negate}.to_be_visible()')

        case AssertionType.TO_BE_HIDDEN:
            lines.append(f'{pad}await expect(page.locator("{sel}")){negate}.to_be_hidden()')

        case AssertionType.TO_HAVE_TEXT:
            val = _esc(assertion.expected_value or "")
            lines.append(
                f'{pad}await expect(page.locator("{sel}")){negate}.to_have_text("{val}")'
            )

        case AssertionType.TO_CONTAIN_TEXT:
            val = _esc(assertion.expected_value or "")
            lines.append(
                f'{pad}await expect(page.locator("{sel}")){negate}.to_contain_text("{val}")'
            )

        case AssertionType.TO_HAVE_URL:
            val = _esc(assertion.expected_value or "")
            lines.append(f'{pad}await expect(page){negate}.to_have_url("{val}")')

        case AssertionType.TO_HAVE_COUNT:
            count = assertion.expected_count or 0
            lines.append(
                f'{pad}await expect(page.locator("{sel}")){negate}.to_have_count({count})'
            )

        case AssertionType.TO_HAVE_VALUE:
            val = _esc(assertion.expected_value or "")
            lines.append(
                f'{pad}await expect(page.locator("{sel}")){negate}.to_have_value("{val}")'
            )

        case AssertionType.TO_BE_CHECKED:
            lines.append(f'{pad}await expect(page.locator("{sel}")){negate}.to_be_checked()')

        case AssertionType.TO_BE_ENABLED:
            lines.append(f'{pad}await expect(page.locator("{sel}")){negate}.to_be_enabled()')

        case AssertionType.TO_HAVE_ATTRIBUTE:
            attr = _esc(assertion.attribute_name or "")
            val = _esc(assertion.expected_value or "")
            lines.append(
                f'{pad}await expect(page.locator("{sel}")){negate}'
                f'.to_have_attribute("{attr}", "{val}")'
            )

    return lines


def _generate_mock_rule_code(rule: MockRule, indent: int = 4) -> list[str]:
    """Generate Python code that sets up a network mock rule."""
    pad = " " * indent
    lines: list[str] = []
    pattern = _esc(rule.url_pattern)

    if rule.action == MockAction.ABORT:
        lines.append(f'{pad}await page.route("{pattern}", lambda route, _: route.abort("failed"))')
    else:
        lines.append(f"{pad}async def _mock_{abs(hash(rule.url_pattern)) % 10000}(route, request):")
        if rule.method:
            lines.append(f'{pad}    if request.method.upper() != "{rule.method.upper()}":')
            lines.append(f"{pad}        await route.fallback()")
            lines.append(f"{pad}        return")

        body_repr: str
        if isinstance(rule.response_body, (dict, list)):
            body_repr = f"json.dumps({repr(rule.response_body)})"
        elif rule.response_body is not None:
            body_repr = repr(str(rule.response_body))
        else:
            body_repr = '""'

        headers = {"content-type": "application/json"}
        if rule.response_headers:
            headers.update(rule.response_headers)

        lines.append(f"{pad}    await route.fulfill(")
        lines.append(f"{pad}        status={rule.response_status},")
        lines.append(f"{pad}        headers={repr(headers)},")
        lines.append(f"{pad}        body={body_repr},")
        lines.append(f"{pad}    )")
        lines.append(
            f'{pad}await page.route("{pattern}", _mock_{abs(hash(rule.url_pattern)) % 10000})'
        )

    return lines
