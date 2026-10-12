/**
 * ==========================================================================
 * LedgerIQ — Enterprise AI Finance Controller Application Logic
 * Full API Integration, State Management, Real-time Charts, and Copilot
 * ==========================================================================
 */

const API_BASE = 'http://localhost:8000';

// Global Application State
const AppState = {
  activeBatchId: localStorage.getItem('ledgeriq_batch_id') || null,
  batchRecords: [],
  filteredRecords: [],
  exceptions: [],
  filteredExceptions: [],
  selectedException: null,
  summary: null,
  forecastBaseline: null,
  forecastSimulated: null,
  auditEvents: [],
  theme: localStorage.getItem('ledgeriq_theme') || 'dark',
  currentTab: 'overview',
  exceptionRiskFilter: 'ALL',
  sourceFilter: 'ALL',
  searchQuery: '',
  runwayChart: null,
  simChart: null,
  copilotThread: [],
  pagination: {
    page: 1,
    pageSize: 10,
    totalPages: 1
  }
};

// ---------------------------------------------------------------------------
// Toast Notification Utility
// ---------------------------------------------------------------------------
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  if (type === 'danger') icon = '❌';
  if (type === 'warning') icon = '⚠️';

  toast.innerHTML = `<span>${icon}</span><div style="flex:1">${message}</div>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(30px)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------
function formatINR(amount) {
  if (amount === undefined || amount === null) return '₹0.00';
  const num = parseFloat(amount);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2
  }).format(num);
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function truncateId(id) {
  if (!id) return '—';
  return id.substring(0, 8) + '…';
}

// ---------------------------------------------------------------------------
// API Client
// ---------------------------------------------------------------------------
const API = {
  async health() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      return await res.json();
    } catch (err) {
      return { status: 'error', db: 'disconnected', error: err.message };
    }
  },

  async generateSyntheticBatch() {
    const res = await fetch(`${API_BASE}/api/batch/generate-synthetic`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to generate synthetic batch`);
    return await res.json();
  },

  async getBatchRecords(batchId) {
    const res = await fetch(`${API_BASE}/api/batch/${batchId}/records`);
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load batch records`);
    return await res.json();
  },

  async runReconciliation(batchId) {
    const res = await fetch(`${API_BASE}/api/reconciliation/run/${batchId}`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Reconciliation failed`);
    return await res.json();
  },

  async getReconciliationSummary(batchId) {
    const res = await fetch(`${API_BASE}/api/reconciliation/summary/${batchId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch summary`);
    return await res.json();
  },

  async getExceptions(batchId, riskScore = null, limit = 200, offset = 0) {
    let url = `${API_BASE}/api/reconciliation/exceptions/${batchId}?limit=${limit}&offset=${offset}`;
    if (riskScore && riskScore !== 'ALL') {
      url += `&risk_score=${riskScore}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch exceptions`);
    return await res.json();
  },

  async diagnoseAllExceptions(batchId) {
    const res = await fetch(`${API_BASE}/api/exceptions/diagnose/${batchId}`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Diagnosis failed`);
    return await res.json();
  },

  async handleExceptionAction(exceptionId, action, synthesizeRule = false, resolvedBy = 'Controller Abhi') {
    const res = await fetch(`${API_BASE}/api/exceptions/${exceptionId}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: action,
        synthesize_rule: synthesizeRule,
        resolved_by: resolvedBy
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Exception action failed`);
    return await res.json();
  },

  async getRunwayForecast(batchId, startDate = null) {
    let url = `${API_BASE}/api/forecast/runway/${batchId}`;
    if (startDate) url += `?start_date=${startDate}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to compute forecast`);
    return await res.json();
  },

  async runSimulation(payload) {
    const res = await fetch(`${API_BASE}/api/forecast/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Simulation failed`);
    return await res.json();
  },

  async getAuditTrail(batchId, actionType = null) {
    let url = `${API_BASE}/api/audit/trail/${batchId}?limit=300`;
    if (actionType && actionType !== 'ALL') {
      url += `&action_type=${actionType}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch audit trail`);
    return await res.json();
  },

  getAuditExportUrl(batchId, format = 'json') {
    return `${API_BASE}/api/audit/export/${batchId}?format=${format}`;
  },

  async askCopilot(batchId, query) {
    const res = await fetch(`${API_BASE}/api/copilot/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ batch_id: batchId, message: query, query: query })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Copilot failed`);
    return await res.json();
  },

  async loadSampleData() {
    const res = await fetch(`${API_BASE}/api/batch/load-sample-data`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load sample data`);
    return await res.json();
  },

  async getNeatLogs(limit = 200, category = null) {
    let url = `${API_BASE}/api/neatlogs?limit=${limit}`;
    if (category && category !== 'ALL') url += `&category=${category}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch NeatLogs`);
    return await res.json();
  },

  async clearNeatLogs() {
    const res = await fetch(`${API_BASE}/api/neatlogs/clear`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to clear NeatLogs`);
    return await res.json();
  }
};

// ---------------------------------------------------------------------------
// Sequential Animated Title on Landing Page
// ---------------------------------------------------------------------------
function initSequentialTitle() {
  const container = document.getElementById('animated-ledgeriq-title');
  if (!container) return;

  const titleText = "LedgerIQ";
  container.innerHTML = '';

  titleText.split('').forEach((char, index) => {
    const span = document.createElement('span');
    span.className = 'animated-letter';
    span.textContent = char;
    span.style.animationDelay = `${index * 0.08}s`;
    container.appendChild(span);
  });
}

function showLandingPage() {
  const landing = document.getElementById('landing-page');
  if (landing) {
    landing.classList.remove('hidden');
    initSequentialTitle();
  }
}
window.showLandingPage = showLandingPage;
window.returnToLanding = showLandingPage;

// ---------------------------------------------------------------------------
// Navigation / Section Routing
// ---------------------------------------------------------------------------
function switchTab(tabName) {
  AppState.currentTab = tabName;

  // Update tab buttons
  document.querySelectorAll('.nav-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
  });

  // Update sections
  document.querySelectorAll('.page-section').forEach(sec => {
    sec.classList.toggle('active', sec.id === `section-${tabName}`);
  });

  // Load specific data on tab enter
  if (tabName === 'neatlogs') {
    loadNeatLogs();
  } else if (AppState.activeBatchId) {
    if (tabName === 'overview') refreshOverview();
    if (tabName === 'reconciliation') loadReconciliationData();
    if (tabName === 'exceptions') loadExceptionsData();
    if (tabName === 'forecast') loadForecastData();
    if (tabName === 'audit') loadAuditData();
  }
}

// ---------------------------------------------------------------------------
// NeatLogs Log Stream Functions
// ---------------------------------------------------------------------------
async function loadNeatLogs() {
  const container = document.getElementById('neatlogs-console-body');
  if (!container) return;

  const categoryFilter = document.getElementById('neatlogs-category-filter')?.value || 'ALL';
  const searchInput = document.getElementById('neatlogs-search-input')?.value?.toLowerCase() || '';

  try {
    const logs = await API.getNeatLogs(300, categoryFilter);
    let filtered = logs;
    if (searchInput) {
      filtered = logs.filter(l => 
        (l.message && l.message.toLowerCase().includes(searchInput)) ||
        (l.category && l.category.toLowerCase().includes(searchInput)) ||
        (l.level && l.level.toLowerCase().includes(searchInput))
      );
    }

    if (!filtered || filtered.length === 0) {
      container.innerHTML = `<div style="color:var(--text-muted); padding:16px;">No NeatLogs matching current filter criteria.</div>`;
      return;
    }

    const html = filtered.map(log => {
      let levelColor = '#38bdf8';
      if (log.level === 'SUCCESS') levelColor = '#34d399';
      if (log.level === 'WARN') levelColor = '#fbbf24';
      if (log.level === 'ERROR') levelColor = '#f87171';
      if (log.level === 'AI_DECISION') levelColor = '#c084fc';
      if (log.level === 'RECON') levelColor = '#60a5fa';
      if (log.level === 'AUDIT') levelColor = '#a7f3d0';

      const timeStr = log.timestamp ? log.timestamp.substring(11, 19) : '';
      return `<div style="margin-bottom:6px; line-height:1.4;">
        <span style="color:#6e7681;">[${timeStr}]</span>
        <span style="color:${levelColor}; font-weight:600; margin:0 6px;">[${log.level}]</span>
        <span style="color:#a5d6ff; margin-right:8px;">[${log.category}]</span>
        <span>${log.message}</span>
      </div>`;
    }).join('');

    // Update Ticker Preview on Overview dashboard
    const tickerContainer = document.getElementById('neatlogs-ticker-content');
    if (tickerContainer && logs.length > 0) {
      const recent = logs.slice(-3);
      tickerContainer.innerHTML = recent.map(log => {
        const timeStr = log.timestamp ? log.timestamp.substring(11, 19) : '';
        return `<div><span style="color:#64748b;">[${timeStr}]</span> <span style="color:#38bdf8;">[${log.category}]</span> ${log.message}</div>`;
      }).join('');
    }

    container.innerHTML = html;
    container.scrollTop = container.scrollHeight;
  } catch (err) {
    container.innerHTML = `<div style="color:#f87171;">Failed to load NeatLogs stream: ${err.message}</div>`;
  }
}

async function handleClearNeatLogs() {
  try {
    await API.clearNeatLogs();
    showToast('NeatLogs stream cleared', 'info');
    await loadNeatLogs();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

// ---------------------------------------------------------------------------
// Sample Data Ingestion Handler
// ---------------------------------------------------------------------------
async function handleLoadSampleData() {
  const btn = document.getElementById('btn-overview-load-sample');
  if (btn) btn.disabled = true;
  showToast('Loading pre-packaged CFO.AI sample dataset...', 'info');

  try {
    const res = await API.loadSampleData();
    AppState.activeBatchId = res.batch_id;
    localStorage.setItem('ledgeriq_batch_id', res.batch_id);

    showToast(`Sample Data Loaded! Ingested ${res.total_records} records (${res.bank_count} Bank, ${res.gateway_count} Gateway, ${res.invoice_count} Invoices)`, 'success');

    updateBatchSelector();
    await refreshOverview();
    if (AppState.currentTab === 'reconciliation') await loadReconciliationData();
    if (AppState.currentTab === 'neatlogs') await loadNeatLogs();
  } catch (err) {
    showToast(err.message, 'danger');
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Health Status Check
// ---------------------------------------------------------------------------
async function checkSystemHealth() {
  const healthPill = document.getElementById('system-health-pill');
  if (!healthPill) return;

  healthPill.innerHTML = `
    <span class="badge-dot" style="background:#f59e0b; animation: pulseGlow 1s infinite;"></span>
    <span>Checking...</span>
  `;

  const health = await API.health();
  const isHealthy = health.db === 'connected';

  healthPill.innerHTML = `
    <span class="badge-dot" style="background:${isHealthy ? '#10b981' : '#ef4444'}"></span>
    <span>${isHealthy ? 'System Active' : 'Degraded'}</span>
    <span style="color:var(--text-muted); font-size:0.7rem;">(${health.db_latency_ms || 0}ms)</span>
  `;
  healthPill.title = `Database: ${health.db} | LLM Configured: ${health.llm_configured} (${health.llm_model || 'Heuristic Fallback'})`;
}

// ---------------------------------------------------------------------------
// Ingestion / Batch Generation Workflow
// ---------------------------------------------------------------------------
async function handleGenerateBatch() {
  const btn = document.getElementById('btn-generate-batch');
  const btnOverview = document.getElementById('btn-overview-generate');
  
  if (btn) btn.disabled = true;
  if (btnOverview) btnOverview.disabled = true;
  showToast('Generating multi-source synthetic batch (Bank, Gateway, Invoices)...', 'info');

  try {
    const res = await API.generateSyntheticBatch();
    AppState.activeBatchId = res.batch_id;
    localStorage.setItem('ledgeriq_batch_id', res.batch_id);

    showToast(`Batch Generated! Ingested ${res.total_records} records (${res.bank_count} Bank, ${res.gateway_count} Gateway, ${res.invoice_count} Invoices)`, 'success');
    
    updateBatchSelector();
    await refreshOverview();
    if (AppState.currentTab === 'reconciliation') await loadReconciliationData();
  } catch (err) {
    showToast(err.message, 'danger');
  } finally {
    if (btn) btn.disabled = false;
    if (btnOverview) btnOverview.disabled = false;
  }
}

function updateBatchSelector() {
  const select = document.getElementById('active-batch-select');
  if (!select) return;

  if (AppState.activeBatchId) {
    select.innerHTML = `<option value="${AppState.activeBatchId}">Batch: ${truncateId(AppState.activeBatchId)}</option>`;
  } else {
    select.innerHTML = `<option value="">No Active Batch</option>`;
  }

  const copilotBadge = document.getElementById('copilot-active-batch-badge');
  if (copilotBadge) {
    copilotBadge.textContent = AppState.activeBatchId ? truncateId(AppState.activeBatchId) : 'None';
  }
}

// ---------------------------------------------------------------------------
// Reconciliation Cascade Runner
// ---------------------------------------------------------------------------
async function handleRunReconciliation() {
  if (!AppState.activeBatchId) {
    showToast('Please generate or select an active batch first', 'warning');
    return;
  }

  const btn = document.getElementById('btn-run-reconciliation');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Reconciling Cascade...</span>`;
  }

  showToast('Running 3-tier reconciliation cascade (Exact → Subset-Sum → RapidFuzz)...', 'info');

  try {
    const result = await API.runReconciliation(AppState.activeBatchId);
    showToast(`Reconciliation Complete! Matched ${result.matched_count} records (${result.match_rate}%), ${result.exception_count} exceptions flagged.`, 'success');
    
    await refreshOverview();
    if (AppState.currentTab === 'reconciliation') await loadReconciliationData();
    if (AppState.currentTab === 'exceptions') await loadExceptionsData();
  } catch (err) {
    showToast(err.message, 'danger');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>⚡ Run Reconciliation Cascade</span>`;
    }
  }
}

// ---------------------------------------------------------------------------
// Overview Dashboard Synchronization
// ---------------------------------------------------------------------------
async function refreshOverview() {
  if (!AppState.activeBatchId) return;

  try {
    const summary = await API.getReconciliationSummary(AppState.activeBatchId);
    AppState.summary = summary;

    // KPI Cards
    setText('kpi-total-records', summary.total_records || 0);
    setText('kpi-matched-records', summary.matched_count || 0);
    setText('kpi-match-rate', `${summary.match_rate || 0}%`);
    setText('kpi-exceptions', summary.exception_count || 0);
    setText('kpi-high-risk', summary.risk_breakdown?.high || 0);
    setText('kpi-resolved', summary.resolved_count || 0);

    // Progress Bar
    const progBar = document.getElementById('overview-match-progress');
    if (progBar) progBar.style.width = `${summary.match_rate || 0}%`;

    // Cascade breakdown
    setText('summary-tier1', `${summary.tier_breakdown?.tier1_exact || 0} Records`);
    setText('summary-tier2', `${summary.tier_breakdown?.tier2_one_to_many || 0} Records`);
    setText('summary-tier3', `${summary.tier_breakdown?.tier3_fuzzy || 0} Records`);

    // Risk breakdown
    setText('summary-risk-high', `${summary.risk_breakdown?.high || 0} Items`);
    setText('summary-risk-med', `${summary.risk_breakdown?.medium || 0} Items`);
    setText('summary-risk-low', `${summary.risk_breakdown?.low || 0} Items`);

    // Cash Health Summary
    const forecast = await API.getRunwayForecast(AppState.activeBatchId);
    if (forecast) {
      setText('kpi-current-cash', formatINR(forecast.baseline_cash));
      const day30 = forecast.daily_projection[forecast.daily_projection.length - 1];
      setText('kpi-projected-cash', formatINR(day30?.projected_balance || 0));
      
      const d2z = forecast.liquidity_risk.days_to_zero;
      setText('kpi-days-to-zero', d2z !== null ? `${d2z} Days` : 'Safe (Never)');
      
      const healthBadge = document.getElementById('kpi-liquidity-health');
      if (healthBadge) {
        healthBadge.textContent = forecast.liquidity_risk.risk_level;
        healthBadge.className = `badge badge-${forecast.liquidity_risk.risk_level === 'HEALTHY' ? 'success' : forecast.liquidity_risk.risk_level === 'CAUTION' ? 'warning' : 'danger'}`;
      }
    }

    // Agent metric state cards updates
    setText('agent-metric-ingest', `Ingested: ${summary.total_records || 0} Records`);
    setText('agent-metric-recon', `Match Rate: ${summary.match_rate || 0}% (${summary.matched_count || 0} matched)`);
    setText('agent-metric-diag', `Exceptions: ${summary.exception_count || 0} (${summary.risk_breakdown?.high || 0} High Risk)`);
    setText('agent-metric-audit', `Resolved HITL: ${summary.resolved_count || 0}`);

    // Recent Activity Feed
    loadRecentActivityFeed();

    // Refresh NeatLogs Ticker
    await loadNeatLogs();
  } catch (err) {
    console.error('Failed to refresh overview:', err);
  }
}

async function loadRecentActivityFeed() {
  const container = document.getElementById('recent-activity-list');
  if (!container || !AppState.activeBatchId) return;

  try {
    const trail = await API.getAuditTrail(AppState.activeBatchId);
    const events = (trail.events || []).slice(0, 6);

    if (events.length === 0) {
      container.innerHTML = `<div style="color:var(--text-muted); padding:16px; text-align:center;">No recent activity logged for this batch yet.</div>`;
      return;
    }

    container.innerHTML = events.map(e => `
      <div class="activity-item">
        <div style="display:flex; align-items:center; gap:10px;">
          <span class="badge ${getEventBadgeClass(e.action_type)}">${e.action_type}</span>
          <span style="color:var(--text-primary); font-weight:500;">${escapeHtml(e.reasoning_snapshot || e.action_type)}</span>
        </div>
        <span style="color:var(--text-muted); font-size:0.75rem; font-family:var(--font-mono);">${new Date(e.created_at).toLocaleTimeString()}</span>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load activity feed:', err);
  }
}

function getEventBadgeClass(actionType) {
  if (actionType.includes('MATCH')) return 'badge-success';
  if (actionType.includes('EXCEPTION')) return 'badge-danger';
  if (actionType.includes('APPROVED')) return 'badge-info';
  if (actionType.includes('RULE')) return 'badge-warning';
  return 'badge-neutral';
}

// ---------------------------------------------------------------------------
// Reconciliation Center (Records Table & Filters)
// ---------------------------------------------------------------------------
async function loadReconciliationData() {
  if (!AppState.activeBatchId) return;

  try {
    const data = await API.getBatchRecords(AppState.activeBatchId);
    AppState.batchRecords = data.records || [];
    filterAndRenderRecords();

    // Update source counts
    const bankCount = AppState.batchRecords.filter(r => r.source_type === 'BANK').length;
    const gatewayCount = AppState.batchRecords.filter(r => r.source_type === 'GATEWAY').length;
    const invoiceCount = AppState.batchRecords.filter(r => r.source_type === 'INVOICE').length;

    setText('source-count-bank', `${bankCount} Records`);
    setText('source-count-gateway', `${gatewayCount} Records`);
    setText('source-count-invoice', `${invoiceCount} Records`);
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

function filterAndRenderRecords() {
  let list = AppState.batchRecords;

  if (AppState.sourceFilter !== 'ALL') {
    list = list.filter(r => r.source_type === AppState.sourceFilter);
  }

  if (AppState.searchQuery) {
    const q = AppState.searchQuery.toLowerCase();
    list = list.filter(r => 
      (r.raw_entity_name && r.raw_entity_name.toLowerCase().includes(q)) ||
      (r.normalized_entity_name && r.normalized_entity_name.toLowerCase().includes(q)) ||
      (r.reference_code && r.reference_code.toLowerCase().includes(q)) ||
      (r.amount && r.amount.toString().includes(q))
    );
  }

  AppState.filteredRecords = list;
  renderRecordsTable(list);
}

function renderRecordsTable(records) {
  const tbody = document.getElementById('records-table-body');
  if (!tbody) return;

  if (records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">No matching financial records found.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => `
    <tr>
      <td>
        <div style="font-weight:600; color:var(--text-primary);">${escapeHtml(r.normalized_entity_name || r.raw_entity_name)}</div>
        <div style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(r.raw_entity_name)}</div>
      </td>
      <td><span class="badge ${getSourceBadgeClass(r.source_type)}">${r.source_type}</span></td>
      <td><span style="font-family:var(--font-mono); font-size:0.8125rem;">${escapeHtml(r.reference_code || 'MISSING')}</span></td>
      <td style="font-weight:700; font-family:var(--font-mono); color:var(--text-primary);">${formatINR(r.amount)}</td>
      <td style="color:var(--text-secondary); font-size:0.8125rem;">${formatDate(r.transaction_date)}</td>
      <td><span class="badge ${getStatusBadgeClass(r.status)}">${r.status}</span></td>
      <td>
        <button class="btn btn-outline btn-sm" onclick="openRecordMetadataModal('${r.record_id}')">
          <span>Metadata</span>
        </button>
      </td>
    </tr>
  `).join('');
}

function getSourceBadgeClass(st) {
  if (st === 'BANK') return 'badge-info';
  if (st === 'GATEWAY') return 'badge-success';
  if (st === 'INVOICE') return 'badge-warning';
  return 'badge-neutral';
}

function getStatusBadgeClass(st) {
  if (st === 'MATCHED' || st === 'RESOLVED') return 'badge-success';
  if (st === 'EXCEPTION') return 'badge-danger';
  return 'badge-neutral';
}

// ---------------------------------------------------------------------------
// Exceptions Workbench
// ---------------------------------------------------------------------------
async function loadExceptionsData() {
  if (!AppState.activeBatchId) return;

  try {
    const data = await API.getExceptions(AppState.activeBatchId, AppState.exceptionRiskFilter);
    AppState.exceptions = data.items || [];
    AppState.filteredExceptions = AppState.exceptions;

    // Update risk counts
    const high = AppState.exceptions.filter(e => e.risk_score === 'HIGH').length;
    const med = AppState.exceptions.filter(e => e.risk_score === 'MEDIUM').length;
    const low = AppState.exceptions.filter(e => e.risk_score === 'LOW').length;

    setText('exc-count-all', AppState.exceptions.length);
    setText('exc-count-high', high);
    setText('exc-count-med', med);
    setText('exc-count-low', low);

    renderExceptionsTable();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

function renderExceptionsTable() {
  const tbody = document.getElementById('exceptions-table-body');
  if (!tbody) return;

  const items = AppState.filteredExceptions;

  if (items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:32px; color:var(--text-muted);">No exceptions found for this filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(ex => `
    <tr style="cursor:pointer;" onclick="openExceptionDrawer('${ex.exception_id}')">
      <td><span style="font-family:var(--font-mono); font-size:0.775rem;">${truncateId(ex.exception_id)}</span></td>
      <td>
        <div style="font-weight:600;">${escapeHtml(ex.entity_name || 'Unmapped')}</div>
        <div style="font-size:0.75rem; color:var(--text-muted);">${ex.source_type} • ${formatDate(ex.transaction_date)}</div>
      </td>
      <td style="font-weight:700; font-family:var(--font-mono);">${formatINR(ex.amount)}</td>
      <td><span class="badge ${ex.risk_score === 'HIGH' ? 'badge-danger' : ex.risk_score === 'MEDIUM' ? 'badge-warning' : 'badge-success'}">${ex.risk_score}</span></td>
      <td style="max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(ex.ai_diagnosis || 'Pending diagnosis')}">
        <span style="color:var(--text-secondary); font-size:0.8125rem;">${escapeHtml(ex.ai_diagnosis || 'Pending AI Diagnosis...')}</span>
      </td>
      <td><span class="badge badge-neutral" style="font-size:0.75rem;">${escapeHtml(ex.recommended_action || 'Review')}</span></td>
      <td><span class="badge ${ex.status === 'APPROVED' ? 'badge-success' : ex.status === 'REJECTED' ? 'badge-danger' : 'badge-warning'}">${ex.status}</span></td>
      <td onclick="event.stopPropagation();">
        <div class="exception-row-btn-group">
          ${ex.drafted_journal_entry ? `
            <button class="btn btn-outline btn-sm" title="Preview Journal Entry" onclick="openJournalModal('${ex.exception_id}')">
              <span>📓</span>
            </button>
          ` : ''}
          <button class="btn btn-success btn-sm" ${ex.status !== 'PENDING' ? 'disabled' : ''} onclick="handleApproveException('${ex.exception_id}')">
            <span>✓ Approve & Rule</span>
          </button>
          <button class="btn btn-danger btn-sm" ${ex.status !== 'PENDING' ? 'disabled' : ''} onclick="handleRejectException('${ex.exception_id}')">
            <span>✕</span>
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

async function handleDiagnoseAll() {
  if (!AppState.activeBatchId) return;

  const btn = document.getElementById('btn-diagnose-all');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>🤖 Analyzing with AI...</span>`;
  }
  showToast('Running AI root-cause diagnostic agent on all exceptions...', 'info');

  try {
    const res = await API.diagnoseAllExceptions(AppState.activeBatchId);
    showToast(`Diagnosed ${res.diagnosed_count} exceptions! Generated root cause and accounting entries.`, 'success');
    await loadExceptionsData();
  } catch (err) {
    showToast(err.message, 'danger');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>🤖 Diagnose All with AI</span>`;
    }
  }
}

async function handleApproveException(exceptionId) {
  try {
    const res = await API.handleExceptionAction(exceptionId, 'APPROVE', true, 'Controller Abhi');
    showToast(`Exception Approved! ${res.rule_synthesized ? `Synthesized DynamicRule: "${res.rule_name}"` : ''}`, 'success');
    await loadExceptionsData();
    await refreshOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function handleRejectException(exceptionId) {
  try {
    await API.handleExceptionAction(exceptionId, 'REJECT', false, 'Controller Abhi');
    showToast('Exception rejected and flagged for secondary review.', 'warning');
    await loadExceptionsData();
    await refreshOverview();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

// ---------------------------------------------------------------------------
// 30-Day Cash Forecasting & What-If Stress Simulator
// ---------------------------------------------------------------------------
async function loadForecastData() {
  if (!AppState.activeBatchId) return;

  try {
    const startDate = document.getElementById('forecast-start-date')?.value || null;
    const forecast = await API.getRunwayForecast(AppState.activeBatchId, startDate);
    AppState.forecastBaseline = forecast;

    // Update KPI Cards
    setText('forecast-kpi-current', formatINR(forecast.baseline_cash));
    const day30 = forecast.daily_projection[forecast.daily_projection.length - 1];
    setText('forecast-kpi-projected', formatINR(day30?.projected_balance || 0));
    setText('forecast-kpi-min', formatINR(forecast.liquidity_risk.min_projected_balance));
    
    const d2z = forecast.liquidity_risk.days_to_zero;
    setText('forecast-kpi-d2z', d2z !== null ? `${d2z} Days` : 'Safe (Never)');
    
    const healthBadge = document.getElementById('forecast-kpi-health');
    if (healthBadge) {
      healthBadge.textContent = forecast.liquidity_risk.risk_level;
      healthBadge.className = `badge badge-${forecast.liquidity_risk.risk_level === 'HEALTHY' ? 'success' : forecast.liquidity_risk.risk_level === 'CAUTION' ? 'warning' : 'danger'}`;
    }

    renderForecastChart(forecast.daily_projection);
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

function renderForecastChart(dailyPoints, simulatedPoints = null) {
  const canvas = document.getElementById('cash-runway-chart');
  if (!canvas || typeof Chart === 'undefined') return;

  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const gridColor = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)';
  const textColor = isLight ? '#475569' : '#94a3b8';

  const labels = dailyPoints.map(d => {
    const parts = d.date.split('-');
    return `${parts[2]}/${parts[1]}`;
  });

  const baselineData = dailyPoints.map(d => d.projected_balance);

  const datasets = [
    {
      label: 'Baseline 30-Day Runway (₹)',
      data: baselineData,
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99, 102, 241, 0.1)',
      borderWidth: 3,
      fill: true,
      tension: 0.35,
      pointRadius: 3,
      pointHoverRadius: 6,
    }
  ];

  if (simulatedPoints) {
    const simData = simulatedPoints.map(d => d.simulated_balance || d.projected_balance);
    datasets.push({
      label: 'What-If Stressed Runway (₹)',
      data: simData,
      borderColor: '#ef4444',
      backgroundColor: 'rgba(239, 68, 68, 0.08)',
      borderWidth: 3,
      borderDash: [6, 4],
      fill: true,
      tension: 0.35,
      pointRadius: 3,
      pointHoverRadius: 6,
    });
  }

  if (AppState.runwayChart) {
    AppState.runwayChart.destroy();
  }

  AppState.runwayChart = new Chart(canvas, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: textColor, font: { family: 'Outfit', weight: '600' } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${formatINR(ctx.raw)}`
          }
        }
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor, font: { family: 'JetBrains Mono', size: 11 } }
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            font: { family: 'JetBrains Mono', size: 11 },
            callback: (val) => `₹${(val / 1000).toFixed(0)}k`
          }
        }
      }
    }
  });
}

async function handleRunSimulation() {
  if (!AppState.activeBatchId) return;

  const delayDays = parseInt(document.getElementById('sim-delay-slider')?.value || '0', 10);
  const defaultRate = parseFloat(document.getElementById('sim-default-slider')?.value || '0') / 100;
  const feeSurge = parseFloat(document.getElementById('sim-fee-slider')?.value || '0') / 100;

  const btn = document.getElementById('btn-run-simulation');
  if (btn) btn.disabled = true;

  try {
    const sim = await API.runSimulation({
      batch_id: AppState.activeBatchId,
      delay_days: delayDays,
      default_rate: defaultRate,
      gateway_fee_surge: feeSurge
    });

    AppState.forecastSimulated = sim;

    // Render dual curves
    renderForecastChart(AppState.forecastBaseline.daily_projection, sim.time_series);

    // Update Delta Box
    setText('sim-delta-variance', formatINR(sim.delta?.net_cash_variance));
    setText('sim-delta-min', formatINR(sim.simulated_summary?.min_cash));
    setText('sim-delta-d2z', sim.simulated_summary?.days_to_zero !== null ? `${sim.simulated_summary.days_to_zero} Days` : 'Safe');
    setText('sim-scenario-insight', sim.summary || 'Stress scenario calculated successfully.');

    showToast('What-If Stress Scenario plotted alongside baseline!', 'success');
  } catch (err) {
    showToast(err.message, 'danger');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function handleResetSimulation() {
  document.getElementById('sim-delay-slider').value = 0;
  document.getElementById('sim-default-slider').value = 0;
  document.getElementById('sim-fee-slider').value = 0;
  
  setText('sim-delay-val', '0 Days');
  setText('sim-default-val', '0%');
  setText('sim-fee-val', '0%');

  if (AppState.forecastBaseline) {
    renderForecastChart(AppState.forecastBaseline.daily_projection);
  }
  
  setText('sim-delta-variance', '₹0.00');
  setText('sim-delta-min', '—');
  setText('sim-delta-d2z', '—');
  setText('sim-scenario-insight', 'Adjust the sliders above to stress-test collection delays, defaults, and fee surges.');

  showToast('Simulation parameters reset to baseline', 'info');
}

// ---------------------------------------------------------------------------
// Audit Trail & Export
// ---------------------------------------------------------------------------
async function loadAuditData() {
  if (!AppState.activeBatchId) return;

  const actionFilter = document.getElementById('audit-action-filter')?.value || 'ALL';

  try {
    const data = await API.getAuditTrail(AppState.activeBatchId, actionFilter);
    AppState.auditEvents = data.events || [];

    // KPI Counters
    const system = AppState.auditEvents.filter(e => e.actor.includes('SYSTEM') || e.actor.includes('RECONCILER')).length;
    const human = AppState.auditEvents.filter(e => e.actor.includes('HUMAN') || e.actor.includes('CONTROLLER')).length;
    const ai = AppState.auditEvents.filter(e => e.actor.includes('DIAGNOSTIC') || e.actor.includes('AGENT') || e.actor.includes('COPILOT')).length;

    setText('audit-kpi-total', data.total_events || AppState.auditEvents.length);
    setText('audit-kpi-system', system);
    setText('audit-kpi-human', human);
    setText('audit-kpi-ai', ai);

    renderAuditTable();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

function renderAuditTable() {
  const tbody = document.getElementById('audit-table-body');
  if (!tbody) return;

  const events = AppState.auditEvents;

  if (events.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">No audit events recorded for this selection.</td></tr>`;
    return;
  }

  tbody.innerHTML = events.map(e => `
    <tr>
      <td style="font-family:var(--font-mono); font-size:0.775rem; color:var(--text-secondary);">
        ${new Date(e.created_at).toLocaleString()}
      </td>
      <td><span class="badge ${getEventBadgeClass(e.action_type)}">${e.action_type}</span></td>
      <td><span class="badge badge-neutral">${e.actor}</span></td>
      <td style="font-family:var(--font-mono); font-size:0.8125rem;">${e.confidence_score ? `${(e.confidence_score * 100).toFixed(0)}%` : '—'}</td>
      <td style="max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(e.reasoning_snapshot || '')}">
        ${escapeHtml(e.reasoning_snapshot || 'State update logged')}
      </td>
      <td>
        <button class="btn btn-outline btn-sm" onclick="openAuditDiffModal('${e.audit_id}')">
          <span>Diff & Details</span>
        </button>
      </td>
    </tr>
  `).join('');
}

function exportAudit(format) {
  if (!AppState.activeBatchId) {
    showToast('Please generate or select an active batch first', 'warning');
    return;
  }
  const url = API.getAuditExportUrl(AppState.activeBatchId, format);
  window.open(url, '_blank');
  showToast(`Downloading immutable audit package (${format.toUpperCase()})...`, 'success');
}

// ---------------------------------------------------------------------------
// AI Finance Copilot Drawer & Chat
// ---------------------------------------------------------------------------
function toggleCopilotDrawer(open = null) {
  const drawer = document.getElementById('copilot-drawer');
  if (!drawer) return;

  if (open === null) {
    drawer.classList.toggle('open');
  } else if (open) {
    drawer.classList.add('open');
  } else {
    drawer.classList.remove('open');
  }

  if (drawer.classList.contains('open')) {
    document.getElementById('copilot-input')?.focus();
  }
}

async function handleSendCopilotMessage(customPrompt = null) {
  if (!AppState.activeBatchId) {
    showToast('Please select or generate a batch to enable Copilot', 'warning');
    return;
  }

  const input = document.getElementById('copilot-input');
  const query = customPrompt || input.value.trim();
  if (!query) return;

  if (!customPrompt && input) input.value = '';

  // Add user bubble
  appendChatBubble('user', query);

  // Add thinking placeholder
  const placeholderId = 'ai-typing-' + Date.now();
  appendChatBubble('ai', `<em>AI Controller is analyzing batch context...</em>`, placeholderId);

  try {
    const res = await API.askCopilot(AppState.activeBatchId, query);
    const placeholder = document.getElementById(placeholderId);
    if (placeholder) {
      placeholder.innerHTML = `
        <div style="font-weight:600; margin-bottom:4px; display:flex; align-items:center; justify-content:space-between;">
          <span>LedgerIQ AI</span>
          <span style="font-size:0.7rem; color:var(--text-muted);">${res.model || 'kimi-k2.6'}</span>
        </div>
        <div>${formatMarkdown(res.reply)}</div>
        ${res.sources && res.sources.length ? `
          <div style="margin-top:8px; padding-top:6px; border-top:1px solid var(--border-color); font-size:0.75rem; color:var(--text-muted);">
            <strong>Sources:</strong> ${res.sources.map(s => `<span class="badge badge-neutral" style="font-size:0.65rem; margin-right:4px;">${s.type}: ${escapeHtml(s.identifier)}</span>`).join('')}
          </div>
        ` : ''}
      `;
    }
  } catch (err) {
    const placeholder = document.getElementById(placeholderId);
    if (placeholder) {
      placeholder.innerHTML = `<span style="color:var(--danger)">Error: ${escapeHtml(err.message)}</span>`;
    }
  }
}

function appendChatBubble(role, html, id = null) {
  const container = document.getElementById('copilot-messages');
  if (!container) return;

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble chat-bubble-${role}`;
  if (id) bubble.id = id;
  bubble.innerHTML = html;
  container.appendChild(bubble);

  container.scrollTop = container.scrollHeight;
}

function clearChatHistory() {
  const container = document.getElementById('copilot-messages');
  if (!container) return;
  container.innerHTML = `
    <div class="chat-bubble chat-bubble-ai">
      <strong>Hello, I'm LedgerIQ Copilot.</strong><br>
      I have full real-time awareness of the current financial batch. Ask me about reconciliation anomalies, missing invoices, fee discrepancies, or forward cash runway projections.
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Modals & Drawers Helpers
// ---------------------------------------------------------------------------
function openRecordMetadataModal(recordId) {
  const record = AppState.batchRecords.find(r => r.record_id === recordId);
  if (!record) return;

  const modal = document.getElementById('record-metadata-modal');
  const body = document.getElementById('record-metadata-content');
  if (!modal || !body) return;

  body.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:16px;">
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
        <div><strong>Record ID:</strong> <span style="font-family:var(--font-mono); font-size:0.8rem;">${record.record_id}</span></div>
        <div><strong>Source:</strong> <span class="badge ${getSourceBadgeClass(record.source_type)}">${record.source_type}</span></div>
        <div><strong>Raw Entity:</strong> ${escapeHtml(record.raw_entity_name)}</div>
        <div><strong>Normalized:</strong> ${escapeHtml(record.normalized_entity_name || 'None')}</div>
        <div><strong>Amount:</strong> <span style="font-weight:700;">${formatINR(record.amount)}</span></div>
        <div><strong>Date:</strong> ${formatDate(record.transaction_date)}</div>
      </div>
      <div>
        <strong>Injected Anomaly & Technical Metadata:</strong>
        <pre style="background:var(--bg-primary); padding:12px; border-radius:var(--radius-md); font-family:var(--font-mono); font-size:0.8125rem; overflow-x:auto; margin-top:6px;">${JSON.stringify(record.metadata_json || {}, null, 2)}</pre>
      </div>
    </div>
  `;
  modal.classList.add('open');
}

function openJournalModal(exceptionId) {
  const ex = AppState.exceptions.find(e => e.exception_id === exceptionId);
  if (!ex || !ex.drafted_journal_entry) return;

  const modal = document.getElementById('journal-entry-modal');
  const body = document.getElementById('journal-entry-content');
  if (!modal || !body) return;

  const j = ex.drafted_journal_entry;
  body.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:16px;">
      <div style="font-size:0.875rem; color:var(--text-secondary);">
        AI Drafted Double-Entry Accounting Adjustment for <strong>${escapeHtml(ex.entity_name || 'Transaction')}</strong>:
      </div>
      <div style="background:var(--bg-tertiary); padding:16px; border-radius:var(--radius-md); border:1px solid var(--border-color); display:flex; flex-direction:column; gap:10px;">
        <div style="display:flex; justify-content:space-between;">
          <span style="font-weight:600; color:var(--text-muted);">DEBIT ACCOUNT:</span>
          <span style="font-weight:700; color:var(--success); font-family:var(--font-mono);">${escapeHtml(j.debit_account || 'Suspense')}</span>
        </div>
        <div style="display:flex; justify-content:space-between;">
          <span style="font-weight:600; color:var(--text-muted);">CREDIT ACCOUNT:</span>
          <span style="font-weight:700; color:var(--accent-cyan); font-family:var(--font-mono);">${escapeHtml(j.credit_account || 'Suspense')}</span>
        </div>
        <div style="display:flex; justify-content:space-between;">
          <span style="font-weight:600; color:var(--text-muted);">AMOUNT:</span>
          <span style="font-weight:800; font-family:var(--font-mono); font-size:1.125rem;">${formatINR(j.amount || ex.amount)}</span>
        </div>
        <div style="display:flex; justify-content:space-between;">
          <span style="font-weight:600; color:var(--text-muted);">MEMO / REASON:</span>
          <span style="font-size:0.8125rem;">${escapeHtml(j.memo || ex.ai_diagnosis || 'Automated Adjustment')}</span>
        </div>
      </div>
    </div>
  `;
  modal.classList.add('open');
}

function openAuditDiffModal(auditId) {
  const event = AppState.auditEvents.find(e => e.audit_id === auditId);
  if (!event) return;

  const modal = document.getElementById('audit-diff-modal');
  const body = document.getElementById('audit-diff-content');
  if (!modal || !body) return;

  body.innerHTML = `
    <div style="display:flex; flex-direction:column; gap:16px;">
      <div>
        <strong>Action:</strong> <span class="badge ${getEventBadgeClass(event.action_type)}">${event.action_type}</span>
        <span style="margin-left:12px;"><strong>Actor:</strong> ${event.actor}</span>
      </div>
      <div>
        <strong>Reasoning Snapshot:</strong>
        <p style="background:var(--bg-tertiary); padding:10px 14px; border-radius:var(--radius-md); font-size:0.875rem; margin-top:6px;">
          ${escapeHtml(event.reasoning_snapshot || 'No reasoning snapshot recorded.')}
        </p>
      </div>
      <div>
        <strong>State Changes / Diff Payload:</strong>
        <pre style="background:var(--bg-primary); padding:12px; border-radius:var(--radius-md); font-family:var(--font-mono); font-size:0.8125rem; overflow-x:auto; margin-top:6px;">${JSON.stringify(event.changes_payload || {}, null, 2)}</pre>
      </div>
    </div>
  `;
  modal.classList.add('open');
}

function openHowItWorksModal() {
  const modal = document.getElementById('how-it-works-modal');
  if (modal) modal.classList.add('open');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('open');
}

// ---------------------------------------------------------------------------
// Theme Toggle (Dark / Light)
// ---------------------------------------------------------------------------
function toggleTheme() {
  const newTheme = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('ledgeriq_theme', newTheme);
  AppState.theme = newTheme;

  // Update Three.js background colors if available
  if (window.threeVisualizer) {
    window.threeVisualizer.updateThemeColors(newTheme === 'light');
  }

  // Redraw chart if open
  if (AppState.forecastBaseline && AppState.currentTab === 'forecast') {
    renderForecastChart(AppState.forecastBaseline.daily_projection, AppState.forecastSimulated?.time_series);
  }
}

// ---------------------------------------------------------------------------
// Helper Utilities
// ---------------------------------------------------------------------------
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

// ---------------------------------------------------------------------------
// DOM Event Listeners & Bootstrapping
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // Apply initial theme
  document.documentElement.setAttribute('data-theme', AppState.theme);

  // Initialize Three.js WebGL Particle Network on Landing Page
  if (typeof FinanceNetworkVisualizer !== 'undefined') {
    window.threeVisualizer = new FinanceNetworkVisualizer('three-canvas-container');
  }

  // Initialize Animated Sequential Title on Landing Page
  initSequentialTitle();

  // Landing Page Buttons
  document.getElementById('btn-enter-app')?.addEventListener('click', () => {
    document.getElementById('landing-page')?.classList.add('hidden');
    switchTab('overview');
  });

  document.getElementById('btn-explore-flow')?.addEventListener('click', openHowItWorksModal);

  // Theme Toggles
  document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
    btn.addEventListener('click', toggleTheme);
  });

  // Navigation Tabs
  document.querySelectorAll('.nav-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.getAttribute('data-tab')));
  });

  // Global Health & Copilot
  document.getElementById('system-health-pill')?.addEventListener('click', checkSystemHealth);
  document.getElementById('btn-open-copilot')?.addEventListener('click', () => toggleCopilotDrawer(true));
  document.getElementById('btn-close-copilot')?.addEventListener('click', () => toggleCopilotDrawer(false));
  document.getElementById('btn-clear-chat')?.addEventListener('click', clearChatHistory);
  document.getElementById('btn-send-copilot')?.addEventListener('click', () => handleSendCopilotMessage());
  
  document.getElementById('copilot-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleSendCopilotMessage();
  });

  // Copilot Quick Prompt Chips
  document.querySelectorAll('.chip-btn').forEach(chip => {
    chip.addEventListener('click', () => {
      handleSendCopilotMessage(chip.getAttribute('data-prompt'));
    });
  });

  // Ingestion / Batch Controls
  document.getElementById('btn-generate-batch')?.addEventListener('click', handleGenerateBatch);
  document.getElementById('btn-overview-generate')?.addEventListener('click', handleGenerateBatch);
  document.getElementById('btn-overview-load-sample')?.addEventListener('click', handleLoadSampleData);
  document.getElementById('btn-run-reconciliation')?.addEventListener('click', handleRunReconciliation);
  document.getElementById('btn-refresh-summary')?.addEventListener('click', refreshOverview);
  document.getElementById('btn-overview-view-forecast')?.addEventListener('click', () => switchTab('forecast'));

  // NeatLogs Telemetry Stream Controls
  document.getElementById('btn-neatlogs-refresh')?.addEventListener('click', loadNeatLogs);
  document.getElementById('btn-neatlogs-clear')?.addEventListener('click', handleClearNeatLogs);
  document.getElementById('neatlogs-search-input')?.addEventListener('input', loadNeatLogs);
  document.getElementById('neatlogs-category-filter')?.addEventListener('change', loadNeatLogs);

  // Source Filters on Reconciliation Center
  document.querySelectorAll('.source-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.source-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      AppState.sourceFilter = btn.getAttribute('data-source');
      filterAndRenderRecords();
    });
  });

  // Record Search Input
  document.getElementById('search-records-input')?.addEventListener('input', (e) => {
    AppState.searchQuery = e.target.value.trim();
    filterAndRenderRecords();
  });

  // Exception Risk Filters
  document.querySelectorAll('.risk-filter-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.risk-filter-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      AppState.exceptionRiskFilter = card.getAttribute('data-risk');
      loadExceptionsData();
    });
  });

  document.getElementById('btn-diagnose-all')?.addEventListener('click', handleDiagnoseAll);

  // Forecast & What-If Simulator
  document.getElementById('btn-compute-forecast')?.addEventListener('click', loadForecastData);
  document.getElementById('forecast-start-date')?.addEventListener('change', loadForecastData);
  document.getElementById('btn-run-simulation')?.addEventListener('click', handleRunSimulation);
  document.getElementById('btn-reset-simulation')?.addEventListener('click', handleResetSimulation);

  // Sliders Live Labels
  document.getElementById('sim-delay-slider')?.addEventListener('input', (e) => {
    setText('sim-delay-val', `${e.target.value} Days`);
  });
  document.getElementById('sim-default-slider')?.addEventListener('input', (e) => {
    setText('sim-default-val', `${e.target.value}%`);
  });
  document.getElementById('sim-fee-slider')?.addEventListener('input', (e) => {
    setText('sim-fee-val', `${e.target.value}%`);
  });

  // Audit Actions
  document.getElementById('btn-load-audit')?.addEventListener('click', loadAuditData);
  document.getElementById('audit-action-filter')?.addEventListener('change', loadAuditData);
  document.getElementById('btn-export-audit-json')?.addEventListener('click', () => exportAudit('json'));
  document.getElementById('btn-export-audit-csv')?.addEventListener('click', () => exportAudit('csv'));

  // Close Modals on click outside or close buttons
  document.querySelectorAll('.modal-close-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-backdrop');
      if (modal) modal.classList.remove('open');
    });
  });

  document.querySelectorAll('.modal-backdrop').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open');
    });
  });

  // Initial Boot
  checkSystemHealth();
  updateBatchSelector();
});

// Expose globals for onclick HTML handlers
window.openRecordMetadataModal = openRecordMetadataModal;
window.openJournalModal = openJournalModal;
window.openAuditDiffModal = openAuditDiffModal;
window.handleApproveException = handleApproveException;
window.handleRejectException = handleRejectException;
window.closeModal = closeModal;
