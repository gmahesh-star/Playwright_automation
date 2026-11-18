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
async function loadRuns() {
  try {
    const filter = document.getElementById('runs-filter-status')?.value || '';
    state.runs = await api.getRuns(filter || undefined);
    renderRuns();
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
          <button class="icon-btn" onclick="deleteRun('${r.id}')" title="Delete">
            <span class="material-icons-outlined" style="font-size:18px">delete</span>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function runSelectedSuite() {
  if (!state.selectedSuiteId) return;
  try {
    const run = await api.createRun({ suite_id: state.selectedSuiteId, browser: 'chromium' });
    toast(`Run queued: ${run.id.substring(0, 8)}…`, 'success');
    navigate('runs');
  } catch (e) {
    toast('Failed to trigger run: ' + e.message, 'error');
  }
}

async function runSuiteById(suiteId) {
  if (state.ctxMenuEl) { state.ctxMenuEl.remove(); state.ctxMenuEl = null; }
  try {
    const run = await api.createRun({ suite_id: suiteId, browser: 'chromium' });
    toast(`Run queued: ${run.id.substring(0, 8)}…`, 'success');
    navigate('runs');
  } catch (e) {
    toast('Failed to trigger run: ' + e.message, 'error');
  }
}

async function viewRunDetail(runId) {
  try {
    const run = await api.getRun(runId);
    // Fetch artifacts (screenshots, video, trace) — non-blocking if endpoint not ready
    let artifacts = null;
    try { artifacts = await api.getRunArtifacts(runId); } catch (_) { /* endpoint may not exist yet */ }

    const overlay = document.getElementById('drawer-overlay');
    const title = document.getElementById('drawer-title');
    const body = document.getElementById('drawer-body');

    // Widen drawer for replay view
    const drawerEl = overlay.querySelector('.drawer');
    if (drawerEl) drawerEl.classList.add('drawer-replay');

    title.innerHTML = `<span class="material-icons-outlined" style="font-size:20px;vertical-align:middle;margin-right:6px;color:#3b82f6">play_circle</span>Run ${runId.substring(0, 8)}… — Execution Replay`;

    const statusClass = `status-${run.status}`;
    const dur = run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '—';

    // ── A. Run Summary Header ───────────────────────────────────
    const summaryHtml = `
      <div class="replay-summary">
        <div class="replay-summary-row">
          <div><span style="color:#94a3b8">Status</span><br><span class="status-badge ${statusClass}">${run.status}</span></div>
          <div><span style="color:#94a3b8">Browser</span><br><strong style="color:#e2e8f0">${esc(run.browser)}</strong></div>
          <div><span style="color:#94a3b8">Duration</span><br><strong style="color:#e2e8f0">${dur}</strong></div>
          ${run.trigger_source ? `<div><span style="color:#94a3b8">Source</span><br><strong style="color:#e2e8f0">${esc(run.trigger_source)}</strong></div>` : ''}
          <div><span style="color:#94a3b8">Run ID</span><br><span style="color:#cbd5e1;font-family:monospace;font-size:11px">${runId}</span></div>
        </div>
      </div>`;

    // ── B. Artifact Action Buttons ──────────────────────────────
    const hasVideo = artifacts && artifacts.videos && artifacts.videos.length > 0;
    const hasTrace = artifacts && artifacts.traces && artifacts.traces.length > 0;
    const hasScreenshots = artifacts && artifacts.screenshots && Object.keys(artifacts.screenshots).length > 0;

    let actionButtonsHtml = `<div class="replay-actions">`;
    if (hasVideo) {
      actionButtonsHtml += `<button class="btn btn-outline replay-action-btn" onclick="document.getElementById('replay-video-section-${runId}').scrollIntoView({behavior:'smooth'})">
        <span class="material-icons-outlined">movie</span> Watch Video
      </button>`;
    }
    if (hasTrace) {
      const traceUrl = artifacts.traces[0].url || `${API_BASE}/runs/${runId}/trace/${artifacts.traces[0].test_case_id}`;
      actionButtonsHtml += `<a class="btn btn-outline replay-action-btn" href="${traceUrl}" download>
        <span class="material-icons-outlined">folder_zip</span> Download Trace
      </a>`;
    }
    actionButtonsHtml += `<a class="btn btn-outline replay-action-btn" href="${API_BASE}/runs/${runId}/report" target="_blank" download>
      <span class="material-icons-outlined">assessment</span> View Report
    </a>`;
    actionButtonsHtml += `</div>`;

    // ── C. Visual Step Replay (per test case) ───────────────────
    let replayHtml = '';
    if (run.results && run.results.length > 0) {
      replayHtml = run.results.map((tc, tcIdx) => {
        const tcStatus = `status-${tc.status}`;
        const steps = tc.step_results || [];
        const tcId = tc.test_case_id || tc.test_id || '';
        const viewerId = `replay-viewer-${tcIdx}`;

        // Check if this test case has screenshots
        const tcHasScreenshots = hasScreenshots && artifacts.screenshots[tcId];
        const screenshotCount = tcHasScreenshots ? artifacts.screenshots[tcId].count : steps.length;

        // Step list items
        const stepListHtml = steps.map((sr, si) => {
          const icon = sr.status === 'passed' ? 'check_circle' : 'cancel';
          const iconColor = sr.status === 'passed' ? '#22c55e' : '#dc2626';
          return `<div class="replay-step-item ${si === 0 ? 'active' : ''}" data-viewer="${viewerId}" data-step="${si}" onclick="replaySelectStep('${viewerId}', ${si}, '${runId}', '${tcId}', ${screenshotCount})">
            <span class="material-icons-outlined" style="font-size:16px;color:${iconColor}">${icon}</span>
            <span class="replay-step-index">${si}</span>
            <span class="replay-step-action">${esc(sr.action || 'step')}</span>
            <span class="replay-step-dur">${sr.duration_ms || 0}ms</span>
          </div>`;
        }).join('');

        // Error display
        const errorHtml = tc.error ? `<div class="replay-error"><span class="material-icons-outlined" style="font-size:16px">error</span> ${esc(tc.error)}</div>` : '';

        return `<div class="replay-testcase">
          <div class="replay-tc-header">
            <div class="replay-tc-title">
              <span class="material-icons-outlined" style="font-size:18px;color:#60a5fa">science</span>
              <span>${esc(tc.test_case_name || 'Test Case')}</span>
              <span class="status-badge ${tcStatus}" style="margin-left:8px">${tc.status}</span>
            </div>
            <span class="replay-tc-dur">${tc.duration_ms || 0}ms</span>
          </div>
          ${errorHtml}
          <div class="replay-viewer-container" id="${viewerId}-container">
            <!-- Screenshot Display -->
            <div class="replay-screenshot-panel">
              <div class="replay-screenshot-frame" id="${viewerId}-frame">
                ${tcHasScreenshots
                  ? `<img id="${viewerId}-img" src="${API_BASE}/runs/${runId}/screenshots/${tcId}/step/0" alt="Step 0 screenshot" class="replay-screenshot-img" />`
                  : `<div class="replay-no-screenshots"><span class="material-icons-outlined" style="font-size:48px;color:#475569">photo_camera</span><p>No screenshots available</p></div>`
                }
              </div>
              <!-- Navigation Controls -->
              <div class="replay-nav-controls">
                <button class="btn btn-sm btn-outline replay-nav-btn" onclick="replayPrev('${viewerId}', '${runId}', '${tcId}', ${screenshotCount})" title="Previous Step">
                  <span class="material-icons-outlined">chevron_left</span>
                </button>
                <span class="replay-step-counter" id="${viewerId}-counter">Step 0 / ${screenshotCount - 1}</span>
                <button class="btn btn-sm btn-outline replay-nav-btn" onclick="replayNext('${viewerId}', '${runId}', '${tcId}', ${screenshotCount})" title="Next Step">
                  <span class="material-icons-outlined">chevron_right</span>
                </button>
                <button class="btn btn-sm btn-outline replay-nav-btn replay-autoplay-btn" id="${viewerId}-autoplay" onclick="replayToggleAutoplay('${viewerId}', '${runId}', '${tcId}', ${screenshotCount})" title="Auto-play">
                  <span class="material-icons-outlined">play_arrow</span>
                </button>
              </div>
            </div>
            <!-- Step List Sidebar -->
            <div class="replay-step-list">
              <div class="replay-step-list-header">Steps (${steps.length})</div>
              <div class="replay-step-list-body" id="${viewerId}-steps">
                ${stepListHtml || '<div style="padding:12px;color:#64748b;font-size:12px">No steps recorded</div>'}
              </div>
            </div>
          </div>
        </div>`;
      }).join('');
    } else {
      replayHtml = '<div class="replay-empty"><span class="material-icons-outlined" style="font-size:40px;color:#475569">hourglass_empty</span><p>No results available yet.</p></div>';
    }

    // ── D. Video Player Section ─────────────────────────────────
    let videoHtml = '';
    if (hasVideo) {
      const videoUrl = artifacts.videos[0].url || `${API_BASE}/runs/${runId}/video/${artifacts.videos[0].filename}`;
      videoHtml = `
        <div class="replay-section" id="replay-video-section-${runId}">
          <div class="replay-section-title">
            <span class="material-icons-outlined" style="color:#60a5fa">videocam</span>
            Video Recording
          </div>
          <div class="replay-video-wrapper">
            <video class="replay-video-player" controls preload="metadata">
              <source src="${videoUrl}" type="video/webm">
              Your browser does not support the video tag.
            </video>
          </div>
        </div>`;
    }

    // ── Assemble ────────────────────────────────────────────────
    body.innerHTML = `
      ${summaryHtml}
      ${actionButtonsHtml}
      <div class="replay-section">
        <div class="replay-section-title">
          <span class="material-icons-outlined" style="color:#60a5fa">camera_alt</span>
          Execution Replay
        </div>
        ${replayHtml}
      </div>
      ${videoHtml}
    `;

    overlay.classList.add('show');
  } catch (e) {
    toast('Failed to load run: ' + e.message, 'error');
  }
}

// ── Replay Navigation Helpers ──────────────────────────────────────
const _replayState = {};

function _getReplayState(viewerId) {
  if (!_replayState[viewerId]) _replayState[viewerId] = { currentStep: 0, autoplayTimer: null };
  return _replayState[viewerId];
}

function replaySelectStep(viewerId, stepIndex, runId, tcId, totalSteps) {
  const rs = _getReplayState(viewerId);
  rs.currentStep = stepIndex;
  // Update image
  const img = document.getElementById(`${viewerId}-img`);
  if (img) {
    img.src = `${API_BASE}/runs/${runId}/screenshots/${tcId}/step/${stepIndex}`;
    img.alt = `Step ${stepIndex} screenshot`;
  }
  // Update counter
  const counter = document.getElementById(`${viewerId}-counter`);
  if (counter) counter.textContent = `Step ${stepIndex} / ${totalSteps - 1}`;
  // Update active step in list
  const stepsContainer = document.getElementById(`${viewerId}-steps`);
  if (stepsContainer) {
    stepsContainer.querySelectorAll('.replay-step-item').forEach(el => {
      el.classList.toggle('active', parseInt(el.dataset.step) === stepIndex);
    });
    // Scroll active step into view
    const activeEl = stepsContainer.querySelector('.replay-step-item.active');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
}

function replayNext(viewerId, runId, tcId, totalSteps) {
  const rs = _getReplayState(viewerId);
  if (rs.currentStep < totalSteps - 1) {
    replaySelectStep(viewerId, rs.currentStep + 1, runId, tcId, totalSteps);
  }
}

function replayPrev(viewerId, runId, tcId, totalSteps) {
  const rs = _getReplayState(viewerId);
  if (rs.currentStep > 0) {
    replaySelectStep(viewerId, rs.currentStep - 1, runId, tcId, totalSteps);
  }
}

function replayToggleAutoplay(viewerId, runId, tcId, totalSteps) {
  const rs = _getReplayState(viewerId);
  const btn = document.getElementById(`${viewerId}-autoplay`);
  if (rs.autoplayTimer) {
    // Stop
    clearInterval(rs.autoplayTimer);
    rs.autoplayTimer = null;
    if (btn) btn.innerHTML = '<span class="material-icons-outlined">play_arrow</span>';
    if (btn) btn.classList.remove('autoplay-active');
  } else {
    // Start
    if (btn) btn.innerHTML = '<span class="material-icons-outlined">pause</span>';
    if (btn) btn.classList.add('autoplay-active');
    rs.autoplayTimer = setInterval(() => {
      if (rs.currentStep < totalSteps - 1) {
        replaySelectStep(viewerId, rs.currentStep + 1, runId, tcId, totalSteps);
      } else {
        // Loop back to start
        replaySelectStep(viewerId, 0, runId, tcId, totalSteps);
      }
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
    // Load all tests from all suites in all projects
    const allTests = await api.getTests();
    const sel = document.getElementById('codegen-test');
    sel.innerHTML = '<option value="">— Select a test case —</option>' +
      allTests.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join('');
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
    return `
      <tr>
        <td style="font-weight:600">${esc(p.name)}</td>
        <td>${proj ? esc(proj.name) : p.project_id.substring(0, 8) + '…'}</td>
        <td style="color:#6b7280">${esc(p.description || '—')}</td>
        <td style="font-family:monospace;font-size:11px">${p.storage_state_path || '—'}</td>
        <td style="font-size:12px">${new Date(p.created_at).toLocaleDateString()}</td>
        <td>
          <button class="icon-btn" onclick="deleteAuthProfile('${p.id}', '${esc(p.name)}')" title="Delete">
            <span class="material-icons-outlined" style="font-size:18px">delete</span>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function deleteAuthProfile(id, name) {
  if (!confirm(`Delete auth profile "${name}"?`)) return;
  try {
    await api.deleteAuthProfile(id);
    toast('Profile deleted', 'success');
    await loadAuthProfiles();
  } catch (e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
// View Test Detail (in Drawer)
// ═══════════════════════════════════════════════════════════════════
async function viewTestDetail(id) {
  if (state.ctxMenuEl) { state.ctxMenuEl.remove(); state.ctxMenuEl = null; }
  try {
    const t = await api.getTest(id);
    const overlay = document.getElementById('drawer-overlay');
    const title = document.getElementById('drawer-title');
    const body = document.getElementById('drawer-body');

    title.textContent = t.name;

    const stepsHtml = (t.steps || []).map((s, i) => `
      <div class="step-entry">
        <span class="step-num">${i + 1}</span>
        <span class="step-action step-action-${s.action === 'selectOption' ? 'select' : (s.action || 'default')}">${s.action}</span>
        <span class="step-detail">${esc(s.url || s.selector || s.key || '')}${s.value ? ' → "' + esc(s.value) + '"' : ''}</span>
      </div>
    `).join('');

    const assertHtml = (t.assertions || []).map((a, i) => `
      <div class="step-entry">
        <span class="step-num">A${i + 1}</span>
        <span class="step-action step-action-default">${a.assertion_type}</span>
        <span class="step-detail">${esc(a.selector || '')} ${a.expected_value ? '= "' + esc(a.expected_value) + '"' : ''}</span>
      </div>
    `).join('');

    body.innerHTML = `
      <div class="drawer-section">
        <p style="color:#6b7280;margin-bottom:12px">${esc(t.description || 'No description')}</p>
        ${t.device_config ? `<div style="font-size:12px;color:#6b7280;margin-bottom:8px">Device: ${JSON.stringify(t.device_config)}</div>` : ''}
      </div>
      <div class="drawer-section">
        <h3>Steps (${(t.steps || []).length})</h3>
        ${stepsHtml || '<p style="color:#9ca3af">No steps defined</p>'}
      </div>
      ${assertHtml ? `<div class="drawer-section"><h3>Assertions (${(t.assertions || []).length})</h3>${assertHtml}</div>` : ''}
      ${(t.mock_rules || []).length ? `<div class="drawer-section"><h3>Mock Rules</h3><pre style="font-size:11px;background:#f8fafc;padding:10px;border-radius:6px;overflow:auto">${esc(JSON.stringify(t.mock_rules, null, 2))}</pre></div>` : ''}
    `;
    overlay.classList.add('show');
  } catch (e) {
    toast('Failed to load test: ' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
// Search / Filter
// ═══════════════════════════════════════════════════════════════════
function toggleSearch(panel) {
  const el = document.getElementById(`search-${panel}`);
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
    const items = document.querySelectorAll('#projects-list .list-item');
    items.forEach(el => {
      const name = el.querySelector('.list-item-name').textContent.toLowerCase();
      el.style.display = name.includes(q) ? '' : 'none';
    });
  } else if (type === 'suites') {
    const items = document.querySelectorAll('#suites-list .list-item');
    items.forEach(el => {
      const name = el.querySelector('.list-item-name').textContent.toLowerCase();
      el.style.display = name.includes(q) ? '' : 'none';
    });
  }
}

// ═══════════════════════════════════════════════════════════════════
// Toast Notifications
// ═══════════════════════════════════════════════════════════════════
function toast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const icon = { success: 'check_circle', error: 'error', info: 'info' }[type] || 'info';
  const div = document.createElement('div');
  div.className = `toast toast-${type}`;
  div.innerHTML = `<span class="material-icons-outlined" style="font-size:18px">${icon}</span> ${esc(message)}`;
  container.appendChild(div);
  setTimeout(() => { div.style.opacity = '0'; div.style.transform = 'translateX(40px)'; setTimeout(() => div.remove(), 300); }, 4000);
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
