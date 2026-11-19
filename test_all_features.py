#!/usr/bin/env python3
"""Comprehensive integration test for every feature of the Playwright Platform."""

import asyncio
import json
import sys
import time
import uuid
import aiohttp

BASE = "http://localhost:8000"
API = f"{BASE}/api"
PASS = 0
FAIL = 0
BUGS = []

def report(test_name, passed, detail=""):
    global PASS, FAIL
    if passed:
        PASS += 1
        print(f"  ✅ {test_name}")
    else:
        FAIL += 1
        BUGS.append((test_name, detail))
        print(f"  ❌ {test_name}: {detail}")

async def run_tests():
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as s:

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 1. HEALTH CHECK")
        # ═══════════════════════════════════════════════════════════
        r = await s.get(f"{BASE}/health")
        data = await r.json()
        report("GET /health returns 200", r.status == 200, f"status={r.status}")
        report("Health response has status=healthy", data.get("status") == "healthy", str(data))

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 2. FRONTEND SERVING")
        # ═══════════════════════════════════════════════════════════
        r = await s.get(f"{BASE}/")
        report("GET / serves index.html (200)", r.status == 200, f"status={r.status}")
        html = await r.text()
        report("HTML contains Playwright Platform", "Playwright" in html, "")

        r = await s.get(f"{BASE}/static/css/styles.css")
        report("GET /static/css/styles.css (200)", r.status == 200, f"status={r.status}")

        r = await s.get(f"{BASE}/static/js/api.js")
        report("GET /static/js/api.js (200)", r.status == 200, f"status={r.status}")

        r = await s.get(f"{BASE}/static/js/app.js")
        report("GET /static/js/app.js (200)", r.status == 200, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 3. PROJECTS CRUD")
        # ═══════════════════════════════════════════════════════════

        # GET projects (may already have some)
        r = await s.get(f"{API}/projects")
        report("GET /api/projects (200)", r.status == 200, f"status={r.status}")
        existing_projects = await r.json()

        # POST create project
        r = await s.post(f"{API}/projects", json={"name": f"TestProject_{uuid.uuid4().hex[:6]}", "description": "Integration test project"})
        report("POST /api/projects (201)", r.status == 201, f"status={r.status} body={await r.text()}")
        if r.status == 201:
            proj = await r.json()
            proj_id = proj["id"]
            report("Project has id field", "id" in proj, str(proj.keys()))
            report("Project has name field", "name" in proj, str(proj.keys()))
            report("Project has created_at", "created_at" in proj, str(proj.keys()))
        else:
            proj_id = None

        # POST duplicate name should fail
        if proj_id:
            r2 = await s.post(f"{API}/projects", json={"name": proj["name"]})
            report("POST duplicate project name rejects", r2.status >= 400, f"status={r2.status}")

        # POST with empty name
        r = await s.post(f"{API}/projects", json={"name": ""})
        report("POST empty project name rejects", r.status >= 400, f"status={r.status}")

        # POST with missing name
        r = await s.post(f"{API}/projects", json={})
        report("POST missing project name rejects", r.status == 422, f"status={r.status}")

        # GET single project
        if proj_id:
            r = await s.get(f"{API}/projects/{proj_id}")
            report("GET /api/projects/:id (200)", r.status == 200, f"status={r.status}")

        # PATCH project
        if proj_id:
            r = await s.patch(f"{API}/projects/{proj_id}", json={"name": "RenamedProject"})
            report("PATCH /api/projects/:id (200)", r.status == 200, f"status={r.status}")
            if r.status == 200:
                patched = await r.json()
                report("PATCH updates name", patched.get("name") == "RenamedProject", f"name={patched.get('name')}")

        # GET non-existent project
        r = await s.get(f"{API}/projects/{uuid.uuid4()}")
        report("GET non-existent project → 404", r.status == 404, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 4. SUITES CRUD")
        # ═══════════════════════════════════════════════════════════

        suite_id = None
        if proj_id:
            # POST create suite
            r = await s.post(f"{API}/suites", json={
                "project_id": proj_id,
                "name": "TestSuite_1",
                "tags": ["smoke", "login"]
            })
            report("POST /api/suites (201)", r.status == 201, f"status={r.status} body={await r.text() if r.status != 201 else ''}")
            if r.status == 201:
                suite = await r.json()
                suite_id = suite["id"]
                report("Suite has tags field", "tags" in suite, str(suite.keys()))

            # GET suites for project
            r = await s.get(f"{API}/suites?project_id={proj_id}")
            report("GET /api/suites?project_id=... (200)", r.status == 200, f"status={r.status}")
            suites = await r.json()
            report("Suites list is array", isinstance(suites, list), type(suites).__name__)

            # GET all suites (no filter)
            r = await s.get(f"{API}/suites")
            report("GET /api/suites (no filter, 200)", r.status == 200, f"status={r.status}")

            # PATCH suite
            if suite_id:
                r = await s.patch(f"{API}/suites/{suite_id}", json={"name": "RenamedSuite"})
                report("PATCH /api/suites/:id (200)", r.status == 200, f"status={r.status}")

            # GET single suite
            if suite_id:
                r = await s.get(f"{API}/suites/{suite_id}")
                report("GET /api/suites/:id (200)", r.status == 200, f"status={r.status}")

        # POST suite with invalid project_id
        r = await s.post(f"{API}/suites", json={
            "project_id": str(uuid.uuid4()),
            "name": "OrphanSuite"
        })
        report("POST suite with bad project_id fails", r.status >= 400, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 5. TEST CASES CRUD")
        # ═══════════════════════════════════════════════════════════

        test_id = None
        if suite_id:
            # POST create test case
            r = await s.post(f"{API}/tests", json={
                "suite_id": suite_id,
                "name": "Login Flow Test",
                "description": "Tests the login page",
                "steps": [
                    {"action": "navigate", "url": "https://httpbin.org/forms/post"},
                    {"action": "fill", "selector": "input[name='custname']", "value": "TestUser"},
                    {"action": "click", "selector": "button[type='submit']"}
                ],
                "assertions": [
                    {"assertion_type": "to_be_visible", "selector": "body"}
                ]
            })
            report("POST /api/tests (201)", r.status == 201, f"status={r.status} body={await r.text() if r.status != 201 else ''}")
            if r.status == 201:
                test = await r.json()
                test_id = test["id"]
                report("Test has steps array", isinstance(test.get("steps"), list), str(type(test.get("steps"))))
                report("Test has 3 steps", len(test.get("steps", [])) == 3, f"count={len(test.get('steps', []))}")

            # Create a second test case
            r = await s.post(f"{API}/tests", json={
                "suite_id": suite_id,
                "name": "Simple Navigate Test",
                "steps": [
                    {"action": "navigate", "url": "https://example.com"}
                ],
                "assertions": []
            })
            report("POST second test case (201)", r.status == 201, f"status={r.status}")

            # GET tests for suite
            r = await s.get(f"{API}/tests?suite_id={suite_id}")
            report("GET /api/tests?suite_id=... (200)", r.status == 200, f"status={r.status}")
            tests = await r.json()
            report("Tests list has 2 items", len(tests) == 2, f"count={len(tests)}")

            # GET all tests (no filter)
            r = await s.get(f"{API}/tests")
            report("GET /api/tests (no filter, 200)", r.status == 200, f"status={r.status}")

            # GET single test
            if test_id:
                r = await s.get(f"{API}/tests/{test_id}")
                report("GET /api/tests/:id (200)", r.status == 200, f"status={r.status}")
                td = await r.json()
                report("Test detail has name", td.get("name") == "Login Flow Test", f"name={td.get('name')}")

            # PATCH test
            if test_id:
                r = await s.patch(f"{API}/tests/{test_id}", json={"description": "Updated desc"})
                report("PATCH /api/tests/:id (200)", r.status == 200, f"status={r.status}")
                if r.status == 200:
                    patched = await r.json()
                    report("PATCH updates description", patched.get("description") == "Updated desc", f"desc={patched.get('description')}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 6. CODE EXPORT")
        # ═══════════════════════════════════════════════════════════

        if test_id:
            r = await s.get(f"{API}/tests/{test_id}/export?lang=python")
            report("GET /api/tests/:id/export (200)", r.status == 200, f"status={r.status}")
            if r.status == 200:
                export = await r.json()
                report("Export has 'code' field", "code" in export, str(export.keys()))
                report("Export has 'filename' field", "filename" in export, str(export.keys()))
                report("Code contains 'playwright'", "playwright" in export.get("code", "").lower(), "")
                report("Code contains test function", "def test_" in export.get("code", "") or "async def test_" in export.get("code", ""), "")

            # Export non-existent test
            r = await s.get(f"{API}/tests/{uuid.uuid4()}/export?lang=python")
            report("Export non-existent test → 404", r.status == 404, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 7. AUTH PROFILES CRUD")
        # ═══════════════════════════════════════════════════════════

        auth_id = None
        if proj_id:
            r = await s.post(f"{API}/auth-profiles", json={
                "project_id": proj_id,
                "name": "Admin Session",
                "description": "Admin user auth state"
            })
            report("POST /api/auth-profiles (201)", r.status == 201, f"status={r.status} body={await r.text() if r.status != 201 else ''}")
            if r.status == 201:
                auth = await r.json()
                auth_id = auth["id"]

            # GET auth profiles
            r = await s.get(f"{API}/auth-profiles")
            report("GET /api/auth-profiles (200)", r.status == 200, f"status={r.status}")

            r = await s.get(f"{API}/auth-profiles?project_id={proj_id}")
            report("GET /api/auth-profiles?project_id=... (200)", r.status == 200, f"status={r.status}")

            # PATCH auth profile
            if auth_id:
                r = await s.patch(f"{API}/auth-profiles/{auth_id}", json={"name": "Updated Session"})
                report("PATCH /api/auth-profiles/:id (200)", r.status == 200, f"status={r.status}")

            # DELETE auth profile
            if auth_id:
                r = await s.delete(f"{API}/auth-profiles/{auth_id}")
                report("DELETE /api/auth-profiles/:id (204)", r.status == 204, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 8. EXECUTION RUNS")
        # ═══════════════════════════════════════════════════════════

        run_id = None
        if suite_id:
            # Trigger a run
            r = await s.post(f"{API}/runs", json={
                "suite_id": suite_id,
                "browser": "chromium",
                "trigger_source": "integration_test"
            })
            report("POST /api/runs (201)", r.status == 201, f"status={r.status} body={await r.text() if r.status != 201 else ''}")
            if r.status == 201:
                run = await r.json()
                run_id = run["id"]
                report("Run has status field", "status" in run, str(run.keys()))
                report("Run status is pending", run.get("status") in ("pending", "running"), f"status={run.get('status')}")

            # Wait for run to complete (poll)
            if run_id:
                print("    ⏳ Waiting for run to complete...")
                for attempt in range(30):
                    await asyncio.sleep(2)
                    r = await s.get(f"{API}/runs/{run_id}")
                    if r.status == 200:
                        run_data = await r.json()
                        st = run_data.get("status")
                        if st in ("passed", "failed", "error"):
                            print(f"    ⏳ Run completed: {st} ({run_data.get('duration_ms')}ms)")
                            break
                else:
                    report("Run completed within 60s", False, "timeout")

                r = await s.get(f"{API}/runs/{run_id}")
                report("GET /api/runs/:id (200)", r.status == 200, f"status={r.status}")
                if r.status == 200:
                    run_data = await r.json()
                    report("Run has final status", run_data.get("status") in ("passed", "failed", "error"), f"status={run_data.get('status')}")
                    report("Run has duration_ms", run_data.get("duration_ms") is not None, f"dur={run_data.get('duration_ms')}")
                    report("Run has results array", isinstance(run_data.get("results"), list), str(type(run_data.get("results"))))
                    if run_data.get("results"):
                        tc_result = run_data["results"][0]
                        report("Result has test_case_name", "test_case_name" in tc_result, str(tc_result.keys()))
                        report("Result has step_results", "step_results" in tc_result, str(tc_result.keys()))

            # GET runs list
            r = await s.get(f"{API}/runs?limit=50")
            report("GET /api/runs (200)", r.status == 200, f"status={r.status}")
            runs = await r.json()
            report("Runs list is array", isinstance(runs, list), type(runs).__name__)

            # GET runs with status filter
            r = await s.get(f"{API}/runs?status=passed&limit=10")
            report("GET /api/runs?status=passed (200)", r.status == 200, f"status={r.status}")

            # ── Report ──
            if run_id:
                r = await s.get(f"{API}/runs/{run_id}/report")
                report("GET /api/runs/:id/report (200 or 409)", r.status in (200, 409), f"status={r.status}")
                if r.status == 200:
                    rpt = await r.json()
                    report("Report has suite_name", "suite_name" in rpt, str(rpt.keys()))
                    report("Report has total/passed/failed", all(k in rpt for k in ("total", "passed", "failed")), str(rpt.keys()))

            # ── Artifacts ──
            if run_id:
                r = await s.get(f"{API}/runs/{run_id}/artifacts")
                report("GET /api/runs/:id/artifacts (200)", r.status == 200, f"status={r.status}")
                if r.status == 200:
                    arts = await r.json()
                    report("Artifacts has traces key", "traces" in arts, str(arts.keys()))
                    report("Artifacts has screenshots key", "screenshots" in arts, str(arts.keys()))
                    report("Artifacts has videos key", "videos" in arts, str(arts.keys()))

                    # Test screenshot serving
                    ss_keys = list(arts.get("screenshots", {}).keys())
                    if ss_keys:
                        tc_ss = arts["screenshots"][ss_keys[0]]
                        if tc_ss:
                            ss_url = tc_ss[0]["url"]
                            r = await s.get(f"{BASE}{ss_url}")
                            report(f"GET screenshot ({ss_url}) → 200", r.status == 200, f"status={r.status}")
                            if r.status == 200:
                                report("Screenshot is PNG", r.content_type == "image/png", f"type={r.content_type}")

                    # Test video serving with Range header
                    if arts.get("videos"):
                        vid_url = arts["videos"][0]["url"]
                        r = await s.get(f"{BASE}{vid_url}", headers={"Range": "bytes=0-1023"})
                        report(f"GET video with Range header → 206", r.status == 206, f"status={r.status}")

                    # Test trace download
                    if arts.get("traces"):
                        trace_url = arts["traces"][0]["url"]
                        r = await s.get(f"{BASE}{trace_url}")
                        report(f"GET trace file → 200", r.status == 200, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 9. WEBHOOK TRIGGER")
        # ═══════════════════════════════════════════════════════════

        if suite_id:
            r = await s.post(f"{API}/webhooks/trigger/{suite_id}?browser=chromium")
            report("POST /api/webhooks/trigger/:suite_id (200)", r.status == 200, f"status={r.status}")
            if r.status == 200:
                wh = await r.json()
                report("Webhook returns run_id", "run_id" in wh, str(wh.keys()))
                report("Webhook returns status=queued", wh.get("status") == "queued", f"status={wh.get('status')}")

            # Webhook with invalid suite
            r = await s.post(f"{API}/webhooks/trigger/{uuid.uuid4()}?browser=chromium")
            report("Webhook with bad suite_id → 404", r.status == 404, f"status={r.status}")

            # Webhook with invalid browser
            r = await s.post(f"{API}/webhooks/trigger/{suite_id}?browser=safari")
            report("Webhook with bad browser → 400", r.status == 400, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 10. SWAGGER/DOCS")
        # ═══════════════════════════════════════════════════════════

        r = await s.get(f"{BASE}/docs")
        report("GET /docs (Swagger UI) (200)", r.status == 200, f"status={r.status}")

        r = await s.get(f"{BASE}/redoc")
        report("GET /redoc (ReDoc) (200)", r.status == 200, f"status={r.status}")

        r = await s.get(f"{BASE}/openapi.json")
        report("GET /openapi.json (200)", r.status == 200, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 11. DELETE CASCADING")
        # ═══════════════════════════════════════════════════════════

        # Delete a run
        if run_id:
            r = await s.delete(f"{API}/runs/{run_id}")
            report("DELETE /api/runs/:id (204)", r.status == 204, f"status={r.status}")

            # Confirm it's gone
            r = await s.get(f"{API}/runs/{run_id}")
            report("Deleted run returns 404", r.status == 404, f"status={r.status}")

        # Delete a test case
        if test_id:
            r = await s.delete(f"{API}/tests/{test_id}")
            report("DELETE /api/tests/:id (204)", r.status == 204, f"status={r.status}")

        # Delete suite (should cascade to remaining tests)
        if suite_id:
            r = await s.delete(f"{API}/suites/{suite_id}")
            report("DELETE /api/suites/:id (204)", r.status == 204, f"status={r.status}")

        # Delete project (should cascade to suites)
        if proj_id:
            r = await s.delete(f"{API}/projects/{proj_id}")
            report("DELETE /api/projects/:id (204)", r.status == 204, f"status={r.status}")

            # Confirm cascade
            r = await s.get(f"{API}/projects/{proj_id}")
            report("Deleted project returns 404", r.status == 404, f"status={r.status}")

        # ═══════════════════════════════════════════════════════════
        print("\n🔹 12. EDGE CASES")
        # ═══════════════════════════════════════════════════════════

        # Invalid UUID format
        r = await s.get(f"{API}/projects/not-a-uuid")
        report("Invalid UUID → 422", r.status == 422, f"status={r.status}")

        # Run trigger with non-existent suite
        r = await s.post(f"{API}/runs", json={"suite_id": str(uuid.uuid4()), "browser": "chromium"})
        report("Run with non-existent suite → 404", r.status == 404, f"status={r.status}")

        # Artifacts for non-existent run
        r = await s.get(f"{API}/runs/{uuid.uuid4()}/artifacts")
        report("Artifacts for non-existent run → 200 (empty)", r.status == 200, f"status={r.status}")

    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    print("=" * 60)
    if BUGS:
        print("\n🐛 BUGS FOUND:")
        for name, detail in BUGS:
            print(f"  ❌ {name}")
            if detail:
                print(f"     → {detail}")
    else:
        print("\n🎉 All tests passed!")
    print()

if __name__ == "__main__":
    asyncio.run(run_tests())
