/**
 * Playwright Testing Platform — Main Application Logic
 */

// ═══════════════════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════════════════
const state = {
  currentPage: 'tests',
  projects: [],
  suites: [],
  tests: [],
  runs: [],
  runsTotal: 0,
  runsLimit: 20,
  runsOffset: 0,
  authProfiles: [],
  selectedProjectId: null,
  selectedSuiteId: null,
  selectedTestId: null,
  recorderSessionId: null,
  recorderWs: null,
  recordedSteps: [],
  modalType: null,
  ctxMenuEl: null,
};

// ═══════════════════════════════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  loadProjects();
  // Close context menu on click outside
  document.addEventListener('click', (e) => {
    if (state.ctxMenuEl && !state.ctxMenuEl.contains(e.target)) {
      state.ctxMenuEl.remove();
      state.ctxMenuEl = null;
    }
  });
});

// ═══════════════════════════════════════════════════════════════════
// Navigation
// ═══════════════════════════════════════════════════════════════════
function navigate(page) {
  state.currentPage = page;
  // Stop runs auto-refresh when navigating away from runs page
  if (page !== 'runs') _stopRunsAutoRefresh();
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === page);
  });
  document.querySelectorAll('.page').forEach(el => {
    el.style.display = 'none';
  });
  const target = document.getElementById(`page-${page}`);
  if (target) {
    target.style.display = page === 'tests' ? 'flex' : 'block';
  }
  // Load data for the page
  if (page === 'runs') loadRuns();
  if (page === 'codegen') loadCodegenTests();
  if (page === 'auth') loadAuthProfiles();
}

function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  sb.classList.toggle('collapsed');
  const main = document.getElementById('main-content');
  main.style.left = sb.classList.contains('collapsed') ? '56px' : '180px';
}

function openSwagger() {
  window.open('/docs', '_blank');
}

// ═══════════════════════════════════════════════════════════════════
// Projects Panel
// ═══════════════════════════════════════════════════════════════════
async function loadProjects() {
  try {
    state.projects = await api.getProjects();
    renderProjects();
  } catch (e) {
    toast('Failed to load projects: ' + e.message, 'error');
  }
}

function renderProjects() {
  const el = document.getElementById('projects-list');
  if (state.projects.length === 0) {
    el.innerHTML = '<div class="empty-state">No projects yet. Click + to create one.</div>';
    document.getElementById('projects-pagination').textContent = '0 of 0';
    return;
  }
  el.innerHTML = state.projects.map((p, i) => `
    <div class="list-item ${state.selectedProjectId === p.id ? 'selected' : ''}"
         onclick="selectProject('${p.id}')" data-id="${p.id}">
      <span class="list-item-num">${i + 1}</span>
      <span class="list-item-name">${esc(p.name)}</span>
      <button class="list-item-menu" onclick="event.stopPropagation(); showCtxMenu(event, 'project', '${p.id}', '${esc(p.name)}')"
              title="Actions">
        <span class="material-icons-outlined">more_horiz</span>
      </button>
    </div>
  `).join('');
  document.getElementById('projects-pagination').textContent =
    `1 – ${state.projects.length} of ${state.projects.length}`;
}

async function selectProject(id) {
  state.selectedProjectId = id;
  state.selectedSuiteId = null;
  state.selectedTestId = null;
  const proj = state.projects.find(p => p.id === id);
  document.getElementById('bc-sel-project').textContent = proj ? proj.name : '—';
  document.getElementById('bc-sel-suite').textContent = '—';
  document.getElementById('sidebar-project-name').textContent = proj ? proj.name : 'Playwright Platform';
  renderProjects();
  await loadSuites(id);
  clearTests();
}

// ═══════════════════════════════════════════════════════════════════
// Suites Panel
// ═══════════════════════════════════════════════════════════════════
async function loadSuites(projectId) {
  try {
    state.suites = await api.getSuites(projectId);
    renderSuites();
  } catch (e) {
    toast('Failed to load suites: ' + e.message, 'error');
  }
}

function renderSuites() {
  const el = document.getElementById('suites-list');
  const runBtn = document.getElementById('btn-run-suite');
  if (state.suites.length === 0) {
    el.innerHTML = state.selectedProjectId
      ? '<div class="empty-state">No suites in this project. Click + to create one.</div>'
      : '<div class="empty-state">Please select a Project to view its Test Suites.</div>';
    runBtn.style.display = 'none';
    document.getElementById('suites-pagination').textContent = '0 of 0';
    return;
  }
  el.innerHTML = state.suites.map((s, i) => {
    const tagsHtml = (s.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join('');
    return `
      <div class="list-item ${state.selectedSuiteId === s.id ? 'selected' : ''}"
           onclick="selectSuite('${s.id}')" data-id="${s.id}">
        <span class="list-item-num">${i + 1}</span>
        <div style="flex:1;min-width:0">
          <span class="list-item-name">${esc(s.name)}</span>
          ${tagsHtml ? `<div class="list-item-tags">${tagsHtml}</div>` : ''}
        </div>
        <button class="list-item-menu" onclick="event.stopPropagation(); showCtxMenu(event, 'suite', '${s.id}', '${esc(s.name)}')"
                title="Actions">
          <span class="material-icons-outlined">more_horiz</span>
        </button>
      </div>
    `;
  }).join('');
  runBtn.style.display = state.selectedSuiteId ? 'flex' : 'none';
  document.getElementById('suites-pagination').textContent =
    `1 – ${state.suites.length} of ${state.suites.length}`;
}

async function selectSuite(id) {
  state.selectedSuiteId = id;
  state.selectedTestId = null;
  const suite = state.suites.find(s => s.id === id);
  document.getElementById('bc-sel-suite').textContent = suite ? suite.name : '—';
  renderSuites();
  await loadTests(id);
}

// ═══════════════════════════════════════════════════════════════════
// Test Cases Panel
// ═══════════════════════════════════════════════════════════════════
async function loadTests(suiteId) {
  try {
    state.tests = await api.getTests(suiteId);
    renderTests();
  } catch (e) {
    toast('Failed to load tests: ' + e.message, 'error');
  }
}

function clearTests() {
  state.tests = [];
  const tbody = document.getElementById('tests-tbody');
  tbody.innerHTML = '';
  document.getElementById('tests-empty').style.display = 'block';
  document.getElementById('tests-table').style.display = 'none';
  document.getElementById('tests-pagination').textContent = '0 of 0';
}

function renderTests() {
  const tbody = document.getElementById('tests-tbody');
  const emptyEl = document.getElementById('tests-empty');
  const tableEl = document.getElementById('tests-table');

  if (state.tests.length === 0) {
    tbody.innerHTML = '';
    emptyEl.style.display = 'block';
    emptyEl.textContent = state.selectedSuiteId
      ? 'No test cases in this suite. Click + to create one.'
      : 'Please select a Project and then a Test Suite to view its Test Cases.';
    tableEl.style.display = 'none';
    document.getElementById('tests-pagination').textContent = '0 of 0';
    return;
  }

  emptyEl.style.display = 'none';
  tableEl.style.display = 'table';

  tbody.innerHTML = state.tests.map((t, i) => {
    const stepCount = (t.steps || []).length;
    const assertCount = (t.assertions || []).length;
    return `
      <tr class="${state.selectedTestId === t.id ? 'selected' : ''}"
          onclick="selectTest('${t.id}')">
        <td><input type="checkbox" onclick="event.stopPropagation()"></td>
        <td>${i + 1}</td>
        <td style="font-weight:600;color:#1f2937">${esc(t.name)}</td>
        <td>
          <span style="color:#3b82f6;font-weight:600">${stepCount}</span> steps
          ${assertCount ? `, <span style="color:#8b5cf6;font-weight:600">${assertCount}</span> asserts` : ''}
        </td>
        <td style="color:#6b7280;font-size:12px">${esc(t.description || '—')}</td>
        <td>
          <button class="icon-btn" onclick="event.stopPropagation(); showCtxMenu(event, 'test', '${t.id}', '${esc(t.name)}')" title="Actions">
            <span class="material-icons-outlined">more_vert</span>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  document.getElementById('tests-pagination').textContent =
    `1 – ${state.tests.length} of ${state.tests.length}`;
  document.getElementById('btn-export').style.display = state.selectedTestId ? 'flex' : 'none';
}

function selectTest(id) {
  state.selectedTestId = id;
  renderTests();
  document.getElementById('btn-export').style.display = 'flex';
  document.getElementById('btn-run-test').style.display = 'flex';
}

function clearTestSelection() {
  state.selectedProjectId = null;
  state.selectedSuiteId = null;
  state.selectedTestId = null;
  document.getElementById('bc-sel-project').textContent = '—';
  document.getElementById('bc-sel-suite').textContent = '—';
  document.getElementById('sidebar-project-name').textContent = 'Playwright Platform';
  renderProjects();
  state.suites = [];
  renderSuites();
  clearTests();
}

// ═══════════════════════════════════════════════════════════════════
// Context Menu
// ═══════════════════════════════════════════════════════════════════
function showCtxMenu(event, type, id, name) {
  if (state.ctxMenuEl) { state.ctxMenuEl.remove(); state.ctxMenuEl = null; }

  const menu = document.createElement('div');
  menu.className = 'ctx-menu';

  let items = '';
  if (type === 'project') {
    items = `
      <div class="ctx-item" onclick="editItem('project','${id}')">
        <span class="material-icons-outlined">edit</span> Rename
      </div>
      <div class="ctx-item danger" onclick="deleteItem('project','${id}','${name}')">
        <span class="material-icons-outlined">delete</span> Delete
      </div>`;
  } else if (type === 'suite') {
    items = `
      <div class="ctx-item" onclick="runSuiteById('${id}')">
        <span class="material-icons-outlined">play_arrow</span> Run Suite
      </div>
      <div class="ctx-item" onclick="editItem('suite','${id}')">
        <span class="material-icons-outlined">edit</span> Rename
      </div>
      <div class="ctx-item danger" onclick="deleteItem('suite','${id}','${name}')">
        <span class="material-icons-outlined">delete</span> Delete
      </div>`;
  } else if (type === 'test') {
    items = `
      <div class="ctx-item" onclick="viewTestDetail('${id}')">
        <span class="material-icons-outlined">visibility</span> View Details
      </div>
      <div class="ctx-item" onclick="exportTestById('${id}')">
        <span class="material-icons-outlined">code</span> Export Code
      </div>
      <div class="ctx-item danger" onclick="deleteItem('test','${id}','${name}')">
        <span class="material-icons-outlined">delete</span> Delete
      </div>`;
  }

  menu.innerHTML = items;
  document.body.appendChild(menu);

  // Position near click
  const rect = event.target.getBoundingClientRect();
  menu.style.top = rect.bottom + 4 + 'px';
  menu.style.left = Math.min(rect.left, window.innerWidth - 180) + 'px';

  state.ctxMenuEl = menu;
}

async function deleteItem(type, id, name) {
  if (state.ctxMenuEl) { state.ctxMenuEl.remove(); state.ctxMenuEl = null; }
  if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
  try {
    if (type === 'project') {
      await api.deleteProject(id);
      if (state.selectedProjectId === id) clearTestSelection();
      await loadProjects();
    } else if (type === 'suite') {
      await api.deleteSuite(id);
      if (state.selectedSuiteId === id) { state.selectedSuiteId = null; clearTests(); }
      await loadSuites(state.selectedProjectId);
    } else if (type === 'test') {
      await api.deleteTest(id);
      await loadTests(state.selectedSuiteId);
    }
    toast(`${name} deleted`, 'success');
  } catch (e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

function editItem(type, id) {
  if (state.ctxMenuEl) { state.ctxMenuEl.remove(); state.ctxMenuEl = null; }
  const name = prompt('Enter new name:');
  if (!name) return;
  (async () => {
    try {
      if (type === 'project') {
        await api.updateProject(id, { name });
        await loadProjects();
      } else if (type === 'suite') {
        await api.updateSuite(id, { name });
        await loadSuites(state.selectedProjectId);
      }
      toast('Renamed successfully', 'success');
    } catch (e) {
      toast('Rename failed: ' + e.message, 'error');
    }
  })();
}

// ═══════════════════════════════════════════════════════════════════
// Modal (Create Project / Suite / Test)
// ═══════════════════════════════════════════════════════════════════
function showModal(type) {
  state.modalType = type;
  const overlay = document.getElementById('modal-overlay');
  const title = document.getElementById('modal-title');
  const body = document.getElementById('modal-body');

  if (type === 'project') {
    title.textContent = 'Create Project';
    body.innerHTML = `
      <div class="form-group">
        <label>Project Name *</label>
        <input type="text" id="m-name" class="form-input" placeholder="My Application Tests">
      </div>
      <div class="form-group">
        <label>Description</label>
        <input type="text" id="m-desc" class="form-input" placeholder="Optional description">
      </div>`;
  } else if (type === 'suite') {
    if (!state.selectedProjectId) { toast('Select a project first', 'error'); return; }
    title.textContent = 'Create Test Suite';
    body.innerHTML = `
      <div class="form-group">
        <label>Suite Name *</label>
        <input type="text" id="m-name" class="form-input" placeholder="Login Flow Tests">
      </div>
      <div class="form-group">
        <label>Tags (comma separated)</label>
        <input type="text" id="m-tags" class="form-input" placeholder="smoke, login, critical">
      </div>`;
  } else if (type === 'test') {
    if (!state.selectedSuiteId) { toast('Select a suite first', 'error'); return; }
    title.textContent = 'Create Test Case';
    body.innerHTML = `
      <div class="form-group">
        <label>Test Name *</label>
        <input type="text" id="m-name" class="form-input" placeholder="User Login Flow">
      </div>
      <div class="form-group">
        <label>Description</label>
        <input type="text" id="m-desc" class="form-input" placeholder="Optional description">
      </div>
      <div class="form-group">
        <label>Steps (JSON array)</label>
        <textarea id="m-steps" class="form-textarea" placeholder='[{"action":"navigate","url":"https://example.com"},{"action":"click","selector":"#btn"}]'>[{"action": "navigate", "url": "https://example.com"}]</textarea>
      </div>
      <div class="form-group">
        <label>Assertions (JSON array, optional)</label>
        <textarea id="m-asserts" class="form-textarea" style="min-height:80px" placeholder='[{"assertion_type":"to_be_visible","selector":"h1"}]'>[]</textarea>
      </div>`;
  } else if (type === 'auth-profile') {
    title.textContent = 'Create Auth Profile';
    body.innerHTML = `
      <div class="form-group">
        <label>Profile Name *</label>
        <input type="text" id="m-name" class="form-input" placeholder="Admin Session">
      </div>
      <div class="form-group">
        <label>Project</label>
        <select id="m-project" class="form-input">
          ${state.projects.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label>Description</label>
        <input type="text" id="m-desc" class="form-input" placeholder="Logged-in admin user session">
      </div>`;
  }

  overlay.classList.add('show');
  setTimeout(() => {
    const first = body.querySelector('input,textarea');
    if (first) first.focus();
  }, 100);
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('show');
  state.modalType = null;
}

async function submitModal() {
  const type = state.modalType;
  try {
    if (type === 'project') {
      const name = document.getElementById('m-name').value.trim();
      const desc = document.getElementById('m-desc').value.trim();
      if (!name) { toast('Name is required', 'error'); return; }
      await api.createProject({ name, description: desc || null });
      toast('Project created!', 'success');
      await loadProjects();
    } else if (type === 'suite') {
      const name = document.getElementById('m-name').value.trim();
      const tags = document.getElementById('m-tags').value.split(',').map(t => t.trim()).filter(Boolean);
      if (!name) { toast('Name is required', 'error'); return; }
      await api.createSuite({ project_id: state.selectedProjectId, name, tags });
      toast('Suite created!', 'success');
      await loadSuites(state.selectedProjectId);
    } else if (type === 'test') {
      const name = document.getElementById('m-name').value.trim();
      const desc = document.getElementById('m-desc').value.trim();
      let steps, assertions;
      try { steps = JSON.parse(document.getElementById('m-steps').value); } catch { toast('Invalid steps JSON', 'error'); return; }
      try { assertions = JSON.parse(document.getElementById('m-asserts').value); } catch { assertions = []; }
      if (!name) { toast('Name is required', 'error'); return; }
      await api.createTest({
        suite_id: state.selectedSuiteId, name,
        description: desc || null, steps, assertions,
      });
      toast('Test case created!', 'success');
      await loadTests(state.selectedSuiteId);
    } else if (type === 'auth-profile') {
      const name = document.getElementById('m-name').value.trim();
      const projectId = document.getElementById('m-project').value;
      const desc = document.getElementById('m-desc').value.trim();
      if (!name) { toast('Name is required', 'error'); return; }
      await api.createAuthProfile({ project_id: projectId, name, description: desc || null });
      toast('Auth profile created!', 'success');
      await loadAuthProfiles();
    }
    closeModal();
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
// Recorder
// ═══════════════════════════════════════════════════════════════════
async function startRecording() {
  const url = document.getElementById('rec-url').value.trim();
  if (!url) { toast('Enter a URL to record', 'error'); return; }

  const browser = document.getElementById('rec-browser').value;
  const headless = document.getElementById('rec-headless').value === 'true';

  try {
    document.getElementById('btn-rec-start').disabled = true;
    document.getElementById('btn-rec-start').innerHTML = '<span class="material-icons-outlined">hourglass_empty</span> Launching...';

    const result = await api.startRecording({ url, browser, headless });
    state.recorderSessionId = result.session_id;
    state.recordedSteps = [];

    document.getElementById('btn-rec-start').style.display = 'none';
    document.getElementById('btn-rec-stop').style.display = 'inline-flex';
    document.getElementById('rec-live').style.display = 'block';
    document.getElementById('rec-session-id').textContent = result.session_id;
    document.getElementById('rec-steps-stream').innerHTML = '';

    // Connect WebSocket for live steps
    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${location.host}/ws/recorder/${result.session_id}`;
    state.recorderWs = new WebSocket(wsUrl);

    state.recorderWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.step) {
          state.recordedSteps.push(data.step);
          appendRecordedStep(data.step, state.recordedSteps.length);
        }
      } catch (e) { /* ignore parse errors */ }
    };

    state.recorderWs.onclose = () => {
      toast('WebSocket connection closed', 'info');
    };

    toast('Recording started! Interact with the browser.', 'success');
  } catch (e) {
    toast('Failed to start recording: ' + e.message, 'error');
    document.getElementById('btn-rec-start').disabled = false;
    document.getElementById('btn-rec-start').innerHTML = '<span class="material-icons-outlined">fiber_manual_record</span> Start Recording';
  }
}

function appendRecordedStep(step, num) {
  const container = document.getElementById('rec-steps-stream');
  const actionClass = {
    navigate: 'navigate', click: 'click', fill: 'fill',
    press: 'press', check: 'check', selectOption: 'select', wait: 'wait',
  }[step.action] || 'default';

  const detail = step.url || step.selector || step.key || '';
  const value = step.value ? ` → "${step.value}"` : '';

  const div = document.createElement('div');
  div.className = 'step-entry';
  div.innerHTML = `
    <span class="step-num">${num}</span>
    <span class="step-action step-action-${actionClass}">${step.action}</span>
    <span class="step-detail">${esc(detail)}${esc(value)}</span>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

async function stopRecording() {
  if (!state.recorderSessionId) return;
  try {
    const result = await api.stopRecording(state.recorderSessionId);
    state.recordedSteps = result.steps || state.recordedSteps;

    if (state.recorderWs) { state.recorderWs.close(); state.recorderWs = null; }

    document.getElementById('btn-rec-stop').style.display = 'none';
    document.getElementById('btn-rec-start').style.display = 'inline-flex';
    document.getElementById('btn-rec-start').disabled = false;
    document.getElementById('btn-rec-start').innerHTML = '<span class="material-icons-outlined">fiber_manual_record</span> Start Recording';

    toast(`Recording stopped. ${state.recordedSteps.length} steps captured (${result.duration_ms}ms)`, 'success');
  } catch (e) {
    toast('Failed to stop recording: ' + e.message, 'error');
  }
}

async function saveRecording() {
  if (state.recordedSteps.length === 0) { toast('No steps recorded', 'error'); return; }
  if (!state.selectedSuiteId) {
    toast('Select a project and suite first (from the Tests page) to save into', 'error');
    return;
  }
  const name = prompt('Test case name:', 'Recorded Test');
  if (!name) return;
  try {
    await api.createTest({
      suite_id: state.selectedSuiteId,
      name,
      description: 'Recorded via browser recorder',
      steps: state.recordedSteps,
      assertions: [],
    });
    toast('Test case saved!', 'success');
    state.recordedSteps = [];
    document.getElementById('rec-live').style.display = 'none';
  } catch (e) {
    toast('Save failed: ' + e.message, 'error');
  }
}

function showAssertionModal() {
  if (!state.recorderSessionId) return;
  const type = prompt('Assertion type:\n1. to_be_visible\n2. to_have_text\n3. to_have_url\n4. to_have_count\n\nEnter type name:');
  if (!type) return;
  const selector = prompt('CSS Selector (leave empty for URL assertions):');
  const value = prompt('Expected value (leave empty for visibility):');
  (async () => {
    try {
      await api.injectAssertion(state.recorderSessionId, {
        assertion_type: type,
        selector: selector || null,
        expected_value: value || null,
      });
      toast('Assertion injected', 'success');
    } catch (e) {
      toast('Failed: ' + e.message, 'error');
    }
  })();
}

// ═══════════════════════════════════════════════════════════════════
// Execution Runs
// ═══════════════════════════════════════════════════════════════════
let _runsAutoRefreshTimer = null;

function _runsFilterParams() {
  const value = id => document.getElementById(id)?.value || '';
  const after = value('runs-filter-after');
  const before = value('runs-filter-before');
  return {
    status: value('runs-filter-status') || undefined,
    suite_id: value('runs-filter-suite') || undefined,
    created_after: after ? new Date(after).toISOString() : undefined,
    created_before: before ? new Date(before).toISOString() : undefined,
  };
}

async function _populateRunSuiteFilter() {
  const sel = document.getElementById('runs-filter-suite');
  if (!sel || sel.dataset.loaded === '1') return;
  try {
    const suites = await api.getSuites();
    const current = sel.value;
    sel.innerHTML = '<option value="">All Suites</option>' +
      suites.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
    sel.value = current;
    sel.dataset.loaded = '1';
  } catch (_) { /* filter is optional */ }
}

async function _fetchRuns() {
  const page = await api.getRunsPage({
    ..._runsFilterParams(),
    limit: state.runsLimit,
    offset: state.runsOffset,
  });

  if (page.runs.length === 0 && page.total > 0 && state.runsOffset > 0) {
    state.runsOffset = Math.max(
      0,
      Math.floor((page.total - 1) / state.runsLimit) * state.runsLimit
    );
    return _fetchRuns();
  }

  state.runs = page.runs;
  state.runsTotal = page.total;
  state.runsOffset = page.offset;
  renderRuns();
  renderRunsPagination();
}

function _startRunsAutoRefresh() {
  _stopRunsAutoRefresh();
  // If any runs are pending or running, poll every 3s
  const hasActive = state.runs.some(r => r.status === 'pending' || r.status === 'running');
  if (hasActive) {
    _runsAutoRefreshTimer = setInterval(async () => {
      try {
        await _fetchRuns();
        // Stop polling if no more active runs
        if (!state.runs.some(r => r.status === 'pending' || r.status === 'running')) {
          _stopRunsAutoRefresh();
        }
      } catch (_) { /* silently ignore poll errors */ }
    }, 3000);
  }
}

function _stopRunsAutoRefresh() {
  if (_runsAutoRefreshTimer) {
    clearInterval(_runsAutoRefreshTimer);
    _runsAutoRefreshTimer = null;
  }
}

async function loadRuns(reset = true) {
  if (reset) state.runsOffset = 0;
  await _populateRunSuiteFilter();
  try {
    await _fetchRuns();
    _startRunsAutoRefresh();
  } catch (e) {
    toast('Failed to load runs: ' + e.message, 'error');
  }
}

function renderRuns() {
  const tbody = document.getElementById('runs-tbody');
  const emptyEl = document.getElementById('runs-empty');

  if (state.runs.length === 0) {
    tbody.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  tbody.innerHTML = state.runs.map(r => {
    const statusClass = `status-${r.status}`;
    const dur = r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : '—';
    const started = r.started_at ? new Date(r.started_at).toLocaleString() : '—';
    const resultSummary = r.results
      ? `${r.results.filter(x => x.status === 'passed').length}/${r.results.length}`
      : '—';
    const isActive = r.status === 'pending' || r.status === 'running';
    const hasFailed = (r.results || []).some(x => x.status === 'failed' || x.status === 'error');
    const retryMode = hasFailed ? 'failed' : 'all';
    const actionButton = isActive
      ? `<button class="icon-btn" onclick="cancelRun('${r.id}')" title="Cancel Run">
           <span class="material-icons-outlined" style="font-size:18px">stop_circle</span>
         </button>`
      : `<button class="icon-btn" onclick="retryRun('${r.id}', '${retryMode}')" title="${hasFailed ? 'Retry Failed' : 'Retry All'}">
           <span class="material-icons-outlined" style="font-size:18px">replay</span>
         </button>`;
    return `
      <tr>
        <td><span class="status-badge ${statusClass}">${r.status}</span></td>
        <td style="font-family:monospace;font-size:11px;color:#6b7280">${r.id.substring(0, 8)}…</td>
        <td>${r.browser}</td>
        <td>${dur}</td>
        <td style="font-size:12px">${started}</td>
        <td style="font-weight:600">${resultSummary}</td>
        <td>
          <button class="icon-btn" onclick="viewRunDetail('${r.id}')" title="View Details">
            <span class="material-icons-outlined">visibility</span>
          </button>
          ${actionButton}
          <button class="icon-btn" onclick="deleteRun('${r.id}')" title="Delete">
            <span class="material-icons-outlined" style="font-size:18px">delete</span>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function renderRunsPagination() {
  const infoEl = document.getElementById('runs-pagination-info');
  const prevBtn = document.getElementById('runs-prev');
  const nextBtn = document.getElementById('runs-next');
  if (!infoEl || !prevBtn || !nextBtn) return;

  const start = state.runsTotal ? state.runsOffset + 1 : 0;
  const end = Math.min(state.runsOffset + state.runs.length, state.runsTotal);
  infoEl.textContent = `${start}–${end} of ${state.runsTotal}`;
  prevBtn.disabled = state.runsOffset <= 0;
  nextBtn.disabled = state.runsOffset + state.runsLimit >= state.runsTotal;
}

function runsPrevPage() {
  if (state.runsOffset <= 0) return;
  state.runsOffset = Math.max(0, state.runsOffset - state.runsLimit);
  loadRuns(false);
}

function runsNextPage() {
  if (state.runsOffset + state.runsLimit >= state.runsTotal) return;
  state.runsOffset += state.runsLimit;
  loadRuns(false);
}

async function cancelRun(id) {
  if (!confirm('Cancel this run?')) return;
  try {
    const result = await api.cancelRun(id);
    toast(result.message || 'Cancellation requested', 'success');
    await loadRuns(false);
  } catch (e) {
    toast('Cancel failed: ' + e.message, 'error');
  }
}

async function retryRun(id, mode = 'all') {
  try {
    const run = await api.retryRun(id, mode);
    toast(`Retry started: ${run.id.substring(0, 8)}…`, 'success');
    navigate('runs');
  } catch (e) {
    toast('Retry failed: ' + e.message, 'error');
  }
}

function getSelectedBrowser() {
  const sel = document.getElementById('run-browser-select');
  return sel ? sel.value : 'chromium';
}

async function runSelectedSuite() {
  if (!state.selectedSuiteId) return;
  try {
    const browser = getSelectedBrowser();
    const run = await api.createRun({ suite_id: state.selectedSuiteId, browser });
    toast(`Run started on ${browser}: ${run.id.substring(0, 8)}…`, 'success');
    watchRunLive(run.id);
  } catch (e) {
    toast('Failed to trigger run: ' + e.message, 'error');
  }
}

async function runSuiteById(suiteId) {
  if (state.ctxMenuEl) { state.ctxMenuEl.remove(); state.ctxMenuEl = null; }
  try {
    const browser = getSelectedBrowser();
    const run = await api.createRun({ suite_id: suiteId, browser });
    toast(`Run started on ${browser}: ${run.id.substring(0, 8)}…`, 'success');
    watchRunLive(run.id);
  } catch (e) {
    toast('Failed to trigger run: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
// Live Run Progress (WebSocket)
// ═══════════════════════════════════════════════════════════════════
let _liveWs = null;

function watchRunLive(runId) {
  // Show the replay page with a live progress view
  document.querySelectorAll('.page').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const replayPage = document.getElementById('page-replay');
  replayPage.style.display = 'block';

  document.getElementById('replay-title').textContent = `Run ${runId.substring(0, 8)}… — Live`;
  document.getElementById('replay-summary').innerHTML =
    '<div class="rsummary-card"><div class="rsummary-label">Status</div><div class="rsummary-value"><span class="status-badge status-running" id="live-status">running</span></div></div>' +
    '<div class="rsummary-card"><div class="rsummary-label">Elapsed</div><div class="rsummary-value" id="live-elapsed">0.0s</div></div>' +
    '<div class="rsummary-card"><div class="rsummary-label">Steps</div><div class="rsummary-value" id="live-steps-count">0 / ?</div></div>';
  document.getElementById('replay-actions').innerHTML = '';

  // Hide video/screenshot sections, show live log
  const videoSec = document.getElementById('replay-video-section');
  const ssSec = document.getElementById('replay-screenshots-section');
  if (videoSec) videoSec.style.display = 'none';
  if (ssSec) ssSec.style.display = 'none';

  // Create live progress container in the results section
  let liveContainer = document.getElementById('live-progress-container');
  if (!liveContainer) {
    liveContainer = document.createElement('div');
    liveContainer.id = 'live-progress-container';
    replayPage.querySelector('.page-single').appendChild(liveContainer);
  }
  liveContainer.innerHTML =
    '<div class="live-progress-panel">' +
      '<h2><span class="material-icons-outlined" style="vertical-align:middle;animation:pulse 1.5s infinite">play_circle</span> Live Execution Progress</h2>' +
      '<div class="live-test-cases" id="live-test-cases"></div>' +
      '<div class="live-log" id="live-log"></div>' +
    '</div>';
  liveContainer.style.display = 'block';

  // Start elapsed timer
  const startTime = Date.now();
  const elapsedTimer = setInterval(() => {
    const el = document.getElementById('live-elapsed');
    if (el) el.textContent = ((Date.now() - startTime) / 1000).toFixed(1) + 's';
  }, 100);

  // Connect WebSocket
  if (_liveWs) { try { _liveWs.close(); } catch(_){} }
  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  _liveWs = new WebSocket(`${wsProtocol}//${location.host}/ws/runs/${runId}`);

  let totalSteps = null;
  let completedSteps = 0;

  _liveWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'test_case_start') {
        totalSteps = msg.total_steps;
        completedSteps = 0;
        const tcDiv = document.getElementById('live-test-cases');
        tcDiv.innerHTML =
          '<div class="live-tc-header">' +
            '<span class="material-icons-outlined" style="color:#2563eb;animation:pulse 1.5s infinite">science</span> ' +
            '<strong>' + esc(msg.test_case_name) + '</strong>' +
            ' <span style="color:#6b7280;font-size:12px">(' + msg.total_steps + ' steps)</span>' +
          '</div>' +
          '<div class="live-steps-list" id="live-steps-list"></div>';
        document.getElementById('live-steps-count').textContent = `0 / ${totalSteps}`;
      }
      else if (msg.type === 'step_progress') {
        completedSteps++;
        const stepsList = document.getElementById('live-steps-list');
        if (stepsList) {
          const icon = msg.status === 'passed' ? 'check_circle'
            : msg.status === 'skipped' ? 'skip_next' : 'cancel';
          const color = msg.status === 'passed' ? '#22c55e'
            : msg.status === 'skipped' ? '#94a3b8' : '#dc2626';
          const errorHtml = msg.error
            ? '<div class="live-step-error">' + esc(msg.error).substring(0, 200) + '</div>'
            : '';
          stepsList.innerHTML +=
            '<div class="live-step-row">' +
              '<span class="material-icons-outlined" style="color:' + color + ';font-size:18px">' + icon + '</span> ' +
              '<span class="live-step-idx">Step ' + msg.step_index + '</span> ' +
              '<span class="live-step-action">' + esc(msg.action || '') + '</span> ' +
              '<span class="live-step-dur">' + (msg.duration_ms || 0) + 'ms</span>' +
              (msg.status === 'failed'
                ? ' <span class="status-badge status-failed">failed</span>'
                : msg.status === 'skipped'
                  ? ' <span class="status-badge status-skipped">skipped</span>'
                  : '') +
              errorHtml +
            '</div>';
          // Auto-scroll to bottom
          stepsList.scrollTop = stepsList.scrollHeight;
        }
        const countEl = document.getElementById('live-steps-count');
        if (countEl) countEl.textContent = `${completedSteps} / ${totalSteps || '?'}`;
      }
      else if (msg.type === 'status_update') {
        const statusEl = document.getElementById('live-status');
        if (statusEl) {
          statusEl.textContent = msg.status;
          statusEl.className = 'status-badge status-' + msg.status;
        }
      }
      else if (msg.type === 'complete') {
        clearInterval(elapsedTimer);
        const statusEl = document.getElementById('live-status');
        if (statusEl) {
          statusEl.textContent = msg.status;
          statusEl.className = 'status-badge status-' + msg.status;
        }
        const elapsedEl = document.getElementById('live-elapsed');
        if (elapsedEl) elapsedEl.textContent = ((msg.duration_ms || 0) / 1000).toFixed(1) + 's';

        // Add a "View Full Results" button
        const actionsEl = document.getElementById('replay-actions');
        if (actionsEl) {
          actionsEl.innerHTML =
            '<button class="btn btn-primary" onclick="viewRunDetail(\'' + runId + '\')">View Full Results</button> ' +
            '<button class="btn btn-outline" onclick="navigate(\'runs\')">Back to Runs</button>';
        }
        document.getElementById('replay-title').textContent = `Run ${runId.substring(0, 8)}… — Complete`;
      }
    } catch (e) {
      console.warn('WS parse error:', e);
    }
  };

  _liveWs.onerror = () => {
    clearInterval(elapsedTimer);
    // Fallback: poll API instead
    _pollRunProgress(runId, startTime, elapsedTimer);
  };

  _liveWs.onclose = () => {
    clearInterval(elapsedTimer);
  };
}

async function _pollRunProgress(runId, startTime, elapsedTimer) {
  // Simple fallback: poll the run status every 2 seconds
  const poll = setInterval(async () => {
    try {
      const run = await api.getRun(runId);
      const statusEl = document.getElementById('live-status');
      if (statusEl) {
        statusEl.textContent = run.status;
        statusEl.className = 'status-badge status-' + run.status;
      }
      if (['passed', 'failed', 'error', 'cancelled'].includes(run.status)) {
        clearInterval(poll);
        clearInterval(elapsedTimer);
        const elapsedEl = document.getElementById('live-elapsed');
        if (elapsedEl) elapsedEl.textContent = ((run.duration_ms || 0) / 1000).toFixed(1) + 's';
        const actionsEl = document.getElementById('replay-actions');
        if (actionsEl) {
          actionsEl.innerHTML =
            '<button class="btn btn-primary" onclick="viewRunDetail(\'' + runId + '\')">View Full Results</button> ' +
            '<button class="btn btn-outline" onclick="navigate(\'runs\')">Back to Runs</button>';
        }
        document.getElementById('replay-title').textContent = `Run ${runId.substring(0, 8)}… — Complete`;
      }
    } catch (_) {}
  }, 2000);
}

async function viewRunDetail(runId) {
  try {
    // Fetch run data and artifacts in parallel
    const [run, artifacts] = await Promise.all([
      api.getRun(runId),
      api.getRunArtifacts(runId).catch(() => ({ traces: [], screenshots: {}, videos: [] })),
    ]);

    // If run is still active, show live progress instead
    if (run.status === 'pending' || run.status === 'running') {
      watchRunLive(runId);
      return;
    }

    // Hide live progress container if visible
    const liveContainer = document.getElementById('live-progress-container');
    if (liveContainer) liveContainer.style.display = 'none';

    // ── Switch to FULL PAGE replay view (NOT a sidebar drawer) ──
    document.querySelectorAll('.page').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const replayPage = document.getElementById('page-replay');
    replayPage.style.display = 'block';

    document.getElementById('replay-title').textContent =
      'Run ' + runId.substring(0, 8) + '\u2026 \u2014 Execution Replay';

    // ── A. Summary cards ───────────────────────────────────────
    const dur = run.duration_ms ? (run.duration_ms / 1000).toFixed(1) + 's' : '\u2014';
    const started = run.started_at ? new Date(run.started_at).toLocaleString() : '\u2014';
    const passed = (run.results || []).filter(r => r.status === 'passed').length;
    const failedCount = (run.results || []).filter(r => r.status === 'failed' || r.status === 'error').length;
    const total = (run.results || []).length;

    document.getElementById('replay-summary').innerHTML =
      '<div class="rsummary-card"><div class="rsummary-label">Status</div><div class="rsummary-value"><span class="status-badge status-' + run.status + '">' + run.status + '</span></div></div>' +
      '<div class="rsummary-card"><div class="rsummary-label">Browser</div><div class="rsummary-value">' + esc(run.browser) + '</div></div>' +
      '<div class="rsummary-card"><div class="rsummary-label">Duration</div><div class="rsummary-value">' + dur + '</div></div>' +
      '<div class="rsummary-card"><div class="rsummary-label">Started</div><div class="rsummary-value" style="font-size:12px">' + started + '</div></div>' +
      '<div class="rsummary-card"><div class="rsummary-label">Test Cases</div><div class="rsummary-value">' + passed + '/' + total + ' passed</div></div>' +
      '<div class="rsummary-card"><div class="rsummary-label">Run ID</div><div class="rsummary-value" style="font-family:monospace;font-size:10px;word-break:break-all">' + runId + '</div></div>';

    // ── B. Action buttons ──────────────────────────────────────
    const hasVideo = artifacts.videos && artifacts.videos.length > 0;
    const hasTrace = artifacts.traces && artifacts.traces.length > 0;
    const hasScreenshots = artifacts.screenshots && Object.keys(artifacts.screenshots).length > 0;

    var actionsHtml = '';
    if (hasVideo) {
      actionsHtml += '<button class="btn btn-primary" onclick="document.getElementById(\'replay-video-section\').scrollIntoView({behavior:\'smooth\'})">' +
        '<span class="material-icons-outlined">videocam</span> Watch Recording</button>';
    }
    if (hasTrace) {
      artifacts.traces.forEach(function(t) {
        actionsHtml += '<a class="btn btn-outline" href="' + t.url + '" download style="text-decoration:none">' +
          '<span class="material-icons-outlined">folder_zip</span> Download Trace</a>';
      });
    }
    actionsHtml += '<a class="btn btn-outline" href="/api/runs/' + runId + '/report" target="_blank" style="text-decoration:none">' +
      '<span class="material-icons-outlined">summarize</span> View Report</a>';
    actionsHtml += '<a class="btn btn-outline" href="/api/runs/' + runId + '/report.xml" style="text-decoration:none">' +
      '<span class="material-icons-outlined">download</span> JUnit XML</a>';
    actionsHtml += '<button class="btn btn-outline" onclick="retryRun(\'' + runId + '\', \'' +
      (failedCount > 0 ? 'failed' : 'all') + '\')">' +
      '<span class="material-icons-outlined">replay</span> ' +
      (failedCount > 0 ? 'Retry Failed' : 'Retry All') + '</button>';
    if (hasScreenshots) {
      actionsHtml += '<button class="btn btn-outline" onclick="document.getElementById(\'replay-screenshots-section\').scrollIntoView({behavior:\'smooth\'})">' +
        '<span class="material-icons-outlined">photo_library</span> View Screenshots</button>';
    }
    document.getElementById('replay-actions').innerHTML = actionsHtml;

    // ── C. Video player ────────────────────────────────────────
    var videoSection = document.getElementById('replay-video-section');
    if (hasVideo) {
      var videoUrl = artifacts.videos[0].url;
      videoSection.style.display = 'block';
      document.getElementById('replay-video').src = videoUrl;
    } else {
      videoSection.style.display = 'none';
    }

    // ── D. Screenshot step-by-step replay ──────────────────────
    var ssSection = document.getElementById('replay-screenshots-section');
    var ssViewer = document.getElementById('replay-viewer');
    window._replayStates = {};

    if (hasScreenshots && run.results && run.results.length > 0) {
      ssSection.style.display = 'block';
      var viewerHtml = '';

      run.results.forEach(function(tc, tcIdx) {
        var tcId = tc.test_case_id || '';
        var tcScreenshots = (artifacts.screenshots[tcId] || []).slice();
        var steps = tc.step_results || [];
        if (tcScreenshots.length === 0 && steps.length === 0) return;

        tcScreenshots.sort(function(a, b) { return a.step_index - b.step_index; });
        var viewerId = 'rv' + tcIdx;
        var firstShot = tcScreenshots.length > 0 ? tcScreenshots[0] : null;
        var firstUrl = firstShot
          ? (firstShot.url || firstShot.failure_url || firstShot.diff_url || '')
          : '';

        // Store replay state
        window._replayStates[viewerId] = {
          current: 0,
          total: tcScreenshots.length,
          screenshots: tcScreenshots,
          steps: steps,
          autoplayTimer: null,
        };

        // Build step list
        var stepListHtml = '';
        steps.forEach(function(sr, si) {
          var isPassed = sr.status === 'passed';
          var isSkipped = sr.status === 'skipped';
          var icon = isPassed ? 'check_circle' : (isSkipped ? 'skip_next' : 'cancel');
          var iconColor = isPassed ? '#22c55e' : (isSkipped ? '#94a3b8' : '#dc2626');
          var hasSS = tcScreenshots.find(function(s) { return s.step_index === si; });
          stepListHtml += '<div class="rstep-item' + (si === 0 ? ' active' : '') + (hasSS ? '' : ' no-ss') + '"' +
            ' data-step="' + si + '" onclick="replayGoTo(\'' + viewerId + '\',' + si + ')">' +
            '<span class="material-icons-outlined" style="font-size:16px;color:' + iconColor + '">' + icon + '</span>' +
            '<span class="rstep-idx">' + si + '</span>' +
            '<span class="rstep-action">' + esc(sr.action || 'step') + '</span>' +
            '<span class="rstep-dur">' + (sr.duration_ms || 0) + 'ms</span>' +
            (sr.error ? '<div class="rstep-err"' + (isSkipped ? ' style="color:#94a3b8"' : '') + '>' + esc(sr.error) + '</div>' +
              (!isSkipped ? '<div class="rstep-fix-hint">' +
                '<span class="material-icons-outlined" style="font-size:14px">lightbulb</span> ' +
                _getFixHint(sr.error, sr.action) +
              '</div>' : '') : '') +
            '</div>';
        });

        viewerHtml +=
          '<div class="rtc-block">' +
          '<div class="rtc-header">' +
          '<span class="material-icons-outlined" style="font-size:18px;color:#60a5fa">science</span> ' +
          '<strong>' + esc(tc.test_case_name || 'Test Case') + '</strong> ' +
          '<span class="status-badge status-' + tc.status + '" style="margin-left:8px">' + tc.status + '</span>' +
          '<span style="margin-left:auto;color:#94a3b8;font-size:12px">' + (tc.duration_ms || 0) + 'ms \u00b7 ' + steps.length + ' steps</span>' +
          '</div>' +
          (tc.error ? '<div class="rtc-error"><span class="material-icons-outlined" style="font-size:16px">error</span> ' + esc(tc.error) + '</div>' : '') +
          '<div class="rtc-viewer">' +
            '<div class="rss-panel">' +
              '<div class="rss-nav-bar">' +
                '<button class="btn btn-sm btn-outline" onclick="replayPrev(\'' + viewerId + '\')"><span class="material-icons-outlined">chevron_left</span></button>' +
                '<span class="rss-counter" id="' + viewerId + '-counter">' + (tcScreenshots.length > 0 ? 'Step 0 \u00b7 1/' + tcScreenshots.length : 'No screenshots') + '</span>' +
                '<button class="btn btn-sm btn-outline" onclick="replayNext(\'' + viewerId + '\')"><span class="material-icons-outlined">chevron_right</span></button>' +
                '<button class="btn btn-sm btn-primary" id="' + viewerId + '-play" onclick="replayToggleAutoplay(\'' + viewerId + '\')" title="Auto-play"><span class="material-icons-outlined">play_arrow</span></button>' +
              '</div>' +
              '<div class="rss-img-wrap">' +
                (firstUrl
                  ? '<img id="' + viewerId + '-img" src="' + firstUrl + '" alt="Step 0" class="rss-img" />'
                  : '<div class="rss-no-img"><span class="material-icons-outlined" style="font-size:48px;color:#475569">photo_camera</span><p>No screenshots captured</p></div>'
                ) +
                '<div class="rss-img-actions" id="' + viewerId + '-img-actions"></div>' +
              '</div>' +
            '</div>' +
            '<div class="rstep-list" id="' + viewerId + '-steps">' +
              '<div class="rstep-list-hdr">Steps (' + steps.length + ')</div>' +
              '<div class="rstep-list-body">' +
                (stepListHtml || '<div style="padding:12px;color:#64748b;font-size:12px">No steps</div>') +
              '</div>' +
            '</div>' +
          '</div>' +
          '</div>';
      });

      ssViewer.innerHTML = viewerHtml;
      Object.keys(window._replayStates || {}).forEach(function(viewerId) {
        var replayState = window._replayStates[viewerId];
        if (replayState && replayState.total > 0) {
          replayGoTo(viewerId, replayState.screenshots[0].step_index);
        }
      });
    } else {
      ssSection.style.display = 'none';
    }

    // ── E. Test case results (compact list) ────────────────────
    var resultsDiv = document.getElementById('replay-results');
    if (run.results && run.results.length > 0) {
      resultsDiv.innerHTML = run.results.map(function(tc) {
        var stepsHtml = (tc.step_results || []).map(function(sr) {
          var isSkipped = sr.status === 'skipped';
          var icon = sr.status === 'passed' ? 'check_circle' : (isSkipped ? 'skip_next' : 'cancel');
          var iconClass = sr.status === 'passed' ? 'pass' : (isSkipped ? 'skip' : 'fail');
          return '<div class="result-step">' +
            '<span class="material-icons-outlined result-step-icon ' + iconClass + '">' + icon + '</span>' +
            '<span>Step ' + sr.step_index + ': ' + sr.action + '</span>' +
            '<span style="margin-left:auto;color:#9ca3af">' + sr.duration_ms + 'ms</span>' +
            (sr.error ? '<div style="color:#dc2626;font-size:11px;width:100%;margin-top:2px">' + esc(sr.error) + '</div>' +
              '<div class="rstep-fix-hint">' +
                '<span class="material-icons-outlined" style="font-size:14px">lightbulb</span> ' +
                _getFixHint(sr.error, sr.action) +
              '</div>' : '') +
            '</div>';
        }).join('');
        return '<div class="result-card">' +
          '<div class="result-card-header">' +
          '<span class="result-card-name">' + esc(tc.test_case_name) + '</span>' +
          '<span class="status-badge status-' + tc.status + '">' + tc.status + '</span>' +
          '</div>' +
          '<div class="result-card-dur">' + tc.duration_ms + 'ms</div>' +
          (tc.error ? '<div style="color:#dc2626;font-size:12px;margin:6px 0">' + esc(tc.error) + '</div>' : '') +
          stepsHtml +
          '</div>';
      }).join('');
    } else {
      resultsDiv.innerHTML = '<p style="color:#9ca3af;text-align:center;padding:24px">No results available yet.</p>';
    }

    // Scroll to top
    window.scrollTo(0, 0);

  } catch (e) {
    toast('Failed to load run details: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
// Replay Navigation Helpers
// ═══════════════════════════════════════════════════════════════════
function _replayImageActions(viewerId, ss, activeKind) {
  var buttons = [];
  function add(kind, url, label, icon) {
    buttons.push(
      '<button class="rss-img-btn' + (activeKind === kind ? ' active' : '') + '" ' +
      'onclick="replayShowImage(\'' + viewerId + '\', \'' + kind + '\')">' +
      '<span class="material-icons-outlined">' + icon + '</span>' + label + '</button>'
    );
  }
  if (ss.url) add('step', ss.url, 'Step', 'photo_camera');
  if (ss.failure_url) add('failure', ss.failure_url, 'Failure', 'error');
  if (ss.diff_url) add('diff', ss.diff_url, 'Diff', 'compare');
  return buttons.join('');
}

function replayShowImage(viewerId, kind) {
  var st = window._replayStates && window._replayStates[viewerId];
  if (!st || st.total === 0) return;
  var ss = st.screenshots[st.current];
  var url = kind === 'failure' ? ss.failure_url : (kind === 'diff' ? ss.diff_url : ss.url);
  if (!url) return;

  var img = document.getElementById(viewerId + '-img');
  if (img) { img.src = url; img.alt = 'Step ' + ss.step_index + ' ' + kind; }

  var actions = document.getElementById(viewerId + '-img-actions');
  if (actions) actions.innerHTML = _replayImageActions(viewerId, ss, kind);
}

function replayGoTo(viewerId, stepIndex) {
  var st = window._replayStates && window._replayStates[viewerId];
  if (!st || st.total === 0) return;

  var ssIdx = -1;
  for (var i = 0; i < st.screenshots.length; i++) {
    if (st.screenshots[i].step_index === stepIndex) { ssIdx = i; break; }
  }
  if (ssIdx < 0) return;

  st.current = ssIdx;
  var ss = st.screenshots[ssIdx];
  var step = (st.steps || []).find(function(s) { return s.step_index === stepIndex; });
  var activeKind = (step && step.status === 'failed' && ss.failure_url)
    ? 'failure'
    : (ss.url ? 'step' : (ss.failure_url ? 'failure' : 'diff'));
  var url = activeKind === 'failure' ? ss.failure_url : (activeKind === 'diff' ? ss.diff_url : ss.url);

  var img = document.getElementById(viewerId + '-img');
  if (img && url) { img.src = url; img.alt = 'Step ' + ss.step_index + ' ' + activeKind; }

  var actions = document.getElementById(viewerId + '-img-actions');
  if (actions) actions.innerHTML = _replayImageActions(viewerId, ss, activeKind);

  var counter = document.getElementById(viewerId + '-counter');
  if (counter) counter.textContent = 'Step ' + ss.step_index + ' \u00b7 ' + (ssIdx + 1) + '/' + st.total;

  var stepsContainer = document.getElementById(viewerId + '-steps');
  if (stepsContainer) {
    stepsContainer.querySelectorAll('.rstep-item').forEach(function(el) {
      el.classList.toggle('active', parseInt(el.dataset.step) === stepIndex);
    });
    var activeEl = stepsContainer.querySelector('.rstep-item.active');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
}

function replayPrev(viewerId) {
  var st = window._replayStates && window._replayStates[viewerId];
  if (!st || st.total === 0) return;
  var prevIdx = Math.max(0, st.current - 1);
  replayGoTo(viewerId, st.screenshots[prevIdx].step_index);
}

function replayNext(viewerId) {
  var st = window._replayStates && window._replayStates[viewerId];
  if (!st || st.total === 0) return;
  var nextIdx = Math.min(st.total - 1, st.current + 1);
  replayGoTo(viewerId, st.screenshots[nextIdx].step_index);
}

function replayToggleAutoplay(viewerId) {
  var st = window._replayStates && window._replayStates[viewerId];
  if (!st || st.total === 0) return;
  var btn = document.getElementById(viewerId + '-play');

  if (st.autoplayTimer) {
    clearInterval(st.autoplayTimer);
    st.autoplayTimer = null;
    if (btn) btn.innerHTML = '<span class="material-icons-outlined">play_arrow</span>';
  } else {
    if (btn) btn.innerHTML = '<span class="material-icons-outlined">pause</span>';
    st.autoplayTimer = setInterval(function() {
      var nextIdx = st.current + 1;
      if (nextIdx >= st.total) {
        clearInterval(st.autoplayTimer);
        st.autoplayTimer = null;
        if (btn) btn.innerHTML = '<span class="material-icons-outlined">play_arrow</span>';
        return;
      }
      replayGoTo(viewerId, st.screenshots[nextIdx].step_index);
    }, 1500);
  }
}

function closeDrawer() {
  document.getElementById('drawer-overlay').classList.remove('show');
}

async function deleteRun(id) {
  if (!confirm('Delete this run and its artifacts?')) return;
  try {
    await api.deleteRun(id);
    toast('Run deleted', 'success');
    await loadRuns();
  } catch (e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
// Code Export
// ═══════════════════════════════════════════════════════════════════
async function loadCodegenTests() {
  try {
    const allTests = await api.getTests();
    const sel = document.getElementById('codegen-test');
    sel.innerHTML = '<option value="">— Select a test case —</option>' +
      allTests.map(t => '<option value="' + t.id + '">' + esc(t.name) + '</option>').join('');
  } catch (e) {
    toast('Failed to load tests: ' + e.message, 'error');
  }
}

async function previewCode() {
  const testId = document.getElementById('codegen-test').value;
  if (!testId) {
    document.getElementById('code-preview').style.display = 'none';
    return;
  }
  try {
    const result = await api.exportTest(testId);
    document.getElementById('code-preview').style.display = 'block';
    document.getElementById('code-filename').textContent = result.filename;
    document.getElementById('code-content').textContent = result.code;
  } catch (e) {
    toast('Export failed: ' + e.message, 'error');
  }
}

async function exportTestById(id) {
  if (state.ctxMenuEl) { state.ctxMenuEl.remove(); state.ctxMenuEl = null; }
  try {
    const result = await api.exportTest(id);
    document.getElementById('code-preview').style.display = 'block';
    document.getElementById('code-filename').textContent = result.filename;
    document.getElementById('code-content').textContent = result.code;
    navigate('codegen');
  } catch (e) {
    toast('Export failed: ' + e.message, 'error');
  }
}

async function exportSelectedTest() {
  if (state.selectedTestId) await exportTestById(state.selectedTestId);
}

function copyCode() {
  const code = document.getElementById('code-content').textContent;
  navigator.clipboard.writeText(code).then(() => toast('Code copied!', 'success'));
}

function downloadCode() {
  const code = document.getElementById('code-content').textContent;
  const filename = document.getElementById('code-filename').textContent;
  const blob = new Blob([code], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ═══════════════════════════════════════════════════════════════════
// Auth Profiles
// ═══════════════════════════════════════════════════════════════════
async function loadAuthProfiles() {
  try {
    state.authProfiles = await api.getAuthProfiles();
    renderAuthProfiles();
  } catch (e) {
    toast('Failed to load auth profiles: ' + e.message, 'error');
  }
}

function renderAuthProfiles() {
  const tbody = document.getElementById('auth-tbody');
  const emptyEl = document.getElementById('auth-empty');

  if (state.authProfiles.length === 0) {
    tbody.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  tbody.innerHTML = state.authProfiles.map(p => {
    const proj = state.projects.find(pr => pr.id === p.project_id);
    return '<tr>' +
      '<td style="font-weight:600">' + esc(p.name) + '</td>' +
      '<td>' + (proj ? esc(proj.name) : p.project_id.substring(0, 8) + '\u2026') + '</td>' +
      '<td style="color:#6b7280">' + esc(p.description || '\u2014') + '</td>' +
      '<td>' + (p.has_storage_state
        ? '<span class="status-badge status-passed">Saved</span>'
        : '<span class="status-badge status-pending">None</span>') + '</td>' +
      '<td style="font-size:12px">' + new Date(p.created_at).toLocaleDateString() + '</td>' +
      '<td>' +
        '<button class="icon-btn" onclick="importAuthState(\'' + p.id + '\')" title="' +
          (p.has_storage_state ? 'Replace state' : 'Import state') + '">' +
          '<span class="material-icons-outlined" style="font-size:18px">upload_file</span></button>' +
        '<button class="icon-btn" onclick="deleteAuthProfile(\'' + p.id + '\', \'' + esc(p.name) + '\')" title="Delete">' +
          '<span class="material-icons-outlined" style="font-size:18px">delete</span></button>' +
      '</td>' +
      '</tr>';
  }).join('');
}

function importAuthState(id) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json,application/json';
  input.onchange = async () => {
    const file = input.files && input.files[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      await api.updateAuthProfile(id, { storage_state: parsed });
      toast('Auth state imported', 'success');
      await loadAuthProfiles();
    } catch (e) {
      toast('Import failed: ' + e.message, 'error');
    }
  };
  input.click();
}

async function deleteAuthProfile(id, name) {
  if (!confirm('Delete auth profile "' + name + '"?')) return;
  try {
    await api.deleteAuthProfile(id);
    toast('Profile deleted', 'success');
    await loadAuthProfiles();
  } catch (e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
// View Test Detail (in Drawer — still uses drawer, it's compact)
// ═══════════════════════════════════════════════════════════════════
async function viewTestDetail(id) {
  if (state.ctxMenuEl) { state.ctxMenuEl.remove(); state.ctxMenuEl = null; }
  try {
    const t = await api.getTest(id);
    state._editingTest = t;

    // Switch to full-page test detail view
    document.querySelectorAll('.page').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.getElementById('page-testdetail').style.display = 'block';

    // Title
    document.getElementById('td-title').textContent = t.name;

    // Header actions
    document.getElementById('td-header-actions').innerHTML =
      '<button class="btn btn-outline" onclick="exportTestById(\'' + id + '\')">' +
        '<span class="material-icons-outlined">code</span> Export Code' +
      '</button>';

    // Info cards
    document.getElementById('td-info').innerHTML =
      '<div class="rsummary-card"><div class="rsummary-label">Description</div><div class="rsummary-value">' + esc(t.description || 'No description') + '</div></div>' +
      '<div class="rsummary-card"><div class="rsummary-label">Steps</div><div class="rsummary-value">' + (t.steps || []).length + '</div></div>' +
      '<div class="rsummary-card"><div class="rsummary-label">Assertions</div><div class="rsummary-value">' + (t.assertions || []).length + '</div></div>' +
      (t.device_config && t.device_config.device_name ? '<div class="rsummary-card"><div class="rsummary-label">Device</div><div class="rsummary-value">' + esc(t.device_config.device_name) + '</div></div>' : '');

    // Steps count
    document.getElementById('td-steps-count').textContent = (t.steps || []).length + ' steps';

    // Steps table
    _renderStepsTable(t);

    // Assertions
    var assertSec = document.getElementById('td-assertions-section');
    if (t.assertions && t.assertions.length > 0) {
      assertSec.style.display = 'block';
      document.getElementById('td-assertions-body').innerHTML = t.assertions.map(function(a, i) {
        return '<div class="td-assert-row">' +
          '<span class="td-assert-num">' + (i + 1) + '</span>' +
          '<span class="td-assert-type">' + esc(a.assertion_type) + '</span>' +
          '<span class="td-assert-sel">' + esc(a.selector || '') + '</span>' +
          (a.expected_value ? '<span class="td-assert-val">' + esc(a.expected_value) + '</span>' : '') +
        '</div>';
      }).join('');
    } else {
      assertSec.style.display = 'none';
    }

    window.scrollTo(0, 0);
  } catch (e) {
    toast('Failed to load test: ' + e.message, 'error');
  }
}

function _renderStepsTable(t) {
  var tbody = document.getElementById('td-steps-tbody');
  var emptyEl = document.getElementById('td-steps-empty');
  var steps = t.steps || [];

  if (steps.length === 0) {
    tbody.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  tbody.innerHTML = steps.map(function(s, i) {
    var actionClass = 'td-action-' + (s.action || 'default');
    var target = s.action === 'navigate' ? (s.url || '') : (s.selector || s.key || '');
    var val = s.value || '';

    return '<tr id="td-step-row-' + i + '">' +
      '<td class="td-step-num">' + (i + 1) + '</td>' +
      '<td><span class="td-action-badge ' + actionClass + '">' + (s.action || '').toUpperCase() + '</span></td>' +
      '<td class="td-step-target" title="' + esc(target).replace(/"/g, '&quot;') + '">' + esc(target) + '</td>' +
      '<td class="td-step-value">' + (val ? '"' + esc(val) + '"' : '<span style="color:#cbd5e1">—</span>') + '</td>' +
      '<td class="td-step-actions">' +
        '<button class="icon-btn" onclick="editStepInline(\'' + t.id + '\',' + i + ')" title="Edit">' +
          '<span class="material-icons-outlined" style="font-size:16px">edit</span>' +
        '</button>' +
        '<button class="icon-btn" onclick="deleteStepInline(\'' + t.id + '\',' + i + ')" title="Delete">' +
          '<span class="material-icons-outlined" style="font-size:16px;color:#dc2626">delete</span>' +
        '</button>' +
      '</td>' +
    '</tr>';
  }).join('');
}

function editStepInline(testId, stepIndex) {
  var t = state._editingTest;
  if (!t || !t.steps || !t.steps[stepIndex]) return;
  var step = t.steps[stepIndex];

  var row = document.getElementById('td-step-row-' + stepIndex);
  if (!row) return;

  var targetVal = step.action === 'navigate' ? (step.url || '') : (step.selector || '');
  var valueVal = step.value !== undefined && step.value !== null ? step.value : '';
  var hasValue = step.value !== undefined && step.value !== null;

  row.innerHTML =
    '<td class="td-step-num">' + (stepIndex + 1) + '</td>' +
    '<td><span class="td-action-badge td-action-' + step.action + '">' + (step.action || '').toUpperCase() + '</span></td>' +
    '<td colspan="' + (hasValue ? '1' : '2') + '">' +
      '<input type="text" class="form-input td-edit-input" id="td-edit-sel-' + stepIndex + '" value="' + esc(targetVal).replace(/"/g, '&quot;') + '">' +
    '</td>' +
    (hasValue ? '<td><input type="text" class="form-input td-edit-input" id="td-edit-val-' + stepIndex + '" value="' + esc(valueVal).replace(/"/g, '&quot;') + '"></td>' : '') +
    '<td class="td-step-actions">' +
      '<button class="icon-btn" onclick="saveStepInline(\'' + testId + '\',' + stepIndex + ')" title="Save">' +
        '<span class="material-icons-outlined" style="font-size:16px;color:#22c55e">check</span>' +
      '</button>' +
      '<button class="icon-btn" onclick="_renderStepsTable(state._editingTest)" title="Cancel">' +
        '<span class="material-icons-outlined" style="font-size:16px;color:#6b7280">close</span>' +
      '</button>' +
    '</td>';

  // Focus the selector input
  var inp = document.getElementById('td-edit-sel-' + stepIndex);
  if (inp) { inp.focus(); inp.select(); }
}

async function saveStepInline(testId, stepIndex) {
  var t = state._editingTest;
  if (!t || !t.steps) return;

  var selInput = document.getElementById('td-edit-sel-' + stepIndex);
  var valInput = document.getElementById('td-edit-val-' + stepIndex);

  if (selInput) {
    var newVal = selInput.value.trim();
    if (t.steps[stepIndex].action === 'navigate') {
      t.steps[stepIndex].url = newVal;
    } else {
      t.steps[stepIndex].selector = newVal;
    }
  }
  if (valInput) {
    t.steps[stepIndex].value = valInput.value;
  }

  try {
    await api.updateTest(testId, { steps: t.steps });
    toast('Step updated', 'success');
    viewTestDetail(testId);
  } catch (e) {
    toast('Failed to save: ' + e.message, 'error');
  }
}

async function deleteStepInline(testId, stepIndex) {
  var t = state._editingTest;
  if (!t || !t.steps) return;
  if (!confirm('Delete step ' + (stepIndex + 1) + ' (' + t.steps[stepIndex].action + ')?')) return;

  t.steps.splice(stepIndex, 1);
  try {
    await api.updateTest(testId, { steps: t.steps });
    toast('Step deleted', 'success');
    viewTestDetail(testId);
  } catch (e) {
    toast('Failed to delete: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
// Search / Filter
// ═══════════════════════════════════════════════════════════════════
function toggleSearch(panel) {
  const el = document.getElementById('search-' + panel);
  if (el.style.display === 'none') {
    el.style.display = 'block';
    el.querySelector('input').focus();
  } else {
    el.style.display = 'none';
    el.querySelector('input').value = '';
  }
}

function filterList(type, query) {
  const q = query.toLowerCase();
  if (type === 'projects') {
    document.querySelectorAll('#projects-list .list-item').forEach(el => {
      el.style.display = el.querySelector('.list-item-name').textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  } else if (type === 'suites') {
    document.querySelectorAll('#suites-list .list-item').forEach(el => {
      el.style.display = el.querySelector('.list-item-name').textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  }
}

// ═══════════════════════════════════════════════════════════════════
// Error Fix Hints
// ═══════════════════════════════════════════════════════════════════
function _getFixHint(error, action) {
  if (!error) return '';
  const e = error.toLowerCase();

  if (e.includes('timeout') && e.includes('waiting for locator')) {
    const selectorMatch = error.match(/locator\("([^"]+)"\)/);
    const sel = selectorMatch ? selectorMatch[1] : '';
    return '<b>Fix:</b> The element <code>' + esc(sel) + '</code> was not found within the timeout. ' +
      '<br>Open the test case details and click the edit icon on this step to update the selector. ' +
      '<br>Or re-record the test to capture the correct selectors. ' +
      '<br>The page may have changed since recording, or a previous step navigated elsewhere.';
  }
  if (e.includes('unknown engine')) {
    return '<b>Fix:</b> The selector uses an unsupported format. ' +
      'Edit this step and use a CSS selector (#id, .class), [data-testid="x"], or role=button[name="x"].';
  }
  if (e.includes('target closed') || e.includes('target page') || e.includes('page closed')) {
    return '<b>Fix:</b> The page was closed or navigated away before this step could execute. ' +
      'A previous step may have triggered an unexpected navigation or popup.';
  }
  if (e.includes('strict mode violation') || (e.includes('resolved to') && e.includes('elements'))) {
    return '<b>Fix:</b> The selector matches multiple elements. Make it more specific using ' +
      '[data-testid], nth= or :has-text() to target the exact element.';
  }
  if (e.includes('detached')) {
    return '<b>Fix:</b> The element was removed from the page before the action completed. ' +
      'Try adding a wait step before this action, or the page may still be loading.';
  }
  if (action === 'navigate' && (e.includes('err_') || e.includes('net::') || e.includes('failed to'))) {
    return '<b>Fix:</b> The URL could not be loaded. Check that the target website is accessible ' +
      'and the URL is correct.';
  }
  return '<b>Tip:</b> Open the test case details to edit this step selector, or re-record the test.';
}

// ═══════════════════════════════════════════════════════════════════
// Toast Notifications
// ═══════════════════════════════════════════════════════════════════
function toast(message, type) {
  type = type || 'info';
  const container = document.getElementById('toast-container');
  const icon = { success: 'check_circle', error: 'error', info: 'info' }[type] || 'info';
  const div = document.createElement('div');
  div.className = 'toast toast-' + type;
  div.innerHTML = '<span class="material-icons-outlined" style="font-size:18px">' + icon + '</span> ' + esc(message);
  container.appendChild(div);
  setTimeout(function() { div.style.opacity = '0'; div.style.transform = 'translateX(40px)'; setTimeout(function() { div.remove(); }, 300); }, 4000);
}

// ═══════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════
function esc(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}
