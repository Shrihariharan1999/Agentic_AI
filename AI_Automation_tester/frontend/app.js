/**
 * Signal QA - Autonomous Web Testing Studio
 * Frontend Application Engine
 */

const state = {
  activeRunId: null,
  pollTimer: null,
  activeTab: "tab-plan",
  lastRenderedLogsCount: 0,
  isAutoScroll: true,
  lastPlanSig: "",
  lastResultsSig: "",
  lastDiscoverySig: "",
  lastSummarySig: "",
  openCaseIds: new Set(),
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

// UI Elements
const el = {
  form: $("#quick-launch-form"),
  urlInput: $("#target-url-input"),
  envSelect: $("#environment-select"),
  formAlert: $("#form-alert"),
  btnLaunch: $("#btn-launch-run"),
  sessionStatusText: $("#session-status-text"),
  pulseDot: $("#pulse-dot"),
  apiStateBadge: $("#api-state-badge"),
  apiStateText: $("#api-state-text"),
  btnRefreshAll: $("#btn-refresh-all"),

  // Hero info
  targetTitle: $("#current-target-title"),
  targetDesc: $("#current-target-desc"),
  envTag: $("#current-env-tag"),
  runIdPill: $("#current-run-id-pill"),

  // Progress & Stepper
  progressStageName: $("#progress-stage-name"),
  progressPercentLabel: $("#progress-percent-label"),
  pipelineProgressBar: $("#pipeline-progress-bar"),
  stepper: $("#pipeline-stepper"),

  // HITL Banner
  hitlBanner: $("#hitl-review-banner"),
  hitlFeedback: $("#hitl-feedback-input"),
  btnApprove: $("#btn-hitl-approve"),
  btnReject: $("#btn-hitl-reject"),

  // KPIs
  kpiTotal: $("#kpi-total"),
  kpiPassed: $("#kpi-passed"),
  kpiFailed: $("#kpi-failed"),
  kpiBlocked: $("#kpi-blocked"),
  kpiPassRate: $("#kpi-pass-rate"),

  // Tabs & Counts
  tabButtons: $$(".tab-btn"),
  tabPanes: $$(".tab-pane"),
  badgePlanCount: $("#badge-plan-count"),
  badgeResultsCount: $("#badge-results-count"),
  badgeLogsCount: $("#badge-logs-count"),
  planCasesTag: $("#plan-cases-tag"),

  // Containers
  planContainer: $("#plan-container"),
  executionContainer: $("#execution-container"),
  discoveryContainer: $("#discovery-container"),
  logTerminal: $("#log-stream-terminal"),
  autoscrollToggle: $("#autoscroll-toggle"),
  btnClearLogs: $("#btn-clear-logs"),
  summaryContainer: $("#summary-container"),
  btnCopySummary: $("#btn-copy-summary"),
  linkHtmlReport: $("#link-html-report"),
  btnExportHtml: $("#btn-export-html-report"),
  historyContainer: $("#history-container"),
  btnRefreshHistory: $("#btn-refresh-history"),

  // Lightbox
  lightbox: $("#image-lightbox"),
  lightboxImg: $("#lightbox-img"),
  lightboxCaption: $("#lightbox-caption"),
  lightboxClose: $("#lightbox-close"),
  lightboxBackdrop: $("#lightbox-backdrop"),
};

// Stage mapping to stepper index
const STAGE_ORDER = [
  "validate",
  "discovery",
  "planning",
  "test_generation",
  "human_review",
  "execution",
  "summary"
];

const STATUS_STAGE_MAP = {
  created: "validate",
  discovering: "discovery",
  planning: "planning",
  test_generation: "test_generation",
  human_review: "human_review",
  executing: "execution",
  summary: "summary",
  completed: "summary",
  failed: "summary",
  cancelled: "human_review"
};

// Escape HTML for safety
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>'"]/g, (tag) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;"
  }[tag] || tag));
}

// Simple Markdown to HTML Renderer
function parseMarkdown(md) {
  if (!md) return "";
  let html = escapeHtml(md);

  // Headers
  html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  html = html.replace(/^## (.*$)/gim, "<h2>$1</h2>");
  html = html.replace(/^# (.*$)/gim, "<h1>$1</h1>");

  // Bold & Italic
  html = html.replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>");
  html = html.replace(/\*(.*?)\*/gim, "<em>$1</em>");
  html = html.replace(/`([^`]+)`/gim, "<code>$1</code>");

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Tables
  const lines = html.split("\n");
  let inTable = false;
  let tableHtml = "";
  const outputLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith("|") && line.endsWith("|")) {
      if (!inTable) {
        inTable = true;
        tableHtml = "<table>";
        const cells = line.split("|").filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
        tableHtml += "<thead><tr>" + cells.map(c => `<th>${c.trim()}</th>`).join("") + "</tr></thead><tbody>";
      } else if (line.includes("---")) {
        // Separator line - ignore
      } else {
        const cells = line.split("|").filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
        tableHtml += "<tr>" + cells.map(c => `<td>${c.trim()}</td>`).join("") + "</tr>";
      }
    } else {
      if (inTable) {
        inTable = false;
        tableHtml += "</tbody></table>";
        outputLines.push(tableHtml);
      }
      if (line.startsWith("- ")) {
        outputLines.push(`<li>${line.substring(2)}</li>`);
      } else if (line.length > 0) {
        outputLines.push(`<p>${line}</p>`);
      }
    }
  }
  if (inTable) {
    tableHtml += "</tbody></table>";
    outputLines.push(tableHtml);
  }

  return `<div class="markdown-body">${outputLines.join("\n")}</div>`;
}

// API Helper
async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!response.ok) {
    const errorText = await response.text();
    const err = new Error(errorText || `HTTP ${response.status}`);
    err.status = response.status;
    throw err;
  }
  return response.status === 204 ? null : response.json();
}

// Show Form Alert
function showAlert(message, isError = true) {
  el.formAlert.textContent = message;
  el.formAlert.classList.remove("hidden");
  el.formAlert.style.color = isError ? "var(--rose)" : "var(--emerald)";
  if (!isError) {
    setTimeout(() => el.formAlert.classList.add("hidden"), 4000);
  }
}

// Update Stepper Visuals
function updateStepper(status) {
  const currentStageKey = STATUS_STAGE_MAP[status] || "validate";
  const currentIndex = STAGE_ORDER.indexOf(currentStageKey);
  const isFinished = ["completed", "failed", "cancelled"].includes(status);

  el.stepper.querySelectorAll(".stage-step").forEach((stepEl) => {
    const stepKey = stepEl.dataset.step;
    const stepIndex = STAGE_ORDER.indexOf(stepKey);

    stepEl.classList.remove("active", "done");

    if (isFinished) {
      if (stepIndex <= currentIndex) {
        stepEl.classList.add("done");
      }
    } else {
      if (stepIndex < currentIndex) {
        stepEl.classList.add("done");
      } else if (stepIndex === currentIndex) {
        stepEl.classList.add("active");
      }
    }
  });
}

// Update KPI Metrics
function updateKPIs(stats, results, plan) {
  const total = (plan && plan.test_cases ? plan.test_cases.length : 0) || (stats ? stats.total : 0) || (results ? results.length : 0);
  const passed = results ? results.filter(r => (r.status || "").toLowerCase() === "passed").length : (stats ? stats.passed : 0);
  const failed = results ? results.filter(r => (r.status || "").toLowerCase() === "failed").length : (stats ? stats.failed : 0);
  const blocked = results ? results.filter(r => (r.status || "").toLowerCase() === "blocked").length : (stats ? stats.blocked : 0);
  const passRate = total > 0 ? ((passed / total) * 100).toFixed(1) : 0;

  el.kpiTotal.textContent = total;
  el.kpiPassed.textContent = passed;
  el.kpiFailed.textContent = failed;
  el.kpiBlocked.textContent = blocked;
  el.kpiPassRate.textContent = `${passRate}%`;

  el.badgePlanCount.textContent = total;
  el.badgeResultsCount.textContent = results ? results.length : 0;
  el.planCasesTag.textContent = `${total} Case${total === 1 ? "" : "s"} Mapped`;
}

// Toggle Test Case Accordion & Record State
window.toggleTestCase = function(headerEl) {
  const card = headerEl.closest(".test-case-card");
  if (!card) return;
  const caseId = card.dataset.caseId;
  card.classList.toggle("open");
  if (card.classList.contains("open")) {
    state.openCaseIds.add(caseId);
  } else {
    state.openCaseIds.delete(caseId);
  }
};

// Render Discovered Map
function renderDiscovery(siteMap) {
  if (!siteMap) {
    state.lastDiscoverySig = "";
    el.discoveryContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🗺️</div>
        <h4>No Discovery Data Yet</h4>
        <p>Discovery agent will crawl the target page and list interactive elements here.</p>
      </div>`;
    return;
  }

  const sig = JSON.stringify(siteMap);
  if (sig === state.lastDiscoverySig) return;
  state.lastDiscoverySig = sig;

  const links = siteMap.links || [];
  const buttons = siteMap.buttons || [];
  const inputs = siteMap.inputs || [];
  const forms = siteMap.forms || [];

  el.discoveryContainer.innerHTML = `
    <div class="plan-overview-card" style="margin-bottom: 1.5rem;">
      <div class="plan-objective-title">DISCOVERED TARGET</div>
      <div class="plan-objective-text">${escapeHtml(siteMap.title || siteMap.url)}</div>
      <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem;">${escapeHtml(siteMap.description || "No meta description found.")}</p>
      <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
        <span class="meta-tag">Auth: ${siteMap.authentication_required ? "Required" : "Public"}</span>
        <span class="meta-tag">CAPTCHA: ${siteMap.captcha_present ? "Detected" : "None"}</span>
      </div>
    </div>

    <div class="discovery-stats-grid">
      <div class="disc-stat-card"><div class="disc-stat-val">${links.length}</div><div class="disc-stat-lbl">Links</div></div>
      <div class="disc-stat-card"><div class="disc-stat-val">${buttons.length}</div><div class="disc-stat-lbl">Buttons</div></div>
      <div class="disc-stat-card"><div class="disc-stat-val">${inputs.length}</div><div class="disc-stat-lbl">Inputs</div></div>
      <div class="disc-stat-card"><div class="disc-stat-val">${forms.length}</div><div class="disc-stat-lbl">Forms</div></div>
    </div>

    <div class="discovery-elements-grid">
      <div class="disc-panel">
        <h4>🔗 Discovered Links (${links.length})</h4>
        <ul class="disc-list">
          ${links.length ? links.slice(0, 30).map(l => `<li>${escapeHtml(l.text || l.href || "Link")} &rarr; <span style="color:var(--text-dim);">${escapeHtml(l.href)}</span></li>`).join("") : "<li>No links detected.</li>"}
        </ul>
      </div>
      <div class="disc-panel">
        <h4>🔘 Interactive Buttons (${buttons.length})</h4>
        <ul class="disc-list">
          ${buttons.length ? buttons.slice(0, 30).map(b => `<li>${escapeHtml(b.text || b.selector || "Button")} <code style="font-size:0.7rem;">${escapeHtml(b.selector || "")}</code></li>`).join("") : "<li>No buttons detected.</li>"}
        </ul>
      </div>
    </div>
  `;
}

// Render Test Plan & Steps
function renderTestPlan(plan) {
  if (!plan || !plan.test_cases || plan.test_cases.length === 0) {
    state.lastPlanSig = "";
    el.planContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📋</div>
        <h4>No Test Plan Generated Yet</h4>
        <p>Enter a target URL above and click "Execute Test Pipeline" to discover elements and generate a structured test plan.</p>
      </div>`;
    return;
  }

  // Preserve user open card state
  el.planContainer.querySelectorAll(".test-case-card.open").forEach(c => {
    if (c.dataset.caseId) state.openCaseIds.add(c.dataset.caseId);
  });

  const sig = JSON.stringify(plan);
  if (sig === state.lastPlanSig) return; // Prevent closing dropdowns on poll ticks
  state.lastPlanSig = sig;

  const cases = plan.test_cases || [];

  const casesHtml = cases.map((tc, index) => {
    const priority = (tc.priority || "medium").toLowerCase();
    const category = (tc.category || "functional").toLowerCase();
    const steps = tc.steps || [];
    const isOpen = state.openCaseIds.has(tc.id) || (state.openCaseIds.size === 0 && index === 0);

    const stepsTableHtml = steps.length > 0 ? `
      <table class="steps-table">
        <thead>
          <tr>
            <th style="width: 50px;">Step</th>
            <th style="width: 100px;">Action</th>
            <th>Target Selector</th>
            <th>Input Value</th>
            <th>Expected Result</th>
          </tr>
        </thead>
        <tbody>
          ${steps.map(s => `
            <tr>
              <td><span style="font-family: var(--font-mono); color: var(--text-dim); font-weight:600;">#${s.step_number}</span></td>
              <td><span class="step-action-tag">${escapeHtml(s.action || "action")}</span></td>
              <td><code class="step-target-code">${escapeHtml(s.target || "-")}</code></td>
              <td><span style="font-family:var(--font-mono); color: var(--amber);">${escapeHtml(s.value || "-")}</span></td>
              <td><span style="color: var(--text-muted);">${escapeHtml(s.expected_result || "-")}</span></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    ` : `<p style="color: var(--text-dim); font-size: 0.8rem;">No explicit steps populated.</p>`;

    return `
      <div class="test-case-card ${isOpen ? "open" : ""}" data-case-id="${escapeHtml(tc.id)}">
        <div class="test-case-header" onclick="window.toggleTestCase(this)">
          <div class="tc-title-wrapper">
            <span class="tc-id-badge">${escapeHtml(tc.id || `TC-${index+1}`)}</span>
            <span class="tc-title-text">${escapeHtml(tc.title || "Untitled Test")}</span>
          </div>
          <div class="tc-badges">
            <span class="priority-tag ${priority}">${priority}</span>
            <span class="category-tag">${category}</span>
            <span class="tc-chevron">&#9660;</span>
          </div>
        </div>
        <div class="test-case-body">
          <p class="tc-desc">${escapeHtml(tc.description || "No description provided.")}</p>
          <div style="margin-bottom: 0.75rem; font-size: 0.8rem; color: var(--text-dim);">
            <strong>Expected Outcome:</strong> <span style="color: var(--text-main);">${escapeHtml(tc.expected_result || "Verification passed.")}</span>
          </div>
          ${stepsTableHtml}
        </div>
      </div>
    `;
  }).join("");

  el.planContainer.innerHTML = `
    <div class="plan-overview-card">
      <div class="plan-objective-title">QA TEST OBJECTIVE</div>
      <div class="plan-objective-text">${escapeHtml(plan.objective || "Autonomous Web Verification Suite")}</div>
      <div class="plan-strategy-box">
        <strong>Strategy:</strong> ${escapeHtml(plan.strategy || "Execute smoke, functional, and form interaction checks.")}
      </div>
    </div>
    <div class="test-cases-grid">
      ${casesHtml}
    </div>
  `;
}

// Render Execution Results & Evidence
function renderExecutionResults(results, plan) {
  if (!results || results.length === 0) {
    state.lastResultsSig = "";
    el.executionContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚡</div>
        <h4>No Execution Results Available</h4>
        <p>Once the plan is approved, live browser interactions and screenshot evidence will stream here in real time.</p>
      </div>`;
    return;
  }

  const sig = JSON.stringify(results);
  if (sig === state.lastResultsSig) return;
  state.lastResultsSig = sig;

  el.btnExportHtml.style.display = "inline-flex";

  const resultsHtml = results.map(res => {
    const status = (res.status || "pending").toLowerCase();
    const caseObj = plan && plan.test_cases ? plan.test_cases.find(c => c.id === res.test_case_id) : null;
    const title = caseObj ? caseObj.title : `Test Case ${res.test_case_id}`;

    // Evidence Screenshots
    const evidenceItems = (res.evidence || []).filter(e => e.type === "screenshot" && e.location);
    const galleryHtml = evidenceItems.length > 0 ? `
      <div class="evidence-gallery">
        ${evidenceItems.map(ev => `
          <img class="evidence-thumb" src="${escapeHtml(ev.location)}" alt="${escapeHtml(ev.description || 'Test Screenshot')}" onclick="openLightbox('${escapeHtml(ev.location)}', '${escapeHtml(ev.description || title)}')">
        `).join("")}
      </div>
    ` : "";

    // Failure Diagnostics
    const failureHtml = res.failure ? `
      <div class="failure-diagnostics-box">
        <div><strong>Root Cause:</strong> ${escapeHtml(res.failure.root_cause || res.failure.message || "Unknown error")}</div>
        <div style="margin-top: 0.25rem; color: var(--text-dim);">Classification: <code style="color:#fb7185;">${escapeHtml(res.failure.failure_type || "application")}</code> (Confidence: ${((res.failure.confidence || 0.9)*100).toFixed(0)}%)</div>
      </div>
    ` : "";

    return `
      <div class="result-card ${status}">
        <div class="result-header">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span class="tc-id-badge">${escapeHtml(res.test_case_id)}</span>
            <strong style="font-size: 0.95rem;">${escapeHtml(title)}</strong>
          </div>
          <span class="status-tag ${status}">${status}</span>
        </div>
        <div class="result-actual">${escapeHtml(res.actual_result || "No logs reported.")}</div>
        ${galleryHtml}
        ${failureHtml}
      </div>
    `;
  }).join("");

  el.executionContainer.innerHTML = `<div class="results-list">${resultsHtml}</div>`;
}

// Render Live Event Stream Logs
function renderLogs(logs) {
  if (!logs || logs.length === 0) return;
  el.badgeLogsCount.textContent = logs.length;

  if (logs.length === state.lastRenderedLogsCount) return;
  state.lastRenderedLogsCount = logs.length;

  const entriesHtml = logs.map(l => `
    <div class="log-entry ${escapeHtml(l.level || 'info')}">
      <span class="log-time">[${escapeHtml(l.time || '00:00:00')}]</span>
      <span class="log-stage">${escapeHtml(l.stage ? `[${l.stage}]` : '[Pipeline]')}</span>
      <span>${escapeHtml(l.message || '')}</span>
    </div>
  `).join("");

  el.logTerminal.innerHTML = entriesHtml;

  if (state.isAutoScroll) {
    el.logTerminal.scrollTop = el.logTerminal.scrollHeight;
  }
}

// Render Executive Summary
function renderSummary(summaryText, htmlReportPath) {
  if (!summaryText) {
    state.lastSummarySig = "";
    el.summaryContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📊</div>
        <h4>Summary Report Pending</h4>
        <p>The complete Executive Summary with metrics, diagnostics, and recommendations will be rendered here upon run completion.</p>
      </div>`;
    el.linkHtmlReport.style.display = "none";
    return;
  }

  const sig = summaryText + (htmlReportPath || "");
  if (sig === state.lastSummarySig) return;
  state.lastSummarySig = sig;

  el.summaryContainer.innerHTML = parseMarkdown(summaryText);
  if (htmlReportPath) {
    el.linkHtmlReport.href = htmlReportPath;
    el.linkHtmlReport.style.display = "inline-flex";
    el.btnExportHtml.onclick = () => window.open(htmlReportPath, "_blank");
  }
}

// Render Run History
function renderHistory(runs) {
  if (!runs || runs.length === 0) {
    el.historyContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📜</div>
        <h4>No Previous Runs Found</h4>
        <p>Launched test runs will be recorded here for instant replay and inspection.</p>
      </div>`;
    return;
  }

  const itemsHtml = runs.map(run => {
    const status = (run.status || "created").toLowerCase();
    return `
      <div class="history-card" data-run-id="${escapeHtml(run.run_id || run.id)}">
        <div class="history-card-header">
          <span class="status-tag ${status}">${status}</span>
          <span class="history-time">${escapeHtml((run.created_at || '').replace('T', ' ').slice(0, 19))}</span>
        </div>
        <div class="history-url">${escapeHtml(run.target_url || 'Target')}</div>
        <div style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-dim);">
          ID: ${escapeHtml(run.run_id || run.id)}
        </div>
      </div>
    `;
  }).join("");

  el.historyContainer.innerHTML = `<div class="history-grid">${itemsHtml}</div>`;

  // Attach click events
  el.historyContainer.querySelectorAll(".history-card").forEach(card => {
    card.addEventListener("click", () => {
      const runId = card.dataset.runId;
      if (runId) loadRun(runId);
    });
  });
}

// Open Image Lightbox
window.openLightbox = function(imgSrc, caption) {
  el.lightboxImg.src = imgSrc;
  el.lightboxCaption.textContent = caption || "Screenshot preview";
  el.lightbox.classList.remove("hidden");
};

function closeLightbox() {
  el.lightbox.classList.add("hidden");
  el.lightboxImg.src = "";
}

// Load Specific Run State
async function loadRun(runId) {
  try {
    const run = await api(`/api/test-runs/${encodeURIComponent(runId)}`);
    state.activeRunId = run.run_id || run.id;

    // Header & Meta
    el.targetTitle.textContent = run.target_url || "Target Website";
    el.targetDesc.textContent = `Target Environment: ${run.environment || 'development'} | Session ID: ${state.activeRunId}`;
    el.envTag.textContent = (run.environment || "DEVELOPMENT").toUpperCase();
    el.runIdPill.textContent = `RUN: ${state.activeRunId}`;

    // Status & Progress
    const status = run.status || "created";
    const stageName = run.current_stage || status;
    const progressPercent = run.progress_percent || 0;

    el.progressStageName.textContent = stageName;
    el.progressPercentLabel.textContent = `${progressPercent}%`;
    el.pipelineProgressBar.style.width = `${progressPercent}%`;
    el.sessionStatusText.textContent = `${stageName} (${progressPercent}%)`;

    // Pulse Dot styling
    el.pulseDot.className = "pulse-indicator";
    if (status === "completed") {
      el.pulseDot.style.background = "var(--emerald)";
    } else if (status === "failed") {
      el.pulseDot.style.background = "var(--rose)";
    } else if (status === "human_review") {
      el.pulseDot.style.background = "var(--amber)";
    } else {
      el.pulseDot.style.background = "var(--cyan)";
    }

    // Update Stepper
    updateStepper(status);

    // HITL Banner
    if (status === "human_review") {
      el.hitlBanner.classList.remove("hidden");
    } else {
      el.hitlBanner.classList.add("hidden");
    }

    // Update KPIs
    updateKPIs(run.stats, run.test_results, run.test_plan);

    // Render Sub-components
    renderTestPlan(run.test_plan);
    renderExecutionResults(run.test_results, run.test_plan);
    renderDiscovery(run.website_map);
    renderLogs(run.logs);
    renderSummary(run.final_summary, run.html_report_path);

    // Continue Polling if active
    if (["created", "discovering", "planning", "test_generation", "human_review", "executing", "summary"].includes(status)) {
      startPolling();
    } else {
      stopPolling();
      loadHistory();
    }

  } catch (err) {
    if (err.status === 404) {
      stopPolling();
      showAlert(`Run ${runId} was not found.`, true);
    } else {
      showAlert(`Failed to fetch run state: ${err.message}`, true);
    }
  }
}

// Start / Stop Polling
function startPolling() {
  stopPolling();
  state.pollTimer = setInterval(() => {
    if (state.activeRunId) {
      loadRun(state.activeRunId);
    }
  }, 1200);
}

function stopPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

// Load Run History
async function loadHistory() {
  try {
    const runs = await api("/api/test-runs?limit=30");
    renderHistory(runs);
    setApiOnline(true);
  } catch (err) {
    setApiOnline(false);
  }
}

function setApiOnline(online) {
  el.apiStateBadge.style.color = online ? "var(--emerald)" : "var(--rose)";
  el.apiStateBadge.style.background = online ? "rgba(16, 185, 129, 0.1)" : "rgba(244, 63, 94, 0.1)";
  el.apiStateText.textContent = online ? "API Online" : "API Offline";
}

// Launch Run Form Submit
async function onLaunchSubmit(e) {
  e.preventDefault();
  const rawUrl = el.urlInput.value.trim();
  if (!rawUrl) return;

  const targetUrl = /^https?:\/\//i.test(rawUrl) ? rawUrl : `https://${rawUrl}`;
  const environment = el.envSelect.value;

  showAlert("Launching autonomous test pipeline...", false);
  el.btnLaunch.disabled = true;

  try {
    const res = await api("/api/test-runs", {
      method: "POST",
      body: JSON.stringify({ target_url: targetUrl, environment })
    });

    state.activeRunId = res.run_id;
    showAlert(`Run ${res.run_id} started successfully!`, false);
    await loadRun(res.run_id);
    startPolling();
    loadHistory();
  } catch (err) {
    showAlert(`Could not start run: ${err.message}`, true);
  } finally {
    el.btnLaunch.disabled = false;
  }
}

// Human Review Sign-Off Action
async function onHitlAction(approved) {
  if (!state.activeRunId) return;

  const btn = approved ? el.btnApprove : el.btnReject;
  btn.disabled = true;
  const feedback = el.hitlFeedback.value.trim();

  try {
    await api(`/api/test-runs/${encodeURIComponent(state.activeRunId)}/approve?approved=${approved}&feedback=${encodeURIComponent(feedback)}`, {
      method: "POST"
    });
    el.hitlBanner.classList.add("hidden");
    showAlert(approved ? "Plan approved! Resuming execution in browser..." : "Plan rejected. Pipeline aborted.", false);
    await loadRun(state.activeRunId);
    startPolling();
  } catch (err) {
    showAlert(`Failed to submit review: ${err.message}`, true);
  } finally {
    btn.disabled = false;
  }
}

// Copy Summary Markdown
function onCopySummary() {
  const summaryEl = el.summaryContainer.querySelector(".markdown-body");
  if (!summaryEl) {
    showAlert("No summary available to copy.", true);
    return;
  }
  navigator.clipboard.writeText(summaryEl.innerText).then(() => {
    showAlert("Markdown report copied to clipboard!", false);
  }).catch(() => {
    showAlert("Failed to copy report.", true);
  });
}

// Tab Switching
function setupTabs() {
  el.tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTabId = btn.dataset.tab;
      el.tabButtons.forEach(b => b.classList.remove("active"));
      el.tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPane = $(`#${targetTabId}`);
      if (targetPane) targetPane.classList.add("active");
      state.activeTab = targetTabId;
    });
  });
}

// Event Listeners
function initEventListeners() {
  el.form.addEventListener("submit", onLaunchSubmit);
  el.btnApprove.addEventListener("click", () => onHitlAction(true));
  el.btnReject.addEventListener("click", () => onHitlAction(false));
  el.btnRefreshAll.addEventListener("click", () => {
    if (state.activeRunId) loadRun(state.activeRunId);
    loadHistory();
  });
  el.btnRefreshHistory.addEventListener("click", loadHistory);
  el.btnCopySummary.addEventListener("click", onCopySummary);

  el.autoscrollToggle.addEventListener("change", (e) => {
    state.isAutoScroll = e.target.checked;
  });

  el.btnClearLogs.addEventListener("click", () => {
    el.logTerminal.innerHTML = '<div class="log-entry system"><span class="log-time">00:00:00</span> <span class="log-stage">[System]</span> Log terminal cleared.</div>';
    state.lastRenderedLogsCount = 0;
  });

  // Lightbox Close
  el.lightboxClose.addEventListener("click", closeLightbox);
  el.lightboxBackdrop.addEventListener("click", closeLightbox);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLightbox();
  });
}

// Initialization
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  initEventListeners();
  loadHistory();
});
