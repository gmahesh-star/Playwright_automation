/**
 * API Client — wraps all backend REST calls.
 */
const API_BASE = '/api';

const api = {
  // ── Projects ──────────────────────────────────────────────────
  async getProjects() {
    const r = await fetch(`${API_BASE}/projects`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async createProject(data) {
    const r = await fetch(`${API_BASE}/projects`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async updateProject(id, data) {
    const r = await fetch(`${API_BASE}/projects/${id}`, {
      method: 'PATCH', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async deleteProject(id) {
    const r = await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' });
    if (!r.ok && r.status !== 204) throw new Error(await r.text());
  },

  // ── Suites ────────────────────────────────────────────────────
  async getSuites(projectId) {
    const q = projectId ? `?project_id=${projectId}` : '';
    const r = await fetch(`${API_BASE}/suites${q}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async createSuite(data) {
    const r = await fetch(`${API_BASE}/suites`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async updateSuite(id, data) {
    const r = await fetch(`${API_BASE}/suites/${id}`, {
      method: 'PATCH', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async deleteSuite(id) {
    const r = await fetch(`${API_BASE}/suites/${id}`, { method: 'DELETE' });
    if (!r.ok && r.status !== 204) throw new Error(await r.text());
  },

  // ── Test Cases ────────────────────────────────────────────────
  async getTests(suiteId) {
    const q = suiteId ? `?suite_id=${suiteId}` : '';
    const r = await fetch(`${API_BASE}/tests${q}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async getTest(id) {
    const r = await fetch(`${API_BASE}/tests/${id}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async createTest(data) {
    const r = await fetch(`${API_BASE}/tests`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async updateTest(id, data) {
    const r = await fetch(`${API_BASE}/tests/${id}`, {
      method: 'PATCH', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async deleteTest(id) {
    const r = await fetch(`${API_BASE}/tests/${id}`, { method: 'DELETE' });
    if (!r.ok && r.status !== 204) throw new Error(await r.text());
  },
  async exportTest(id, lang = 'python') {
    const r = await fetch(`${API_BASE}/tests/${id}/export?lang=${lang}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  // ── Runs ──────────────────────────────────────────────────────
  async getRuns(statusFilter) {
    let q = '?limit=50';
    if (statusFilter) q += `&status=${statusFilter}`;
    const r = await fetch(`${API_BASE}/runs${q}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async getRun(id) {
    const r = await fetch(`${API_BASE}/runs/${id}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async getRunReport(id) {
    const r = await fetch(`${API_BASE}/runs/${id}/report`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async createRun(data) {
    const r = await fetch(`${API_BASE}/runs`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async deleteRun(id) {
    const r = await fetch(`${API_BASE}/runs/${id}`, { method: 'DELETE' });
    if (!r.ok && r.status !== 204) throw new Error(await r.text());
  },
  async getRunArtifacts(id) {
    const r = await fetch(`${API_BASE}/runs/${id}/artifacts`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  // ── Auth Profiles ─────────────────────────────────────────────
  async getAuthProfiles(projectId) {
    const q = projectId ? `?project_id=${projectId}` : '';
    const r = await fetch(`${API_BASE}/auth-profiles${q}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async createAuthProfile(data) {
    const r = await fetch(`${API_BASE}/auth-profiles`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async deleteAuthProfile(id) {
    const r = await fetch(`${API_BASE}/auth-profiles/${id}`, { method: 'DELETE' });
    if (!r.ok && r.status !== 204) throw new Error(await r.text());
  },

  // ── Recorder ──────────────────────────────────────────────────
  async startRecording(data) {
    const r = await fetch(`${API_BASE}/recorder/start`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async stopRecording(sessionId) {
    const r = await fetch(`${API_BASE}/recorder/stop/${sessionId}`, { method: 'POST' });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async injectAssertion(sessionId, assertion) {
    const r = await fetch(`${API_BASE}/recorder/assert/${sessionId}`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ assertion }),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  // ── Artifacts ──────────────────────────────────────────────────
  async getRunArtifacts(id) {
    const r = await fetch(`${API_BASE}/runs/${id}/artifacts`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  // ── Webhook ───────────────────────────────────────────────────
  async webhookTrigger(suiteId, browser = 'chromium') {
    const r = await fetch(`${API_BASE}/webhooks/trigger/${suiteId}?browser=${browser}`, {
      method: 'POST',
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};
