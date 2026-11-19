# Playwright Testing Platform — User Manual

> Step-by-step guide for every feature. Follow the numbered instructions in order.

---

## Table of Contents

- [Chapter 1: Starting the Application](#chapter-1-starting-the-application)
- [Chapter 2: Understanding the Interface](#chapter-2-understanding-the-interface)
- [Chapter 3: Managing Projects](#chapter-3-managing-projects)
- [Chapter 4: Managing Test Suites](#chapter-4-managing-test-suites)
- [Chapter 5: Creating Test Cases Manually](#chapter-5-creating-test-cases-manually)
- [Chapter 6: Recording Tests with the Browser Recorder](#chapter-6-recording-tests-with-the-browser-recorder)
- [Chapter 7: Running Tests](#chapter-7-running-tests)
- [Chapter 8: Viewing Run Results & Reports](#chapter-8-viewing-run-results--reports)
- [Chapter 9: Exporting Tests as Python Code](#chapter-9-exporting-tests-as-python-code)
- [Chapter 10: Managing Authentication Profiles](#chapter-10-managing-authentication-profiles)
- [Chapter 11: Device & Mobile Emulation](#chapter-11-device--mobile-emulation)
- [Chapter 12: Network Mocking & Interception](#chapter-12-network-mocking--interception)
- [Chapter 13: Visual Regression Testing](#chapter-13-visual-regression-testing)
- [Chapter 14: CI/CD Webhook Integration](#chapter-14-cicd-webhook-integration)
- [Chapter 15: Live WebSocket Monitoring](#chapter-15-live-websocket-monitoring)
- [Chapter 16: Settings & Configuration](#chapter-16-settings--configuration)
- [Chapter 17: Keyboard Shortcuts & Tips](#chapter-17-keyboard-shortcuts--tips)
- [Chapter 18: Troubleshooting](#chapter-18-troubleshooting)
- [Appendix A: Step Action Reference](#appendix-a-step-action-reference)
- [Appendix B: Assertion Type Reference](#appendix-b-assertion-type-reference)
- [Appendix C: API Endpoint Reference](#appendix-c-api-endpoint-reference)

---

## Chapter 1: Starting the Application

### Step 1: Open a terminal

Open your terminal application (Terminal, iTerm, Windows Terminal, etc.)

### Step 2: Navigate to the project folder

```bash
cd /home/gmahesh/playwright/playwright-platform
```

### Step 3: Start the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 4: Verify startup

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Starting Playwright Platform API
INFO:     Database tables ensured
```

> [!IMPORTANT]
> Keep this terminal **open** the entire time you're using the application. The server must stay running. To stop, press `Ctrl + C`.

### Step 5: Open the application

Open your web browser (Chrome, Firefox, Edge, etc.) and go to:

```
http://localhost:8000
```

You will see the Playwright Testing Platform dashboard with the teal sidebar and three-panel layout.

### Step 6: Verify everything works

- You should see the **sidebar** on the left with menu items (Tests, Recorder, Execution Runs, etc.)
- The main area shows three panels: **Projects**, **Suites**, and **Test Cases**
- If you see "Loading..." that briefly shows then changes to "No projects yet", everything is working

> [!TIP]
> You can also access the **Swagger API Docs** at `http://localhost:8000/docs` for a technical API playground.

---

## Chapter 2: Understanding the Interface

### 2.1 The Header Bar (top, dark navy)

| Element | Location | Purpose |
|---------|----------|---------|
| ☰ Hamburger | Far left | Collapse/expand the sidebar |
| 🏠 Project | Left center | Shows current navigation context |
| 🔔 Bell icon | Right side | Notifications indicator |
| 📄 Doc icon | Right side | Access documentation |
| 👤 User avatar | Far right | Shows current user (Mahesh) |

### 2.2 The Sidebar (left, teal)

The sidebar is your **main navigation**. Click any item to switch pages:

| Menu Item | What It Does |
|-----------|-------------|
| **Tests** | Main test management — 3-panel view for Projects → Suites → Test Cases |
| **Recorder** | Launch the smart browser recorder to record tests by interacting with a website |
| **Execution Runs** | View history of all test runs, their statuses, and detailed results |
| **Code Export** | Convert any test case into runnable Python pytest code |
| **Auth Profiles** | Manage saved login sessions that tests can reuse |
| **Settings** | View platform configuration |
| **API Docs** | Opens the Swagger interactive API documentation in a new tab |

> [!TIP]
> Click the **☰ hamburger icon** in the header to collapse the sidebar and get more screen space. Click it again to expand.

### 2.3 The Three-Panel Layout (Tests Page)

When "Tests" is selected, you see three panels side by side:

```
┌──────────────┬──────────────┬─────────────────────────┐
│   PROJECTS   │    SUITES    │      TEST CASES         │
│              │              │                         │
│ (Panel 1)    │ (Panel 2)    │ (Panel 3)              │
│              │              │                         │
│ Select a     │ Shows suites │ Shows test cases in a   │
│ project to   │ in selected  │ table with Sr.No, Name, │
│ see its      │ project      │ Steps, Description      │
│ suites →     │              │                         │
└──────────────┴──────────────┴─────────────────────────┘
```

**Flow**: Click a Project → its Suites appear → Click a Suite → its Test Cases appear in the table.

### 2.4 Common UI Elements

| Element | Appearance | Purpose |
|---------|-----------|---------|
| Green **+** button | Round green circle | Create a new item (project, suite, or test) |
| 🔍 Search icon | In panel header | Toggle search bar to filter items |
| ⋯ Three dots | On each list row | Open context menu (Rename, Delete, Run, Export) |
| ▶ Play button | In suite header | Run all tests in the selected suite |
| Breadcrumb | Top of Test Cases panel | Shows current selection: Home >> Project >> Suite |

---

## Chapter 3: Managing Projects

A **Project** is the top-level container. Everything starts with creating a project.

### 3.1 Creating a New Project

1. Make sure you're on the **Tests** page (click "Tests" in the sidebar)
2. Look at the **Projects** panel (left panel)
3. Click the **green + button** in the Projects panel header
4. A modal dialog appears with the title "Create Project"
5. Fill in:
   - **Project Name** (required): Enter a name, e.g., `My Website Tests`
   - **Description** (optional): Enter a description, e.g., `End-to-end tests for our website`
6. Click the **Create** button
7. ✅ The modal closes and your new project appears in the Projects list

### 3.2 Selecting a Project

1. Click on any project name in the Projects list
2. The project row highlights with a **blue left border**
3. The **Suites** panel (middle) updates to show suites for this project
4. The breadcrumb at the top of the Test Cases panel updates to show the project name
5. The sidebar project name also updates

### 3.3 Renaming a Project

1. Find the project you want to rename in the Projects list
2. Click the **⋯** (three dots) button on that project's row
3. A context menu appears
4. Click **Rename**
5. A browser prompt appears — type the new name
6. Click **OK**
7. ✅ The project is renamed

### 3.4 Deleting a Project

> [!CAUTION]
> Deleting a project permanently removes **all suites, test cases, and related data** inside it. This cannot be undone.

1. Click the **⋯** button on the project row
2. Click **Delete** (shown in red)
3. A confirmation dialog appears: "Delete 'My Website Tests'? This cannot be undone."
4. Click **OK** to confirm
5. ✅ The project and all its contents are deleted

### 3.5 Searching Projects

1. Click the **🔍 search icon** in the Projects panel header
2. A search bar appears below the header
3. Start typing — the list filters in real time to show only matching projects
4. Click the search icon again to close the search bar

---

## Chapter 4: Managing Test Suites

A **Test Suite** groups related test cases. Each project can have multiple suites.

### 4.1 Creating a New Suite

1. **First, select a project** by clicking on it in the Projects panel
2. Click the **green + button** in the **Suites** panel header
3. A modal dialog appears with the title "Create Test Suite"
4. Fill in:
   - **Suite Name** (required): e.g., `Login Flow Tests`
   - **Tags** (optional): comma-separated tags, e.g., `smoke, login, critical`
5. Click **Create**
6. ✅ The new suite appears in the Suites list with its tags shown as blue pills

> [!NOTE]
> If no project is selected, you'll see a toast message: "Select a project first"

### 4.2 Selecting a Suite

1. Click on any suite in the Suites list
2. The suite row highlights with a blue left border
3. The **Test Cases** panel (right) updates to show tests in this suite
4. The breadcrumb updates: Home >> Project Name >> Suite Name
5. A **▶ Play** button appears in the Suites header to run this suite

### 4.3 Running All Tests in a Suite

1. Select a suite by clicking on it
2. Click the **▶ Play** button that appears in the Suites panel header
3. OR: Click **⋯** on the suite row → Click **Run Suite**
4. A toast message confirms: "Run queued: abc12345…"
5. The app automatically switches to the **Execution Runs** page
6. You can see your run with status "pending" or "running"

### 4.4 Renaming / Deleting a Suite

Same process as projects — click **⋯** → **Rename** or **Delete**.

---

## Chapter 5: Creating Test Cases Manually

A **Test Case** contains a sequence of steps (actions) and assertions (checks).

### 5.1 Creating a Basic Test Case

1. Select a **project** (Panel 1)
2. Select a **suite** (Panel 2)
3. Click the **green + button** in the **Test Cases** panel header
4. A modal dialog appears with "Create Test Case"
5. Fill in:
   - **Test Name** (required): e.g., `Homepage Load Test`
   - **Description** (optional): e.g., `Verify the homepage loads correctly`
   - **Steps** (JSON): This is where you define what the test does
   - **Assertions** (JSON): This is where you define what to verify

### 5.2 Writing Steps (JSON format)

Steps tell the browser what to do. Each step is a JSON object with an `action` and additional fields.

**Example — a simple login test:**

```json
[
  {
    "action": "navigate",
    "url": "https://myapp.com/login"
  },
  {
    "action": "fill",
    "selector": "#email",
    "value": "user@example.com"
  },
  {
    "action": "fill",
    "selector": "#password",
    "value": "mypassword123"
  },
  {
    "action": "click",
    "selector": "button[type='submit']"
  }
]
```

**What each step does:**

| Step | Action | What happens in the browser |
|------|--------|---------------------------|
| 1 | `navigate` | Opens the URL `https://myapp.com/login` |
| 2 | `fill` | Finds the element with id "email" and types `user@example.com` |
| 3 | `fill` | Finds the password field and types `mypassword123` |
| 4 | `click` | Clicks the submit button |

### 5.3 Writing Assertions (JSON format)

Assertions verify that the test produced the expected result.

**Example — verify login was successful:**

```json
[
  {
    "assertion_type": "to_have_url",
    "expected_value": "https://myapp.com/dashboard"
  },
  {
    "assertion_type": "to_be_visible",
    "selector": ".welcome-message"
  },
  {
    "assertion_type": "to_have_text",
    "selector": "h1",
    "expected_value": "Welcome back!"
  }
]
```

**What each assertion checks:**

| # | Type | What it verifies |
|---|------|-----------------|
| 1 | `to_have_url` | The browser is now on the dashboard URL |
| 2 | `to_be_visible` | An element with class "welcome-message" is visible |
| 3 | `to_have_text` | The h1 heading says exactly "Welcome back!" |

### 5.4 Understanding Selectors

A **selector** tells the browser which element to interact with. Here are the most common types:

| Selector Type | Example | Finds |
|--------------|---------|-------|
| By ID | `#login-btn` | Element with `id="login-btn"` |
| By class | `.submit-button` | Element with `class="submit-button"` |
| By data-testid | `[data-testid="email"]` | Element with `data-testid="email"` |
| By placeholder | `[placeholder="Enter email"]` | Input with that placeholder |
| By type | `button[type="submit"]` | Submit button |
| By text (Playwright) | `text=Sign In` | Element containing text "Sign In" |
| By role (Playwright) | `role=button[name="Submit"]` | Button with accessible name "Submit" |

> [!TIP]
> The best practice is to use `data-testid` attributes in your app's HTML. They are the most stable and don't break when CSS classes or text changes.

### 5.5 Viewing Test Case Details

1. Click on any test case row in the table
2. OR: Click **⋯** → **View Details**
3. A **slide-out drawer** appears on the right showing:
   - Test name and description
   - All steps with action badges (color-coded by type)
   - All assertions
   - Device config and mock rules (if any)

### 5.6 Editing a Test Case

1. Currently, editing is done through the **⋯** → Rename for the name
2. For full editing (steps, assertions, etc.), use the **API** directly:

```bash
curl -X PATCH http://localhost:8000/api/tests/YOUR_TEST_ID \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [{"action": "navigate", "url": "https://new-url.com"}]
  }'
```

Then refresh the page to see changes.

### 5.7 Deleting a Test Case

1. Click **⋯** on the test case row
2. Click **Delete** (red)
3. Confirm in the dialog
4. ✅ Test case is permanently removed

---

## Chapter 6: Recording Tests with the Browser Recorder

The **Recorder** lets you create tests by simply interacting with a website — no code or JSON writing needed.

### 6.1 Starting a Recording Session

1. Click **Recorder** in the sidebar
2. You see the Recorder page with a URL input, browser selector, and mode selector
3. Enter the **Target URL**: the website you want to test, e.g., `https://example.com`
4. Choose a **Browser**:
   - **Chromium** (default) — Chrome-based, most compatible
   - **Firefox** — Mozilla Firefox engine
   - **WebKit** — Safari engine
5. Choose a **Mode**:
   - **Headed** — A visible browser window opens (requires a display/GUI)
   - **Headless** — Browser runs invisibly (for servers without a display)
6. Click the **🔴 Start Recording** button

### 6.2 What Happens After Starting

1. The button changes to "Launching..."
2. A real browser window opens (if Headed mode) and navigates to your URL
3. Below the form, a **LIVE** panel appears with a red pulsing dot
4. The session ID is displayed (e.g., `a1b2c3d4e5f6`)

### 6.3 Recording Your Actions

1. **Switch to the browser window** that just opened
2. **Interact with the website** normally:
   - Click buttons and links
   - Type into input fields
   - Select dropdown options
   - Check/uncheck checkboxes
   - Upload files
   - Press keyboard keys (Enter, Tab, etc.)
3. **Watch the LIVE panel** in the platform — each action appears instantly:

```
 1  navigate   https://example.com
 2  click      [data-testid="search-box"]
 3  fill       [data-testid="search-box"] → "playwright"
 4  press      [data-testid="search-box"] Enter
 5  click      a.result-link
```

Each step shows:
- **Number** — the order it was recorded
- **Action badge** — color-coded (blue for navigate, yellow for click, green for fill, purple for press)
- **Selector** — what element was interacted with
- **Value** — what was typed or selected (if applicable)

### 6.4 Adding Assertions During Recording

While the recording is active, you can add verification checks:

1. Click the **✅ Add Assertion** button below the live steps
2. A series of prompts appear:
   - **Assertion type**: Type one of: `to_be_visible`, `to_have_text`, `to_have_url`, `to_have_count`
   - **Selector**: Enter a CSS selector (e.g., `h1` or `.result-count`). Leave empty for URL assertions.
   - **Expected value**: Enter the expected text, URL, etc. Leave empty for visibility checks.
3. The assertion is injected into the recording
4. A toast confirms: "Assertion injected"

**Example flow:**
- You navigated to a search results page
- You want to verify the heading says "Search Results"
- Click "Add Assertion"
- Type: `to_have_text`
- Selector: `h1`
- Expected value: `Search Results`
- ✅ Done — this assertion is now part of your recording

### 6.5 Stopping the Recording

1. When you've finished interacting with the website, **go back to the platform**
2. Click the **⬛ Stop Recording** button (red button)
3. The browser window closes
4. A toast shows: "Recording stopped. 12 steps captured (45000ms)"
5. The LIVE panel remains visible showing all captured steps

### 6.6 Saving the Recording as a Test Case

> [!IMPORTANT]
> Before saving, you must have a Project and Suite selected on the Tests page. If you haven't created them yet, do Chapter 3 and 4 first, then come back to save.

1. Click the **💾 Save as Test Case** button
2. A prompt asks for the test name — type a name, e.g., `Search Flow Test`
3. Click **OK**
4. ✅ Toast confirms: "Test case saved!"
5. The recording panel clears
6. Switch to the **Tests** page to see your new test case in the suite you had selected

### 6.7 Recording Tips

| Tip | Details |
|-----|---------|
| **Wait for pages to load** | Pause briefly after clicking links to let pages fully load before interacting |
| **Use clear inputs** | Clear text fields before typing so the fill action captures the full text |
| **Test one flow at a time** | Record a single user flow per test case (e.g., just login, or just checkout) |
| **Add assertions at key points** | After important actions (login, form submission), add assertions to verify success |
| **data-testid is best** | The recorder generates smart selectors, but apps with `data-testid` produce the most reliable tests |

---

## Chapter 7: Running Tests

### 7.1 Running a Single Suite

**Method A — From the Suites panel:**
1. Go to the **Tests** page
2. Select a project, then select a suite
3. Click the **▶ Play** button in the Suites panel header
4. The app switches to Execution Runs and shows your queued run

**Method B — From the context menu:**
1. Click **⋯** on any suite
2. Click **Run Suite**
3. Same result — run is queued

### 7.2 Running with Different Browsers

By default, runs use **Chromium**. To run on Firefox or WebKit, use the API:

```bash
# Run on Firefox
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"suite_id": "YOUR_SUITE_ID", "browser": "firefox"}'

# Run on WebKit (Safari)
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"suite_id": "YOUR_SUITE_ID", "browser": "webkit"}'
```

### 7.3 Understanding Run Statuses

| Status | Badge Color | Meaning |
|--------|------------|---------|
| **pending** | Gray | Run is queued, waiting for a worker to pick it up |
| **running** | Blue | Tests are currently executing |
| **passed** | Green | All tests passed ✅ |
| **failed** | Red | One or more tests failed ❌ |
| **error** | Amber | A system error occurred (browser crash, timeout, etc.) |

### 7.4 What Happens During a Run

When a run executes, the system:
1. Opens a browser (Chromium/Firefox/WebKit)
2. Starts **tracing** (screenshots, snapshots, source code capture)
3. Starts **video recording**
4. For each test case in the suite:
   - Loads authentication state (if an auth profile is attached)
   - Sets up network mocks (if mock rules are defined)
   - Configures device emulation (if device config is set)
   - Executes each step one by one
   - Takes a screenshot after each step
   - Runs all assertions
   - If a step fails: takes a failure screenshot and stops that test case
5. Saves the trace file (.zip), video, and screenshots to the `artifacts/` folder
6. Writes results to the database
7. Generates a JSON report

> [!NOTE]
> Runs execute via **ARQ background workers**. This requires Redis to be running.
> If Redis is not running, the run will stay in "pending" forever. See Chapter 18 for setup instructions.

---

## Chapter 8: Viewing Run Results & Reports

### 8.1 Navigating to Execution Runs

1. Click **Execution Runs** in the sidebar
2. You see a table of all runs with columns: Status, Run ID, Browser, Duration, Started, Results, Actions

### 8.2 Filtering Runs

1. Use the **Status dropdown** at the top to filter:
   - All Statuses (default)
   - Pending
   - Running
   - Passed
   - Failed
   - Error
2. Click **🔄 Refresh** to reload the list

### 8.3 Viewing Run Details

1. Find the run you want to inspect
2. Click the **👁 eye icon** in the Actions column
3. A **slide-out drawer** opens on the right showing:
   - **Summary**: Status badge, browser, duration, trigger source
   - **Trace file link**: Click to access the trace files
   - **Test Case Results**: Each test case with its status and step-by-step results

### 8.4 Understanding the Results Drawer

The drawer shows each test case as a card:

```
┌─────────────────────────────────────────┐
│  User Login Flow              ✅ passed │
│  4200ms                                 │
│                                         │
│  ✅ Step 0: navigate          1500ms    │
│  ✅ Step 1: fill               300ms    │
│  ✅ Step 2: fill               250ms    │
│  ✅ Step 3: click              200ms    │
│  ✅ Step 4: assert_to_have_url 150ms    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Add to Cart Test             ❌ failed │
│  5000ms                                 │
│  Timeout after 30000ms on click         │
│  (selector: .buy-btn)                   │
│                                         │
│  ✅ Step 0: navigate          2000ms    │
│  ✅ Step 1: click              500ms    │
│  ❌ Step 2: click             30000ms   │
│     Timeout: .buy-btn not found         │
└─────────────────────────────────────────┘
```

Each step shows:
- ✅ Green check = step passed
- ❌ Red X = step failed (with error message)
- Duration in milliseconds

### 8.5 Downloading Trace Files

Trace files let you debug failures using Playwright's Trace Viewer:

1. In the run details drawer, click the **📁 View Trace Files** link
2. OR use the API: `http://localhost:8000/api/runs/RUN_ID/trace/TEST_CASE_ID`
3. Download the `.zip` file
4. Open it with:
   ```bash
   playwright show-trace trace.zip
   ```
5. OR drag the .zip file into https://trace.playwright.dev/ in your browser

The Trace Viewer shows:
- Screenshots at each step
- DOM snapshots
- Network requests
- Console logs
- Source code

### 8.6 Viewing Screenshots

Screenshots are taken at every step during execution.

**Via API:**
```bash
curl http://localhost:8000/api/runs/RUN_ID/screenshots/TEST_CASE_ID
```

**Via direct URL:**
```
http://localhost:8000/artifacts/screenshots/RUN_ID/TEST_CASE_ID/step_0.png
http://localhost:8000/artifacts/screenshots/RUN_ID/TEST_CASE_ID/step_1.png
http://localhost:8000/artifacts/screenshots/RUN_ID/TEST_CASE_ID/step_2_failure.png
```

### 8.7 Getting a JSON Report

```bash
curl http://localhost:8000/api/runs/RUN_ID/report
```

Returns a structured JUnit-style report with:
- Suite name, total/passed/failed/error/skipped counts
- Duration
- Per-test-case details with per-step results

### 8.8 Deleting a Run

1. Click the **🗑 trash icon** in the Actions column
2. Confirm: "Delete this run and its artifacts?"
3. Click **OK**
4. ✅ The run and all its trace files, videos, and screenshots are permanently deleted

---

## Chapter 9: Exporting Tests as Python Code

Convert any test case into a standalone, runnable Python `pytest-playwright` file.

### 9.1 Exporting from the Code Export Page

1. Click **Code Export** in the sidebar
2. Select a **Test Case** from the dropdown
3. The exported Python code appears immediately in a syntax-highlighted preview
4. The filename is shown (e.g., `test_user_login_flow.py`)

### 9.2 Exporting from the Test Cases Panel

1. On the **Tests** page, click **⋯** on any test case
2. Click **Export Code**
3. The app switches to the Code Export page with the code displayed

### 9.3 Copying the Code

1. Click the **📋 Copy** button in the code header bar
2. The code is copied to your clipboard
3. Toast confirms: "Code copied!"
4. Paste it into your IDE or editor

### 9.4 Downloading as a File

1. Click the **⬇ Download** button in the code header bar
2. A `.py` file downloads to your computer (e.g., `test_user_login_flow.py`)
3. Move it to your test project folder

### 9.5 Running the Exported Code

1. Make sure you have the required packages:
   ```bash
   pip install pytest pytest-playwright pytest-asyncio
   playwright install chromium
   ```

2. Run the test:
   ```bash
   pytest test_user_login_flow.py -v
   ```

3. Expected output:
   ```
   test_user_login_flow.py::test_user_login_flow PASSED
   ```

### 9.6 What the Exported Code Looks Like

The generated code is a complete, standalone pytest file:

```python
"""Auto-generated Playwright test — do not edit manually."""

import json
import re

import pytest
from playwright.async_api import Page, BrowserContext, expect


@pytest.fixture
async def context(browser):
    """Create a browser context with the configured options."""
    ctx = await browser.new_context()
    yield ctx
    await ctx.close()


@pytest.fixture
async def page(context: BrowserContext):
    """Create a new page from the context."""
    page = await context.new_page()
    yield page
    await page.close()


@pytest.mark.asyncio
async def test_user_login_flow(page: Page):
    """Test: User Login Flow"""

    # Step 1: navigate
    await page.goto("https://example.com/login", wait_until="domcontentloaded")

    # Step 2: fill
    await page.fill("#email", "user@example.com")

    # Step 3: fill
    await page.fill("#password", "mypassword123")

    # Step 4: click
    await page.click("button[type='submit']")

    # ── Assertions ──────────────────────────────
    # Assertion 1: to_have_url
    await expect(page).to_have_url("https://example.com/dashboard")

    # Assertion 2: to_be_visible
    await expect(page.locator(".welcome-message")).to_be_visible()
```

It includes:
- All imports
- Context fixture with device config (if any)
- Page fixture with network mocking (if any)
- Test function with every step as a Playwright call
- All assertions using Playwright's `expect` API

---

## Chapter 10: Managing Authentication Profiles

Auth profiles let tests **skip login** by reusing saved browser sessions.

### 10.1 Understanding Auth Profiles

When you log into a website, the browser stores:
- **Cookies** (session tokens, auth cookies)
- **LocalStorage** (JWT tokens, user preferences)

An auth profile saves this data so other tests can start already logged in.

### 10.2 Creating an Auth Profile

1. Click **Auth Profiles** in the sidebar
2. Click the **+ New Profile** button (blue)
3. A modal appears:
   - **Profile Name** (required): e.g., `Admin User Session`
   - **Project**: Select which project this profile belongs to
   - **Description** (optional): e.g., `Logged in as admin@company.com`
4. Click **Create**
5. ✅ Profile appears in the table

### 10.3 Using an Auth Profile in a Test

1. Create a test case that performs the login (via API):

```bash
curl -X POST http://localhost:8000/api/tests \
  -H "Content-Type: application/json" \
  -d '{
    "suite_id": "YOUR_SUITE_ID",
    "name": "Login and Save Session",
    "auth_profile_id": "YOUR_AUTH_PROFILE_ID",
    "steps": [
      {"action": "navigate", "url": "https://myapp.com/login"},
      {"action": "fill", "selector": "#email", "value": "admin@company.com"},
      {"action": "fill", "selector": "#password", "value": "password123"},
      {"action": "click", "selector": "#login-btn"}
    ]
  }'
```

2. **Run this test** — after it passes, the browser session is automatically saved to the auth profile

3. **Now create other tests** using the same `auth_profile_id`:

```bash
curl -X POST http://localhost:8000/api/tests \
  -H "Content-Type: application/json" \
  -d '{
    "suite_id": "YOUR_SUITE_ID",
    "name": "Admin Dashboard (no login needed)",
    "auth_profile_id": "YOUR_AUTH_PROFILE_ID",
    "steps": [
      {"action": "navigate", "url": "https://myapp.com/admin"}
    ],
    "assertions": [
      {"assertion_type": "to_be_visible", "selector": ".admin-panel"}
    ]
  }'
```

This test starts **already logged in** — it loads the saved cookies and localStorage before navigating.

### 10.4 Deleting an Auth Profile

1. On the Auth Profiles page, click the **🗑 trash icon** for the profile
2. Confirm deletion
3. ✅ Profile is removed (the saved session file is kept on disk)

---

## Chapter 11: Device & Mobile Emulation

Test your website as if it's running on a phone, tablet, or specific configuration.

### 11.1 Using a Device Preset

Add `device_config` when creating a test case (via API):

```bash
curl -X POST http://localhost:8000/api/tests \
  -H "Content-Type: application/json" \
  -d '{
    "suite_id": "YOUR_SUITE_ID",
    "name": "Mobile Homepage Test",
    "device_config": {
      "device_name": "iPhone 14"
    },
    "steps": [
      {"action": "navigate", "url": "https://myapp.com"},
      {"action": "screenshot"}
    ]
  }'
```

This runs the test with iPhone 14's exact viewport, user agent, and touch settings.

### 11.2 Available Device Presets

| Device | Viewport | Mobile |
|--------|----------|--------|
| `iPhone 14` | 390 × 844 | ✅ |
| `iPhone 14 Pro Max` | 430 × 932 | ✅ |
| `iPad Pro 11` | 834 × 1194 | ✅ |
| `Pixel 7` | 412 × 915 | ✅ |
| `Galaxy S9+` | 320 × 658 | ✅ |
| `Desktop Chrome` | 1280 × 720 | ❌ |
| `Desktop Firefox` | 1280 × 720 | ❌ |

### 11.3 Custom Viewport & Settings

```json
"device_config": {
  "viewport": {"width": 1920, "height": 1080},
  "locale": "fr-FR",
  "timezone_id": "Europe/Paris",
  "color_scheme": "dark",
  "geolocation": {"latitude": 48.8566, "longitude": 2.3522},
  "permissions": ["geolocation"]
}
```

| Setting | What it does |
|---------|-------------|
| `viewport` | Sets the browser window size |
| `locale` | Sets the language/region (e.g., `en-US`, `fr-FR`, `ja-JP`) |
| `timezone_id` | Sets the timezone (e.g., `America/New_York`, `Asia/Kolkata`) |
| `color_scheme` | Sets light/dark mode (`light`, `dark`, `no-preference`) |
| `geolocation` | Fakes GPS coordinates |
| `permissions` | Grants browser permissions (e.g., `geolocation`, `notifications`) |
| `user_agent` | Overrides the browser user agent string |

---

## Chapter 12: Network Mocking & Interception

Control what API responses your tests see — mock data, block requests, or simulate errors.

### 12.1 Mocking an API Response

Add `mock_rules` when creating a test:

```json
"mock_rules": [
  {
    "url_pattern": "**/api/users",
    "method": "GET",
    "action": "mock",
    "response_status": 200,
    "response_body": [
      {"id": 1, "name": "Alice"},
      {"id": 2, "name": "Bob"}
    ]
  }
]
```

**What this does:** When the browser requests any URL ending in `/api/users` with GET, instead of hitting the real server, it immediately returns the fake JSON data you specified.

### 12.2 Blocking Requests (Analytics, Ads)

```json
"mock_rules": [
  {
    "url_pattern": "**google-analytics.com/**",
    "action": "abort",
    "description": "Block analytics"
  },
  {
    "url_pattern": "**facebook.com/**",
    "action": "abort",
    "description": "Block Facebook tracking"
  }
]
```

**What this does:** Any request to these domains is immediately blocked. The page loads faster without third-party scripts.

### 12.3 Simulating Server Errors

```json
"mock_rules": [
  {
    "url_pattern": "**/api/checkout",
    "method": "POST",
    "action": "mock",
    "response_status": 500,
    "response_body": {"error": "Internal Server Error"}
  }
]
```

**What this does:** Tests how your app handles a server error when the user tries to checkout.

### 12.4 URL Pattern Syntax

| Pattern | Matches |
|---------|---------|
| `**/api/users` | Any URL ending in `/api/users` |
| `**/api/**` | Any URL with `/api/` in the path |
| `https://example.com/**` | Any URL on example.com |
| `**/*.png` | Any PNG image request |

---

## Chapter 13: Visual Regression Testing

Detect unintended visual changes by comparing screenshots against baselines.

### 13.1 How It Works

1. **First run**: Screenshots are taken and saved as **baselines** (the "correct" look)
2. **Subsequent runs**: New screenshots are compared pixel-by-pixel against baselines
3. If more than **10%** of pixels differ, the step **fails** with the exact diff percentage
4. A **diff image** is generated showing exactly which pixels changed

### 13.2 Setting Up Visual Regression

**Step 1: Create a test with screenshot steps**
```json
{
  "steps": [
    {"action": "navigate", "url": "https://myapp.com"},
    {"action": "screenshot", "description": "Homepage"},
    {"action": "click", "selector": "#features"},
    {"action": "screenshot", "description": "Features section"}
  ]
}
```

**Step 2: Run it once** to establish baselines (first run always passes)

**Step 3: Set baseline paths on the test case**
```bash
curl -X PATCH http://localhost:8000/api/tests/TEST_ID \
  -H "Content-Type: application/json" \
  -d '{
    "baseline_screenshots": {
      "1": "artifacts/screenshots/baselines/TEST_CASE_ID/step_1.png",
      "3": "artifacts/screenshots/baselines/TEST_CASE_ID/step_3.png"
    }
  }'
```

**Step 4: Run again** — now comparisons happen automatically

### 13.3 When a Visual Diff Is Detected

If a step fails due to visual changes, the step result shows:
```
Visual diff 15.30% exceeds threshold 10.00%
```

Three files are saved:
- `step_1.png` — the actual screenshot from this run
- `baselines/step_1.png` — the expected baseline
- `step_1_diff.png` — highlighting the changed pixels

### 13.4 Adjusting the Threshold

By default, the threshold is **10%** (0.1). To change it, set the environment variable before starting the server:

```bash
export VISUAL_DIFF_THRESHOLD=0.05  # Stricter: fail at 5% diff
# OR
export VISUAL_DIFF_THRESHOLD=0.2   # Looser: fail at 20% diff
```

---

## Chapter 14: CI/CD Webhook Integration

Trigger test runs from your CI/CD pipeline (GitHub Actions, GitLab CI, Jenkins, etc.)

### 14.1 Triggering a Run via Webhook

```bash
curl -X POST "http://YOUR_SERVER:8000/api/webhooks/trigger/SUITE_ID?browser=chromium"
```

**Response:**
```json
{
  "run_id": "abc12345-...",
  "status": "queued",
  "message": "Test run queued for suite 'Login Tests' on chromium"
}
```

### 14.2 Polling for Results

```bash
# Check status
curl http://YOUR_SERVER:8000/api/runs/RUN_ID

# Get full report when done
curl http://YOUR_SERVER:8000/api/runs/RUN_ID/report
```

### 14.3 GitHub Actions Example

```yaml
name: E2E Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger E2E Tests
        run: |
          RESPONSE=$(curl -s -X POST "http://your-server:8000/api/webhooks/trigger/$SUITE_ID")
          RUN_ID=$(echo $RESPONSE | jq -r '.run_id')
          echo "Run ID: $RUN_ID"

          # Poll until complete
          while true; do
            STATUS=$(curl -s http://your-server:8000/api/runs/$RUN_ID | jq -r '.status')
            echo "Status: $STATUS"
            if [ "$STATUS" = "passed" ] || [ "$STATUS" = "failed" ] || [ "$STATUS" = "error" ]; then
              break
            fi
            sleep 10
          done

          # Get report
          curl -s http://your-server:8000/api/runs/$RUN_ID/report | jq .

          # Fail CI if tests failed
          [ "$STATUS" = "passed" ] || exit 1
```

---

## Chapter 15: Live WebSocket Monitoring

### 15.1 Monitoring Recorder Steps (Real-time)

When recording, the WebSocket at `/ws/recorder/SESSION_ID` streams every action as it happens.

**Connect with Python:**
```python
import asyncio, websockets, json

async def watch():
    async with websockets.connect("ws://localhost:8000/ws/recorder/SESSION_ID") as ws:
        async for msg in ws:
            data = json.loads(msg)
            step = data.get("step", {})
            print(f"[{step['action']}] {step.get('selector', '')} {step.get('value', '')}")

asyncio.run(watch())
```

### 15.2 Monitoring Run Progress (Real-time)

When a test run is executing, the WebSocket at `/ws/runs/RUN_ID` streams step-by-step progress.

**Connect with Python:**
```python
import asyncio, websockets, json

async def watch_run():
    async with websockets.connect("ws://localhost:8000/ws/runs/RUN_ID") as ws:
        async for msg in ws:
            data = json.loads(msg)
            if data.get("type") == "complete":
                print(f"✅ Run finished: {data['status']}")
                break
            else:
                print(f"Step {data['step_index']}: {data['status']} ({data['duration_ms']}ms)")

asyncio.run(watch_run())
```

---

## Chapter 16: Settings & Configuration

### 16.1 Viewing Settings

1. Click **Settings** in the sidebar
2. You see configuration cards showing:
   - **Database**: SQLite engine, database file path
   - **Playwright**: Default browser, timeout, headless mode
   - **Visual Regression**: Diff threshold
   - **Artifacts**: Directory paths for traces, videos, screenshots

### 16.2 Changing Settings

Settings are controlled via **environment variables**. Create a `.env` file:

```bash
nano /home/gmahesh/playwright/playwright-platform/.env
```

Add any settings you want to change:
```
HEADLESS=false
DEFAULT_TIMEOUT_MS=60000
VISUAL_DIFF_THRESHOLD=0.05
DEBUG=true
```

Save and **restart the server** for changes to take effect.

---

## Chapter 17: Keyboard Shortcuts & Tips

### Tips for Efficient Use

| Tip | How |
|-----|-----|
| **Quick access to API docs** | Click "API Docs" at the bottom of the sidebar |
| **Collapse sidebar** | Click the ☰ hamburger to get more screen space |
| **Bulk operations** | Use the API directly for bulk create/update/delete |
| **Copy test cases** | Export as JSON via API, modify, and re-create |
| **Fast navigation** | Use the breadcrumb in the Test Cases panel to jump back |

### Browser DevTools Trick

To debug what selectors to use in your tests:
1. Right-click any element on your website
2. Click "Inspect"
3. In the Elements panel, look for `data-testid`, `id`, `class`, or `role` attributes
4. Use those in your test selectors

---

## Chapter 18: Troubleshooting

### "No projects yet" but I created one

**Solution:** Click the **🔄 Refresh** button or reload the page (`F5`).

### Runs stay in "pending" forever

**Cause:** The ARQ background worker is not running (requires Redis).

**Solution:**
```bash
# Install Redis
sudo apt install redis-server    # Ubuntu/Debian
brew install redis                # macOS

# Start Redis
redis-server &

# Start the ARQ worker (in a new terminal)
cd /home/gmahesh/playwright/playwright-platform
pip install redis arq
python -m arq app.workers.tasks.WorkerSettings
```

### "Executable doesn't exist" error

**Cause:** Playwright browsers not installed.

**Solution:**
```bash
playwright install chromium
playwright install firefox    # optional
playwright install webkit     # optional

# If system dependencies are missing:
sudo playwright install-deps
```

### Browser window doesn't open (Recorder)

**Cause:** Headless mode is selected, or no display available.

**Solution:** Make sure:
1. Mode is set to **Headed** (not Headless)
2. You're running on a machine with a GUI (not a headless server)
3. Display is available (`echo $DISPLAY` should show `:0` or similar)

### "Port 8000 already in use"

**Solution:**
```bash
# Find what's using it
lsof -i :8000

# Kill it
kill -9 $(lsof -t -i :8000)

# Or use a different port
uvicorn app.main:app --port 8001
```

### Reset all data (start fresh)

```bash
cd /home/gmahesh/playwright/playwright-platform

# Delete the database
rm -f playwright_platform.db

# Delete all artifacts
rm -rf artifacts/*

# Restart
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Modal or drawer won't close

Click anywhere **outside** the modal/drawer, or press the **✕** button.

---

## Appendix A: Step Action Reference

| Action | Required Fields | What It Does |
|--------|----------------|-------------|
| `navigate` | `url` | Opens a web page |
| `click` | `selector` | Clicks an element |
| `fill` | `selector`, `value` | Types text into a field |
| `selectOption` | `selector`, `value` | Selects a dropdown option |
| `check` | `selector` | Checks a checkbox |
| `uncheck` | `selector` | Unchecks a checkbox |
| `press` | `selector`, `key` | Presses a key (e.g., `Enter`, `Tab`, `Control+a`) |
| `fileUpload` | `selector`, `files` | Uploads files (array of file paths) |
| `hover` | `selector` | Hovers over an element |
| `dblclick` | `selector` | Double-clicks an element |
| `wait` | — | Waits 1 second |
| `screenshot` | — | Takes a full-page screenshot |
| `iframe` | `frame_selector` | Switches to an iframe |

## Appendix B: Assertion Type Reference

| Type | Required Fields | What It Checks |
|------|----------------|----------------|
| `to_be_visible` | `selector` | Element exists and is visible |
| `to_be_hidden` | `selector` | Element is hidden or doesn't exist |
| `to_have_text` | `selector`, `expected_value` | Element text matches exactly |
| `to_contain_text` | `selector`, `expected_value` | Element text contains the value |
| `to_have_url` | `expected_value` | Current page URL matches |
| `to_have_count` | `selector`, `expected_count` | Number of matching elements |
| `to_have_value` | `selector`, `expected_value` | Input field value matches |
| `to_be_checked` | `selector` | Checkbox/radio is checked |
| `to_be_enabled` | `selector` | Element is not disabled |
| `to_have_attribute` | `selector`, `attribute_name`, `expected_value` | HTML attribute matches |

> Add `"negate": true` to any assertion to check the **opposite** (e.g., element is NOT visible).

## Appendix C: API Endpoint Reference

```
GET    /                                    → Frontend UI
GET    /health                              → Health check
GET    /docs                                → Swagger API Docs

POST   /api/projects                        → Create project
GET    /api/projects                        → List projects
GET    /api/projects/{id}                   → Get project
PATCH  /api/projects/{id}                   → Update project
DELETE /api/projects/{id}                   → Delete project

POST   /api/suites                          → Create suite
GET    /api/suites?project_id=...           → List suites
GET    /api/suites/{id}                     → Get suite
PATCH  /api/suites/{id}                     → Update suite
DELETE /api/suites/{id}                     → Delete suite

POST   /api/tests                           → Create test case
GET    /api/tests?suite_id=...              → List test cases
GET    /api/tests/{id}                      → Get test case
PATCH  /api/tests/{id}                      → Update test case
DELETE /api/tests/{id}                      → Delete test case
GET    /api/tests/{id}/export?lang=python   → Export as Python code

POST   /api/auth-profiles                   → Create auth profile
GET    /api/auth-profiles?project_id=...    → List profiles
GET    /api/auth-profiles/{id}              → Get profile
PATCH  /api/auth-profiles/{id}              → Update profile
DELETE /api/auth-profiles/{id}              → Delete profile

POST   /api/recorder/start                  → Start recording session
POST   /api/recorder/stop/{session_id}      → Stop recording
POST   /api/recorder/assert/{session_id}    → Inject assertion
GET    /api/recorder/sessions               → List active sessions
WS     /ws/recorder/{session_id}            → Live step stream

POST   /api/runs                            → Trigger test run
GET    /api/runs?suite_id=...&status=...    → List runs
GET    /api/runs/{id}                       → Get run details
DELETE /api/runs/{id}                       → Delete run
GET    /api/runs/{id}/report                → JUnit JSON report
GET    /api/runs/{id}/trace/{tc_id}         → Download trace .zip
GET    /api/runs/{id}/screenshots/{tc_id}   → List screenshots

POST   /api/webhooks/trigger/{suite_id}     → CI/CD webhook
WS     /ws/runs/{run_id}                    → Live run progress
```
