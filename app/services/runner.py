"""Comprehensive async Playwright test runner with full feature support."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image
from playwright.async_api import (
    Browser,
    BrowserContext,
    BrowserType,
    Dialog,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)

from app.core.config import settings
from app.schemas.test_schemas import (
    AssertionStep,
    AssertionType,
    BrowserTypeEnum,
    DeviceConfig,
    MockAction,
    MockRule,
    RecordedStep,
    StepAction,
    StepResult,
    TestCaseResult,
)
from app.services.selectors import GET_BY_LABEL_PREFIX, canonicalize_selector
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


class VisualComparer:
    """Compare screenshots against baselines using Pillow + pixelmatch."""

    @staticmethod
    async def compare(
        actual_path: Path,
        baseline_path: Path,
        diff_path: Path,
        threshold: float = 0.1,
    ) -> tuple[bool, float]:
        """Compare two images. Returns (passed, diff_ratio)."""
        try:
            from pixelmatch import pixelmatch  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("pixelmatch not installed; skipping visual diff")
            return True, 0.0

        if not baseline_path.exists():
            logger.info("No baseline at %s; saving current as baseline", baseline_path)
            import shutil
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(actual_path, baseline_path)
            return True, 0.0

        img_a = Image.open(baseline_path).convert("RGBA")
        img_b = Image.open(actual_path).convert("RGBA")

        # Resize to same dimensions if needed
        if img_a.size != img_b.size:
            img_b = img_b.resize(img_a.size, Image.LANCZOS)

        width, height = img_a.size
        diff_img = Image.new("RGBA", (width, height))

        num_diff_pixels: int = pixelmatch(
            img_a.tobytes(),
            img_b.tobytes(),
            width,
            height,
            diff_img.tobytes(),
            threshold=0.1,
            alpha=0.5,
        )

        total_pixels = width * height
        diff_ratio = num_diff_pixels / total_pixels if total_pixels else 0.0

        diff_img.save(diff_path)

        passed = diff_ratio <= threshold
        return passed, diff_ratio


class TestRunner:
    """Executes test cases against a Playwright browser with full feature set."""

    def __init__(
        self,
        run_id: uuid.UUID,
        browser_type: BrowserTypeEnum = BrowserTypeEnum.CHROMIUM,
        on_progress: Callable[..., Any] | None = None,
        cancel_check: Callable[[], Any] | None = None,
    ) -> None:
        self.run_id = run_id
        self.browser_type = browser_type
        self._on_progress = on_progress
        self._cancel_check = cancel_check
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    @staticmethod
    def _wait_duration_ms(step: RecordedStep) -> int:
        """Resolve a wait step duration, defaulting to 1s for legacy steps."""
        if step.value:
            try:
                value = int(float(step.value))
            except (TypeError, ValueError):
                return 1000
            return max(0, min(value, 60_000))
        return 1000

    async def _is_cancelled(self) -> bool:
        if self._cancel_check is None:
            return False
        try:
            result = self._cancel_check()
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)
        except Exception:
            return False

    async def __aenter__(self) -> TestRunner:
        self._playwright = await async_playwright().start()
        launcher: BrowserType = {
            BrowserTypeEnum.CHROMIUM: self._playwright.chromium,
            BrowserTypeEnum.FIREFOX: self._playwright.firefox,
            BrowserTypeEnum.WEBKIT: self._playwright.webkit,
        }[self.browser_type]
        self._browser = await launcher.launch(headless=settings.HEADLESS)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

    @staticmethod
    def _normalize_selector(selector: str) -> str:
        """Convert non-standard recorder selectors to consistent Playwright selectors."""
        return canonicalize_selector(selector) or ""

    @staticmethod
    def _get_locator(frame: "Page", selector: str):
        """Return a Playwright locator for the given (normalized) selector."""
        if selector.startswith(GET_BY_LABEL_PREFIX):
            label_text = selector[len(GET_BY_LABEL_PREFIX):]
            return frame.get_by_label(label_text)
        return frame.locator(selector)

    async def run_test_case(
        self,
        test_case_id: uuid.UUID,
        test_case_name: str,
        steps: list[RecordedStep],
        assertions: list[AssertionStep] | None = None,
        device_config: DeviceConfig | None = None,
        mock_rules: list[MockRule] | None = None,
        auth_profile_id: uuid.UUID | None = None,
        baseline_screenshots: dict[str, str] | None = None,
    ) -> TestCaseResult:
        """Execute a single test case with full Playwright capabilities."""
        assert self._playwright is not None
        assert self._browser is not None

        start = time.monotonic()
        step_results: list[StepResult] = []
        overall_status = "passed"
        overall_error: str | None = None

        # Build context options
        ctx_kwargs: dict[str, Any] = {
            "record_video_dir": str(StorageService.video_dir(self.run_id)),
        }

        if device_config:
            if device_config.device_name:
                device_desc = self._playwright.devices.get(device_config.device_name, {})
                ctx_kwargs.update(device_desc)
            if device_config.viewport:
                ctx_kwargs["viewport"] = {
                    "width": device_config.viewport.width,
                    "height": device_config.viewport.height,
                }
            if device_config.locale:
                ctx_kwargs["locale"] = device_config.locale
            if device_config.timezone_id:
                ctx_kwargs["timezone_id"] = device_config.timezone_id
            if device_config.geolocation:
                ctx_kwargs["geolocation"] = {
                    "latitude": device_config.geolocation.latitude,
                    "longitude": device_config.geolocation.longitude,
                }
                ctx_kwargs.setdefault("permissions", []).append("geolocation")
            if device_config.permissions:
                perms = ctx_kwargs.get("permissions", [])
                perms.extend(device_config.permissions)
                ctx_kwargs["permissions"] = list(set(perms))
            if device_config.color_scheme:
                ctx_kwargs["color_scheme"] = device_config.color_scheme.value
            if device_config.user_agent:
                ctx_kwargs["user_agent"] = device_config.user_agent
            if device_config.is_mobile is not None:
                ctx_kwargs["is_mobile"] = device_config.is_mobile
            if device_config.has_touch is not None:
                ctx_kwargs["has_touch"] = device_config.has_touch
            if device_config.device_scale_factor is not None:
                ctx_kwargs["device_scale_factor"] = device_config.device_scale_factor
            if device_config.extra_http_headers:
                ctx_kwargs["extra_http_headers"] = device_config.extra_http_headers

        # Auth state reuse
        if auth_profile_id:
            state_path = StorageService.auth_state_path(auth_profile_id)
            if state_path.exists():
                ctx_kwargs["storage_state"] = str(state_path)
                logger.info("Loading auth state from %s", state_path)

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            context = await self._browser.new_context(**ctx_kwargs)

            # ── Tracing ─────────────────────────────────────────────
            await context.tracing.start(
                screenshots=True, snapshots=True, sources=True
            )

            # ── Network mocking ─────────────────────────────────────
            if mock_rules:
                for rule in mock_rules:
                    await self._setup_mock_rule(context, rule)

            # ── Multi-tab / dialog handling ─────────────────────────
            new_pages: list[Page] = []
            context.on("page", lambda p: new_pages.append(p))

            page = await context.new_page()

            # Dialog handler (auto-accept alerts/confirms)
            async def _handle_dialog(dialog: Dialog) -> None:
                logger.info("Dialog detected: type=%s message=%s", dialog.type, dialog.message)
                await dialog.accept()

            page.on("dialog", _handle_dialog)

            # Emit test case start event
            if self._on_progress:
                try:
                    result = self._on_progress(
                        type="test_case_start",
                        run_id=str(self.run_id),
                        test_case_id=str(test_case_id),
                        test_case_name=test_case_name,
                        total_steps=len(steps),
                    )
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass

            # ── Execute steps ───────────────────────────────────────
            step_failed = False
            cancelled = False
            for idx, step in enumerate(steps):
                if cancelled:
                    skipped = StepResult(
                        step_index=idx,
                        action=step.action.value,
                        status="skipped",
                        error="Run cancelled",
                    )
                    step_results.append(skipped)
                    if self._on_progress:
                        await self._emit_progress(test_case_id, idx, skipped)
                    continue

                if step_failed:
                    skipped = StepResult(
                        step_index=idx,
                        action=step.action.value,
                        status="skipped",
                        error="Not executed: previous step failed",
                    )
                    step_results.append(skipped)
                    if self._on_progress:
                        await self._emit_progress(test_case_id, idx, skipped)
                    continue

                if await self._is_cancelled():
                    cancelled = True
                    overall_status = "cancelled"
                    overall_error = "Run cancelled"
                    skipped = StepResult(
                        step_index=idx,
                        action=step.action.value,
                        status="skipped",
                        error="Run cancelled",
                    )
                    step_results.append(skipped)
                    if self._on_progress:
                        await self._emit_progress(test_case_id, idx, skipped)
                    continue

                step_start = time.monotonic()
                sr = await self._execute_step(page, step, idx, test_case_id, baseline_screenshots)
                sr.duration_ms = int((time.monotonic() - step_start) * 1000)

                if sr.status == "failed":
                    overall_status = "failed"
                    step_failed = True
                    if not overall_error:
                        overall_error = sr.error
                    # Take failure screenshot and attach it to the result.
                    fail_ss = StorageService.screenshot_path(
                        self.run_id, test_case_id, idx, suffix="_failure"
                    )
                    try:
                        await page.screenshot(path=str(fail_ss), full_page=True)
                        sr.failure_screenshot_path = fail_ss.name
                    except Exception:
                        pass

                step_results.append(sr)

                # Emit progress after the failure screenshot is attached.
                if self._on_progress:
                    await self._emit_progress(test_case_id, idx, sr)

            # ── Execute assertions ──────────────────────────────────
            if assertions:
                if overall_status == "passed" and not cancelled:
                    for a_idx, assertion in enumerate(assertions):
                        if await self._is_cancelled():
                            cancelled = True
                            overall_status = "cancelled"
                            overall_error = "Run cancelled"
                            for rest_idx in range(a_idx, len(assertions)):
                                step_results.append(
                                    StepResult(
                                        step_index=len(steps) + rest_idx,
                                        action=f"assert_{assertions[rest_idx].assertion_type.value}",
                                        status="skipped",
                                        error="Run cancelled",
                                    )
                                )
                            break
                        a_start = time.monotonic()
                        a_result = await self._execute_assertion(page, assertion, len(steps) + a_idx)
                        a_result.duration_ms = int((time.monotonic() - a_start) * 1000)
                        step_results.append(a_result)
                        if a_result.status == "failed":
                            overall_status = "failed"
                            overall_error = a_result.error
                            break
                else:
                    reason = "Run cancelled" if cancelled else "Not executed: previous step failed"
                    for a_idx, assertion in enumerate(assertions):
                        step_results.append(
                            StepResult(
                                step_index=len(steps) + a_idx,
                                action=f"assert_{assertion.assertion_type.value}",
                                status="skipped",
                                error=reason,
                            )
                        )

            # ── Save auth state if needed ───────────────────────────
            if auth_profile_id and overall_status == "passed":
                state_path = StorageService.auth_state_path(auth_profile_id)
                await context.storage_state(path=str(state_path))

        except PlaywrightTimeout as exc:
            overall_status = "failed"
            overall_error = f"Playwright timeout: {exc}"
            logger.error("Timeout during test case %s: %s", test_case_name, exc)
        except Exception as exc:
            overall_status = "error"
            overall_error = f"Unexpected error: {type(exc).__name__}: {exc}"
            logger.exception("Error during test case %s", test_case_name)
        finally:
            # Stop tracing and save
            if context:
                trace_path = StorageService.trace_path(self.run_id, test_case_id)
                try:
                    await context.tracing.stop(path=str(trace_path))
                except Exception as exc:
                    logger.warning("Failed to save trace: %s", exc)
                try:
                    await context.close()
                except Exception:
                    pass

        duration_ms = int((time.monotonic() - start) * 1000)
        return TestCaseResult(
            test_case_id=test_case_id,
            test_case_name=test_case_name,
            status=overall_status,
            duration_ms=duration_ms,
            step_results=step_results,
            error=overall_error,
        )

    async def _execute_step(
        self,
        page: Page,
        step: RecordedStep,
        index: int,
        test_case_id: uuid.UUID,
        baseline_screenshots: dict[str, str] | None,
    ) -> StepResult:
        """Execute a single step and return the result."""
        try:
            timeout = step.timeout_ms

            # Normalize the selector to handle legacy/custom engines
            selector = self._normalize_selector(step.selector) if step.selector else None

            target_frame = page
            if step.frame_selector:
                frame_el = await page.query_selector(step.frame_selector)
                if frame_el:
                    frame = await frame_el.content_frame()
                    if frame:
                        target_frame = frame  # type: ignore[assignment]

            match step.action:
                case StepAction.NAVIGATE:
                    if step.url:
                        await page.goto(step.url, wait_until="domcontentloaded", timeout=timeout)

                case StepAction.CLICK:
                    if selector:
                        loc = self._get_locator(target_frame, selector)
                        await loc.click(timeout=timeout)

                case StepAction.FILL:
                    if selector and step.value is not None:
                        loc = self._get_locator(target_frame, selector)
                        await loc.fill(step.value, timeout=timeout)

                case StepAction.SELECT_OPTION:
                    if selector and step.value is not None:
                        loc = self._get_locator(target_frame, selector)
                        await loc.select_option(step.value, timeout=timeout)

                case StepAction.CHECK:
                    if selector:
                        loc = self._get_locator(target_frame, selector)
                        await loc.check(timeout=timeout)

                case StepAction.UNCHECK:
                    if selector:
                        loc = self._get_locator(target_frame, selector)
                        await loc.uncheck(timeout=timeout)

                case StepAction.PRESS:
                    if selector and step.key:
                        loc = self._get_locator(target_frame, selector)
                        await loc.press(step.key, timeout=timeout)

                case StepAction.FILE_UPLOAD:
                    if selector and step.files:
                        loc = self._get_locator(target_frame, selector)
                        await loc.set_input_files(step.files, timeout=timeout)

                case StepAction.HOVER:
                    if selector:
                        loc = self._get_locator(target_frame, selector)
                        await loc.hover(timeout=timeout)

                case StepAction.DBLCLICK:
                    if selector:
                        loc = self._get_locator(target_frame, selector)
                        await loc.dblclick(timeout=timeout)

                case StepAction.WAIT:
                    await page.wait_for_timeout(self._wait_duration_ms(step))

                case StepAction.SCREENSHOT:
                    ss_path = StorageService.screenshot_path(
                        self.run_id, test_case_id, index
                    )
                    await page.screenshot(path=str(ss_path), full_page=True)

                    # Visual regression comparison
                    if baseline_screenshots and str(index) in baseline_screenshots:
                        baseline_p = Path(baseline_screenshots[str(index)])
                        diff_p = StorageService.diff_screenshot_path(
                            self.run_id, test_case_id, index
                        )
                        passed, diff_pct = await VisualComparer.compare(
                            ss_path, baseline_p, diff_p, settings.VISUAL_DIFF_THRESHOLD
                        )
                        if not passed:
                            return StepResult(
                                step_index=index,
                                action=step.action.value,
                                status="failed",
                                error=f"Visual diff {diff_pct:.2%} exceeds threshold {settings.VISUAL_DIFF_THRESHOLD:.2%}",
                                screenshot_path=ss_path.name,
                                diff_screenshot_path=diff_p.name,
                                visual_diff_percent=diff_pct,
                            )
                        return StepResult(
                            step_index=index,
                            action=step.action.value,
                            status="passed",
                            screenshot_path=ss_path.name,
                            diff_screenshot_path=diff_p.name,
                            visual_diff_percent=diff_pct,
                        )

                case StepAction.IFRAME:
                    pass  # iframe targeting handled via frame_selector above

            # Take a step screenshot for forensics
            ss_path = StorageService.screenshot_path(self.run_id, test_case_id, index)
            try:
                await page.screenshot(path=str(ss_path))
            except Exception:
                pass

            # Visual regression if baseline exists
            visual_diff: float | None = None
            diff_name: str | None = None
            if baseline_screenshots and str(index) in baseline_screenshots:
                baseline_p = Path(baseline_screenshots[str(index)])
                diff_p = StorageService.diff_screenshot_path(self.run_id, test_case_id, index)
                passed, diff_pct = await VisualComparer.compare(
                    ss_path, baseline_p, diff_p, settings.VISUAL_DIFF_THRESHOLD
                )
                visual_diff = diff_pct
                diff_name = diff_p.name
                if not passed:
                    return StepResult(
                        step_index=index,
                        action=step.action.value,
                        status="failed",
                        error=f"Visual diff {diff_pct:.2%} exceeds threshold {settings.VISUAL_DIFF_THRESHOLD:.2%}",
                        screenshot_path=ss_path.name,
                        diff_screenshot_path=diff_name,
                        visual_diff_percent=diff_pct,
                    )

            return StepResult(
                step_index=index,
                action=step.action.value,
                status="passed",
                screenshot_path=ss_path.name,
                diff_screenshot_path=diff_name,
                visual_diff_percent=visual_diff,
            )

        except PlaywrightTimeout as exc:
            return StepResult(
                step_index=index,
                action=step.action.value,
                status="failed",
                error=f"Timeout after {step.timeout_ms}ms on {step.action.value} "
                      f"(selector: {step.selector}): {exc}",
            )
        except Exception as exc:
            return StepResult(
                step_index=index,
                action=step.action.value,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )

    async def _execute_assertion(
        self, page: Page, assertion: AssertionStep, index: int
    ) -> StepResult:
        """Execute a single assertion and return step-level result."""
        try:
            timeout = assertion.timeout_ms
            selector = canonicalize_selector(assertion.selector) if assertion.selector else None
            locator = self._get_locator(page, selector) if selector else None

            match assertion.assertion_type:
                case AssertionType.TO_BE_VISIBLE:
                    if locator:
                        if assertion.negate:
                            await locator.wait_for(state="hidden", timeout=timeout)
                        else:
                            await locator.wait_for(state="visible", timeout=timeout)

                case AssertionType.TO_BE_HIDDEN:
                    if locator:
                        if assertion.negate:
                            await locator.wait_for(state="visible", timeout=timeout)
                        else:
                            await locator.wait_for(state="hidden", timeout=timeout)

                case AssertionType.TO_HAVE_TEXT:
                    if locator and assertion.expected_value is not None:
                        from playwright.async_api import expect
                        exp = expect(locator)
                        if assertion.negate:
                            exp = exp.not_
                        await exp.to_have_text(assertion.expected_value, timeout=timeout)

                case AssertionType.TO_CONTAIN_TEXT:
                    if locator and assertion.expected_value is not None:
                        from playwright.async_api import expect
                        exp = expect(locator)
                        if assertion.negate:
                            exp = exp.not_
                        await exp.to_contain_text(assertion.expected_value, timeout=timeout)

                case AssertionType.TO_HAVE_URL:
                    if assertion.expected_value is not None:
                        from playwright.async_api import expect
                        exp = expect(page)
                        if assertion.negate:
                            exp = exp.not_
                        await exp.to_have_url(assertion.expected_value, timeout=timeout)

                case AssertionType.TO_HAVE_COUNT:
                    if locator and assertion.expected_count is not None:
                        from playwright.async_api import expect
                        exp = expect(locator)
                        if assertion.negate:
                            exp = exp.not_
                        await exp.to_have_count(assertion.expected_count, timeout=timeout)

                case AssertionType.TO_HAVE_VALUE:
                    if locator and assertion.expected_value is not None:
                        from playwright.async_api import expect
                        exp = expect(locator)
                        if assertion.negate:
                            exp = exp.not_
                        await exp.to_have_value(assertion.expected_value, timeout=timeout)

                case AssertionType.TO_BE_CHECKED:
                    if locator:
                        from playwright.async_api import expect
                        exp = expect(locator)
                        if assertion.negate:
                            exp = exp.not_
                        await exp.to_be_checked(timeout=timeout)

                case AssertionType.TO_BE_ENABLED:
                    if locator:
                        from playwright.async_api import expect
                        exp = expect(locator)
                        if assertion.negate:
                            exp = exp.not_
                        await exp.to_be_enabled(timeout=timeout)

                case AssertionType.TO_HAVE_ATTRIBUTE:
                    if (
                        locator
                        and assertion.attribute_name
                        and assertion.expected_value is not None
                    ):
                        from playwright.async_api import expect
                        exp = expect(locator)
                        if assertion.negate:
                            exp = exp.not_
                        await exp.to_have_attribute(
                            assertion.attribute_name,
                            assertion.expected_value,
                            timeout=timeout,
                        )

            return StepResult(
                step_index=index,
                action=f"assert_{assertion.assertion_type.value}",
                status="passed",
            )

        except (AssertionError, PlaywrightTimeout, Exception) as exc:
            return StepResult(
                step_index=index,
                action=f"assert_{assertion.assertion_type.value}",
                status="failed",
                error=f"Assertion failed: {type(exc).__name__}: {exc}",
            )

    async def _setup_mock_rule(self, context: BrowserContext, rule: MockRule) -> None:
        """Register a network interception rule on the context."""
        async def _route_handler(route, request) -> None:  # type: ignore[no-untyped-def]
            if rule.method and request.method.upper() != rule.method.upper():
                await route.fallback()
                return

            if rule.action == MockAction.ABORT:
                await route.abort("failed")
                return

            # Mock response
            body: str | bytes = ""
            content_type = "application/json"
            if rule.response_body is not None:
                if isinstance(rule.response_body, (dict, list)):
                    body = json.dumps(rule.response_body)
                else:
                    body = str(rule.response_body)
                    content_type = "text/plain"

            headers = {"content-type": content_type}
            if rule.response_headers:
                headers.update(rule.response_headers)

            await route.fulfill(
                status=rule.response_status,
                headers=headers,
                body=body,
            )

        await context.route(rule.url_pattern, _route_handler)

    async def _emit_progress(
        self, test_case_id: uuid.UUID, step_index: int, sr: StepResult
    ) -> None:
        if self._on_progress:
            try:
                result = self._on_progress(
                    type="step_progress",
                    run_id=str(self.run_id),
                    test_case_id=str(test_case_id),
                    step_index=step_index,
                    action=sr.action,
                    status=sr.status,
                    duration_ms=sr.duration_ms,
                    error=sr.error,
                )
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning("Progress callback error: %s", exc)
