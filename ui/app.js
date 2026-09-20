/**
 * AgenticAutomation Dashboard — Frontend Logic
 *
 * Client-side SPA with hash routing:
 *   #/             → Workflow list view
 *   #/workflow/{id} → Workflow detail + pipeline view
 */

const API_BASE = '/api';
const REFRESH_INTERVAL = 10; // seconds

// --- State ---

let currentView = 'list';
let refreshTimerValue = REFRESH_INTERVAL;
let refreshIntervalId = null;
let selectedFile = null;

// --- DOM References ---

const $listView = document.getElementById('listView');
const $detailView = document.getElementById('detailView');
const $workflowTableBody = document.getElementById('workflowTableBody');
const $workflowCount = document.getElementById('workflowCount');
const $refreshTimer = document.getElementById('refreshTimer');
const $emptyState = document.getElementById('emptyState');
const $workflowTable = document.getElementById('workflowTable');

const $detailHeader = document.getElementById('detailHeader');
const $pipeline = document.getElementById('pipeline');
const $extractedSection = document.getElementById('extractedSection');
const $extractedBody = document.getElementById('extractedBody');
const $extractedJson = document.getElementById('extractedJson');
const $toggleExtractedBtn = document.getElementById('toggleExtractedBtn');

const $themeToggleBtn = document.getElementById('themeToggleBtn');
const $triggerBtn = document.getElementById('triggerBtn');
const $triggerModal = document.getElementById('triggerModal');
const $closeModalBtn = document.getElementById('closeModalBtn');
const $fileCards = document.querySelectorAll('.file-card');
const $customPath = document.getElementById('customPath');
const $submitTriggerBtn = document.getElementById('submitTriggerBtn');
const $triggerStatus = document.getElementById('triggerStatus');
const $backBtn = document.getElementById('backBtn');

const $toastContainer = document.getElementById('toastContainer');

// --- Utilities ---

function formatTimestamp(iso) {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        return d.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    } catch {
        return iso;
    }
}

function formatTime(iso) {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        return d.toLocaleTimeString(undefined, {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    } catch {
        return '';
    }
}

function statusBadge(status) {
    const s = (status || '').toUpperCase();
    if (s === 'POSTED') {
        return `<span class="status-badge status-badge--posted"><span class="status-badge__dot"></span>POSTED</span>`;
    }
    if (s === 'FAILED') {
        return `<span class="status-badge status-badge--failed"><span class="status-badge__dot"></span>FAILED</span>`;
    }
    return `<span class="status-badge status-badge--progress"><span class="status-badge__dot"></span>${s}</span>`;
}

function modelShortName(modelId) {
    if (!modelId) return '—';
    if (modelId.includes('nova-micro')) return 'Nova Micro';
    if (modelId.includes('nova-lite')) return 'Nova Lite';
    if (modelId.includes('claude-3-haiku')) return 'Claude 3 Haiku';
    if (modelId.includes('claude-3-sonnet')) return 'Claude 3 Sonnet';
    if (modelId.includes('llama3-1-70b')) return 'Llama 3.1 70B';
    if (modelId.includes('titan-text-premier')) return 'Titan Premier';
    return modelId.split(':')[0].split('.').pop();
}

function toast(message, type = 'info') {
    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.textContent = message;
    $toastContainer.appendChild(el);
    setTimeout(() => {
        el.style.animation = 'toast-out 0.3s ease forwards';
        setTimeout(() => el.remove(), 300);
    }, 4000);
}

// --- API ---

async function fetchJson(path) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return res.json();
}

// --- Workflow List ---

async function loadWorkflows() {
    try {
        const workflows = await fetchJson('/workflows');
        renderWorkflowList(workflows);
    } catch (err) {
        console.error('Failed to load workflows:', err);
    }
}

function renderWorkflowList(workflows) {
    $workflowCount.textContent = `${workflows.length} workflow${workflows.length !== 1 ? 's' : ''}`;

    if (workflows.length === 0) {
        $workflowTable.querySelector('thead').style.display = 'none';
        $emptyState.classList.add('visible');
        $workflowTableBody.innerHTML = '';
        return;
    }

    $workflowTable.querySelector('thead').style.display = '';
    $emptyState.classList.remove('visible');

    $workflowTableBody.innerHTML = workflows.map((w, i) => `
        <tr class="animate-in" style="animation-delay: ${i * 40}ms" onclick="navigateTo('workflow/${w.workflow_id}')">
            <td class="td-filename">${escapeHtml(w.file_name || '—')}</td>
            <td class="td-model">${modelShortName(w.model_id)}</td>
            <td>${statusBadge(w.status)}</td>
            <td class="td-time">${formatTimestamp(w.created_at)}</td>
            <td class="td-arrow">→</td>
        </tr>
    `).join('');
}

// --- Workflow Detail ---

async function loadWorkflowDetail(workflowId) {
    try {
        const data = await fetchJson(`/workflows/${workflowId}`);
        renderDetail(data.workflow, data.steps);

        // Try loading extracted object
        try {
            const extracted = await fetchJson(`/workflows/${workflowId}/object`);
            renderExtracted(extracted);
        } catch {
            $extractedSection.style.display = 'none';
        }
    } catch (err) {
        console.error('Failed to load workflow detail:', err);
        toast('Failed to load workflow details', 'error');
    }
}

function renderDetail(workflow, steps) {
    const w = workflow;
    $detailHeader.innerHTML = `
        <div class="detail-header__row">
            <span class="detail-header__filename">${escapeHtml(w.file_name)}</span>
            ${statusBadge(w.status)}
        </div>
        <dl class="detail-header__meta">
            <div>
                <dt>Workflow ID</dt>
                <dd>${w.workflow_id}</dd>
            </div>
            <div>
                <dt>Model</dt>
                <dd>${modelShortName(w.model_id)}</dd>
            </div>
            <div>
                <dt>Created</dt>
                <dd>${formatTimestamp(w.created_at)}</dd>
            </div>
            <div>
                <dt>Updated</dt>
                <dd>${formatTimestamp(w.updated_at)}</dd>
            </div>
            ${w.error_message ? `<div style="flex-basis:100%"><dt style="color:var(--error)">Error</dt><dd style="color:var(--error)">${escapeHtml(w.error_message)}</dd></div>` : ''}
        </dl>
    `;

    renderPipeline(steps, w.status);
}

const PIPELINE_ORDER = ['FILE_LANDED', 'REGISTRY_MATCHED', 'CONTENT_READ', 'AGENT_PARSING', 'PARSED', 'POSTED'];

const SVG_CHECK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
const SVG_CROSS = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;

function formatStepDetail(step) {
    if (!step || !step.detail) return '<span class="detail-empty">—</span>';
    const raw = step.detail;

    // Pattern matching: e.g. "Matched pattern 'contract_*' → Nova Lite (amazon.nova-lite-v1:0)"
    const matchPattern = raw.match(/Matched pattern '([^']+)'\s*→\s*([^(]+)(?:\s*\(([^)]+)\))?/);
    if (matchPattern) {
        const pattern = matchPattern[1];
        const modelLabel = matchPattern[2].trim();
        const modelId = matchPattern[3] || '';
        return `
            <span class="detail-main">${escapeHtml(pattern)} → <strong>${escapeHtml(modelLabel)}</strong></span>
            ${modelId ? `<span class="detail-sub">${escapeHtml(modelId)}</span>` : ''}
        `;
    }

    // e.g. "Bedrock model invoked: Nova Lite"
    const invokedMatch = raw.match(/Bedrock model invoked:\s*(.+)/);
    if (invokedMatch) {
        return `
            <span class="detail-main"><strong>${escapeHtml(invokedMatch[1])}</strong></span>
            <span class="detail-sub">Bedrock InvokeModel</span>
        `;
    }

    // e.g. "File detected: contract_vendor_A.txt"
    const fileMatch = raw.match(/File detected:\s*(.+)/);
    if (fileMatch) {
        return `<span class="detail-main detail-code">${escapeHtml(fileMatch[1])}</span>`;
    }

    return `<span class="detail-main">${escapeHtml(raw)}</span>`;
}

function renderPipeline(steps, workflowStatus) {
    const stepMap = {};
    (steps || []).forEach(s => { stepMap[s.step_name] = s; });

    const failedStep = stepMap['FAILED'];

    $pipeline.innerHTML = PIPELINE_ORDER.map((name, i) => {
        const step = stepMap[name];
        let stateClass = 'pipeline-step--pending';
        let icon = `<span class="pipeline-step__num">${i + 1}</span>`;
        let connectorClass = '';

        if (step && step.status === 'SUCCESS') {
            stateClass = 'pipeline-step--success';
            icon = SVG_CHECK;
        } else if (step && step.status === 'FAILED') {
            stateClass = 'pipeline-step--failed';
            icon = SVG_CROSS;
        } else if (failedStep && !step) {
            stateClass = 'pipeline-step--pending';
            icon = `<span class="pipeline-step__num">${i + 1}</span>`;
        }

        // Connector styling between step i and step i+1
        const nextStep = stepMap[PIPELINE_ORDER[i + 1]];
        if (step && step.status === 'SUCCESS' && nextStep) {
            connectorClass = nextStep.status === 'FAILED' ? 'failed' : 'active';
        } else if (step && step.status === 'SUCCESS' && i < PIPELINE_ORDER.length - 1 && !failedStep) {
            connectorClass = 'active';
        }

        return `
            <div class="pipeline-step ${stateClass} animate-in" style="animation-delay: ${i * 60}ms">
                ${i < PIPELINE_ORDER.length - 1 ? `<div class="pipeline-step__connector ${connectorClass}"></div>` : ''}
                <div class="pipeline-step__dot" aria-label="${name}: ${step ? step.status : 'PENDING'}">${icon}</div>
                <div class="pipeline-step__content">
                    <div class="pipeline-step__label">${name}</div>
                    <div class="pipeline-step__detail">${formatStepDetail(step)}</div>
                    <div class="pipeline-step__time">${step ? formatTime(step.timestamp) : ''}</div>
                </div>
            </div>
        `;
    }).join('');
}

function renderExtracted(extracted) {
    if (!extracted || !extracted.data) {
        $extractedSection.style.display = 'none';
        return;
    }
    $extractedSection.style.display = '';
    $extractedJson.textContent = JSON.stringify(extracted.data, null, 2);
}

// --- Routing ---

function navigateTo(path) {
    window.location.hash = `#/${path}`;
}

function handleRoute() {
    const hash = window.location.hash || '#/';
    const path = hash.replace('#/', '');

    if (path.startsWith('workflow/')) {
        const id = path.replace('workflow/', '');
        showDetailView(id);
    } else {
        showListView();
    }
}

function showListView() {
    currentView = 'list';
    $listView.classList.remove('view--hidden');
    $detailView.classList.add('view--hidden');
    loadWorkflows();
    startAutoRefresh();
}

function showDetailView(workflowId) {
    currentView = 'detail';
    $listView.classList.add('view--hidden');
    $detailView.classList.remove('view--hidden');
    $extractedBody.style.display = 'none';
    $toggleExtractedBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14">
            <polyline points="6 9 12 15 18 9"/>
        </svg>
        Show JSON
    `;
    loadWorkflowDetail(workflowId);
    stopAutoRefresh();
}

// --- Auto Refresh ---

function startAutoRefresh() {
    stopAutoRefresh();
    refreshTimerValue = REFRESH_INTERVAL;
    $refreshTimer.textContent = refreshTimerValue;
    refreshIntervalId = setInterval(() => {
        refreshTimerValue--;
        $refreshTimer.textContent = refreshTimerValue;
        if (refreshTimerValue <= 0) {
            refreshTimerValue = REFRESH_INTERVAL;
            if (currentView === 'list') loadWorkflows();
        }
    }, 1000);
}

function stopAutoRefresh() {
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
        refreshIntervalId = null;
    }
}

// --- Trigger Modal ---

function openTriggerModal() {
    selectedFile = null;
    $customPath.value = '';
    $fileCards.forEach(c => c.classList.remove('selected'));
    $triggerStatus.style.display = 'none';
    $triggerModal.classList.add('open');
}

function closeTriggerModal() {
    $triggerModal.classList.remove('open');
}

async function submitTrigger() {
    const filename = selectedFile;
    const filePath = $customPath.value.trim();

    if (!filename && !filePath) {
        toast('Select a file or enter a path', 'error');
        return;
    }

    $submitTriggerBtn.disabled = true;
    $submitTriggerBtn.innerHTML = '<span class="spinner"></span> Processing...';
    $triggerStatus.style.display = 'none';

    try {
        const body = filePath ? { file_path: filePath } : { filename };
        const res = await fetch(`${API_BASE}/trigger`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();

        if (res.ok) {
            $triggerStatus.className = 'modal__status success';
            $triggerStatus.textContent = `✓ Workflow ${data.workflow_id} — ${data.status}`;
            $triggerStatus.style.display = '';
            toast(`Processed ${data.file_name} → ${data.status}`, data.status === 'POSTED' ? 'success' : 'error');

            // Refresh list and navigate
            setTimeout(() => {
                closeTriggerModal();
                loadWorkflows();
            }, 1200);
        } else {
            $triggerStatus.className = 'modal__status error';
            $triggerStatus.textContent = `✗ ${data.error || 'Unknown error'}`;
            $triggerStatus.style.display = '';
            toast(data.error || 'Trigger failed', 'error');
        }
    } catch (err) {
        $triggerStatus.className = 'modal__status error';
        $triggerStatus.textContent = `✗ ${err.message}`;
        $triggerStatus.style.display = '';
        toast('Network error', 'error');
    } finally {
        $submitTriggerBtn.disabled = false;
        $submitTriggerBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
                <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            Process Document
        `;
    }
}

// --- Escaping ---

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- Theme Management ---

function initTheme() {
    const saved = localStorage.getItem('agenticautomation-theme') || localStorage.getItem('docprocessor-theme');
    const systemPrefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
    const theme = saved || (systemPrefersLight ? 'light' : 'dark');
    setTheme(theme);
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('agenticautomation-theme', theme);
    updateThemeIcon(theme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    setTheme(current === 'dark' ? 'light' : 'dark');
}

function updateThemeIcon(theme) {
    const sun = document.querySelector('.theme-icon-sun');
    const moon = document.querySelector('.theme-icon-moon');
    if (sun && moon) {
        if (theme === 'light') {
            sun.style.display = 'none';
            moon.style.display = 'block';
        } else {
            sun.style.display = 'block';
            moon.style.display = 'none';
        }
    }
}

// --- Event Listeners ---

if ($themeToggleBtn) {
    $themeToggleBtn.addEventListener('click', toggleTheme);
}
$triggerBtn.addEventListener('click', openTriggerModal);
$closeModalBtn.addEventListener('click', closeTriggerModal);
$submitTriggerBtn.addEventListener('click', submitTrigger);
$backBtn.addEventListener('click', () => navigateTo(''));

$triggerModal.addEventListener('click', (e) => {
    if (e.target === $triggerModal) closeTriggerModal();
});

$fileCards.forEach(card => {
    card.addEventListener('click', () => {
        $fileCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedFile = card.dataset.filename;
        $customPath.value = '';
    });
});

$customPath.addEventListener('input', () => {
    if ($customPath.value.trim()) {
        selectedFile = null;
        $fileCards.forEach(c => c.classList.remove('selected'));
    }
});

$toggleExtractedBtn.addEventListener('click', () => {
    const visible = $extractedBody.style.display !== 'none';
    $extractedBody.style.display = visible ? 'none' : '';
    $toggleExtractedBtn.innerHTML = visible
        ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><polyline points="6 9 12 15 18 9"/></svg> Show JSON`
        : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><polyline points="18 15 12 9 6 15"/></svg> Hide JSON`;
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTriggerModal();
});

// --- Init ---

initTheme();
window.addEventListener('hashchange', handleRoute);
handleRoute();
