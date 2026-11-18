"""Smart Recorder Service — headed browser with injected JS event capture."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.core.config import settings
from app.schemas.test_schemas import (
    AssertionStep,
    BrowserTypeEnum,
    DeviceConfig,
    RecordedStep,
    StepAction,
)

# ── JS recorder injected into every page via add_init_script ────────

RECORDER_JS = r"""
(() => {
  if (window.__pw_recorder_injected) return;
  window.__pw_recorder_injected = true;

  /* ── Smart selector generator ───────────────────────────────── */
  function bestSelector(el) {
    // Priority 1: data-testid
    const testId = el.getAttribute('data-testid') || el.getAttribute('data-test-id');
    if (testId) return `[data-testid="${testId}"]`;

    // Priority 2: ARIA role + accessible name
    const role = el.getAttribute('role') || implicitRole(el);
    const accName = el.getAttribute('aria-label') || el.innerText?.trim().substring(0, 50);
    if (role && accName) return `role=${role}[name="${escQ(accName)}"]`;

    // Priority 3: label association (for inputs)
    if (el.id) {
      const label = document.querySelector(`label[for="${el.id}"]`);
      if (label) return `label=${escQ(label.innerText.trim())}`;
    }

    // Priority 4: placeholder
    const ph = el.getAttribute('placeholder');
    if (ph) return `[placeholder="${escQ(ph)}"]`;

    // Priority 5: id (if short and not auto-generated looking)
    if (el.id && el.id.length < 60 && !/^\d|^:[rR]/.test(el.id)) return `#${CSS.escape(el.id)}`;

    // Priority 6: unique CSS path
    return cssSelectorPath(el);
  }

  function implicitRole(el) {
    const tag = el.tagName.toLowerCase();
    const map = {button:'button',a:'link',input:'textbox',select:'combobox',textarea:'textbox',img:'img'};
    if (tag === 'input') {
      const t = (el.type||'text').toLowerCase();
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (t === 'submit' || t === 'button') return 'button';
      return 'textbox';
    }
    return map[tag] || null;
  }

  function escQ(s) { return s.replace(/"/g, '\\"'); }

  function cssSelectorPath(el) {
    const parts = [];
    let cur = el;
    while (cur && cur !== document.body && cur !== document.documentElement) {
      let sel = cur.tagName.toLowerCase();
      if (cur.id && cur.id.length < 60) {
        sel = `#${CSS.escape(cur.id)}`;
        parts.unshift(sel);
        break;
      }
      const parent = cur.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
        if (siblings.length > 1) {
          const idx = siblings.indexOf(cur) + 1;
          sel += `:nth-of-type(${idx})`;
        }
      }
      parts.unshift(sel);
      cur = parent;
    }
    return parts.join(' > ');
  }

  /* ── Event listeners ────────────────────────────────────────── */
  function emit(step) {
    if (window.__pw_on_step) window.__pw_on_step(JSON.stringify(step));
  }

  document.addEventListener('click', (e) => {
    const el = e.target.closest('a,button,input,select,textarea,[role="button"],[onclick]') || e.target;
    emit({ action: 'click', selector: bestSelector(el), timestamp: Date.now() });
  }, true);

  document.addEventListener('input', (() => {
    let debounce = {};
    return (e) => {
      const el = e.target;
      if (!el.matches || !el.matches('input,textarea,select,[contenteditable]')) return;
      const key = bestSelector(el);
      clearTimeout(debounce[key]);
      debounce[key] = setTimeout(() => {
        if (el.tagName.toLowerCase() === 'select') {
          emit({ action: 'selectOption', selector: key, value: el.value, timestamp: Date.now() });
        } else {
          emit({ action: 'fill', selector: key, value: el.value, timestamp: Date.now() });
        }
      }, 400);
    };
  })(), true);

  document.addEventListener('change', (e) => {
    const el = e.target;
    if (el.type === 'checkbox' || el.type === 'radio') {
      emit({
        action: el.checked ? 'check' : 'uncheck',
        selector: bestSelector(el),
        timestamp: Date.now()
      });
    }
    if (el.type === 'file' && el.files.length) {
      const files = Array.from(el.files).map(f => f.name);
      emit({ action: 'fileUpload', selector: bestSelector(el), files: files, timestamp: Date.now() });
    }
  }, true);

  document.addEventListener('keydown', (e) => {
    const special = ['Enter','Escape','Tab','ArrowDown','ArrowUp','ArrowLeft','ArrowRight',
                     'Backspace','Delete','Home','End','PageUp','PageDown'];
    if (special.includes(e.key) || (e.ctrlKey || e.metaKey)) {
      let keyStr = '';
      if (e.ctrlKey || e.metaKey) keyStr += 'Control+';
      if (e.altKey) keyStr += 'Alt+';
      if (e.shiftKey) keyStr += 'Shift+';
      keyStr += e.key;
      const el = e.target;
      emit({ action: 'press', selector: bestSelector(el), key: keyStr, timestamp: Date.now() });
    }
  }, true);
})();
"""


class RecorderSession:
    """Manages a single recording session."""

    def __init__(self, session_id: str) -> None:
        self.session_id: str = session_id
        self.steps: list[RecordedStep] = []
        self.assertions: list[AssertionStep] = []
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._start_time: float = 0.0
        self._step_callback: Callable[[RecordedStep], Any] | None = None
        self._running: bool = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(
        self,
        url: str,
        browser_type: BrowserTypeEnum = BrowserTypeEnum.CHROMIUM,
        device_config: DeviceConfig | None = None,
        headless: bool = False,
        on_step: Callable[[RecordedStep], Any] | None = None,
    ) -> None:
        """Launch browser, inject recorder JS, and start capturing events."""
        self._step_callback = on_step
        self._start_time = time.monotonic()
        self._running = True

        self._playwright = await async_playwright().start()

        launcher = {
            BrowserTypeEnum.CHROMIUM: self._playwright.chromium,
            BrowserTypeEnum.FIREFOX: self._playwright.firefox,
            BrowserTypeEnum.WEBKIT: self._playwright.webkit,
        }[browser_type]

        self._browser = await launcher.launch(headless=headless)

        # Build context options from device config
        ctx_kwargs: dict[str, Any] = {}
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

        self._context = await self._browser.new_context(**ctx_kwargs)
        self._page = await self._context.new_page()

        # Inject the recorder JS into every frame
        await self._context.add_init_script(script=RECORDER_JS)

        # Expose the callback so JS can push steps to Python
        await self._page.expose_function("__pw_on_step", self._handle_js_step)

        # Also inject into the already-loaded page
        await self._page.evaluate(RECORDER_JS)

        # Navigate and capture the initial navigate step
        await self._page.goto(url, wait_until="domcontentloaded", timeout=settings.DEFAULT_TIMEOUT_MS)
        nav_step = RecordedStep(
            action=StepAction.NAVIGATE,
            url=url,
            timestamp=time.time() * 1000,
            description="Initial navigation",
        )
        self.steps.append(nav_step)
        if self._step_callback:
            await self._maybe_await(self._step_callback(nav_step))

        # Watch for new pages (popups / tabs)
        self._context.on("page", self._on_new_page)

    async def _on_new_page(self, page: Page) -> None:
        """Handle popups / new-tab pages opened during recording."""
        await page.expose_function("__pw_on_step", self._handle_js_step)
        await page.evaluate(RECORDER_JS)

    async def _handle_js_step(self, raw_json: str) -> None:
        """Callback invoked from the injected JS whenever a user action is detected."""
        import json

        data = json.loads(raw_json)
        step = RecordedStep(**data)
        self.steps.append(step)
        if self._step_callback:
            await self._maybe_await(self._step_callback(step))

    async def add_assertion(self, assertion: AssertionStep) -> None:
        """Inject an assertion at the current point in the recording."""
        self.assertions.append(assertion)
        # Insert a marker step so the assertion is ordered relative to actions
        marker = RecordedStep(
            action=StepAction.WAIT,
            description=f"Assertion: {assertion.assertion_type.value}",
            timestamp=time.time() * 1000,
        )
        self.steps.append(marker)
        if self._step_callback:
            await self._maybe_await(self._step_callback(marker))

    async def stop(self) -> tuple[list[RecordedStep], int]:
        """Stop recording, close browser, and return captured steps."""
        self._running = False
        duration_ms = int((time.monotonic() - self._start_time) * 1000)

        if self._page and not self._page.is_closed():
            try:
                await self._page.close()
            except Exception:
                pass
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
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

        return self.steps, duration_ms

    @staticmethod
    async def _maybe_await(result: Any) -> None:
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            await result


class RecorderManager:
    """Manages multiple concurrent recorder sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, RecorderSession] = {}

    def create_session(self) -> RecorderSession:
        session_id = uuid.uuid4().hex[:12]
        session = RecorderSession(session_id)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> RecorderSession | None:
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    @property
    def active_sessions(self) -> list[str]:
        return [sid for sid, s in self._sessions.items() if s.is_running]


# Module-level singleton
recorder_manager = RecorderManager()
