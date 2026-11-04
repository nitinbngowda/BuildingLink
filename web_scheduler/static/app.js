// CronMaster Client-side Application Logic

let activeTab = 'jobs';
let currentJobs = [];
let preferredTimes = [];
let liveLogPollTimer = null;
let currentModalHistoryId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  updateClock();
  setInterval(updateClock, 1000);

  loadSystemMetrics();
  loadJobs();
  loadHistory();
  loadBLConfig();

  // Enter key support for preferred times input
  const timeInput = document.getElementById('newTimeInput');
  if (timeInput) {
    timeInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        addPreferredTime();
      }
    });
  }

  // Polling for live status every 4 seconds
  setInterval(() => {
    loadSystemMetrics();
    if (activeTab === 'jobs') loadJobs(false);
    if (activeTab === 'history') loadHistory(false);
  }, 4000);
});

function updateClock() {
  const clockEl = document.getElementById('serverClock');
  if (clockEl) {
    const now = new Date();
    clockEl.textContent = now.toTimeString().split(' ')[0] + ' (Local)';
  }
}

// ==========================================
// TABS NAVIGATION
// ==========================================
function switchTab(tab) {
  activeTab = tab;
  
  const tabs = {
    jobs: {
      section: document.getElementById('tabJobs'),
      button: document.getElementById('tabBtnJobs')
    },
    history: {
      section: document.getElementById('tabHistory'),
      button: document.getElementById('tabBtnHistory')
    },
    buildinglink: {
      section: document.getElementById('tabBuildingLink'),
      button: document.getElementById('tabBtnBL')
    }
  };

  for (const [key, item] of Object.entries(tabs)) {
    if (!item.section || !item.button) continue;
    if (key === tab) {
      item.section.classList.remove('hidden');
      item.button.classList.add('text-brand-400', 'border-brand-500');
      item.button.classList.remove('text-slate-400', 'border-transparent');
    } else {
      item.section.classList.add('hidden');
      item.button.classList.remove('text-brand-400', 'border-brand-500');
      item.button.classList.add('text-slate-400', 'border-transparent');
    }
  }

  if (tab === 'jobs') loadJobs();
  if (tab === 'history') loadHistory();
  if (tab === 'buildinglink') loadBLConfig();
  if (window.lucide) lucide.createIcons();
}

// ==========================================
// SYSTEM METRICS
// ==========================================
async function loadSystemMetrics() {
  try {
    const res = await fetch('/api/system');
    const data = await res.json();
    document.getElementById('statActiveJobs').textContent = `${data.active_jobs} / ${data.total_jobs}`;
    document.getElementById('statTotalRuns').textContent = data.total_runs;
    document.getElementById('statSuccessRate').textContent = `${data.success_rate}%`;

    const nextEl = document.getElementById('statNextRun');
    const nextDescEl = document.getElementById('statNextRunDesc');
    if (data.next_scheduled_run) {
      const dt = new Date(data.next_scheduled_run);
      nextEl.textContent = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      nextDescEl.textContent = dt.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } else {
      nextEl.textContent = 'None scheduled';
      nextDescEl.textContent = 'Enable a job to schedule';
    }
  } catch (err) {
    console.error('Failed to load system metrics', err);
  }
}

// ==========================================
// JOBS MANAGEMENT
// ==========================================
async function loadJobs(showLoading = true) {
  const container = document.getElementById('jobsList');
  if (showLoading && currentJobs.length === 0) {
    container.innerHTML = '<div class="p-8 text-center text-slate-500 text-xs">Loading jobs...</div>';
  }

  try {
    const res = await fetch('/api/jobs');
    const jobs = await res.json();
    currentJobs = jobs;

    const countBadge = document.getElementById('jobsCountBadge');
    if (countBadge) countBadge.textContent = jobs.length;

    if (!jobs || jobs.length === 0) {
      container.innerHTML = `
        <div class="bg-surface-900 border border-slate-800 rounded-2xl p-12 text-center text-slate-400">
          <i data-lucide="layers" class="w-10 h-10 mx-auto text-slate-600 mb-3"></i>
          <p class="font-medium">No scheduled jobs found</p>
          <p class="text-xs text-slate-500 mt-1">Click "+ New Job" to create your first scheduler</p>
        </div>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    container.innerHTML = jobs.map(job => renderJobCard(job)).join('');
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs">Failed to load jobs: ${err.message}</div>`;
  }
}

function renderJobCard(job) {
  const isRunning = job.last_status === 'running';
  const isSuccess = job.last_status === 'success';
  const isFailed = job.last_status === 'failed';

  let statusBadge = '';
  if (isRunning) {
    statusBadge = `
      <span class="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-medium bg-blue-500/15 text-blue-400 border border-blue-500/30">
        <span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping"></span>
        <span>Running...</span>
      </span>
    `;
  } else if (isSuccess) {
    statusBadge = `
      <span class="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
        <i data-lucide="check" class="w-3 h-3"></i>
        <span>Success (${job.last_duration}s)</span>
      </span>
    `;
  } else if (isFailed) {
    statusBadge = `
      <span class="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30">
        <i data-lucide="alert-circle" class="w-3 h-3"></i>
        <span>Failed</span>
      </span>
    `;
  } else {
    statusBadge = `
      <span class="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
        <span>Never run</span>
      </span>
    `;
  }

  const nextRunFormatted = job.next_run_at 
    ? new Date(job.next_run_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Disabled';

  return `
    <div class="bg-surface-900 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 shadow-sm transition">
      <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        
        <!-- Job Info -->
        <div class="space-y-2 flex-1 min-w-0">
          <div class="flex flex-wrap items-center gap-3">
            <h3 class="font-semibold text-sm text-white">${escapeHtml(job.name)}</h3>
            ${statusBadge}
            <span class="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-md text-[11px] font-mono bg-surface-950 text-brand-300 border border-brand-500/20">
              <i data-lucide="clock" class="w-3 h-3"></i>
              <span>${escapeHtml(job.human_schedule)}</span>
            </span>
          </div>

          ${job.description ? `<p class="text-xs text-slate-400 line-clamp-2">${escapeHtml(job.description)}</p>` : ''}

          <!-- Command Display -->
          <div class="flex items-center space-x-2 bg-[#090d16] border border-slate-800/80 rounded-lg px-3 py-1.5 font-mono text-[11px] text-slate-300 max-w-2xl overflow-hidden">
            <span class="text-brand-400 font-bold">$</span>
            <span class="truncate flex-1">${escapeHtml(job.command)}</span>
          </div>

          <div class="flex flex-wrap items-center gap-4 text-[11px] text-slate-500 pt-1">
            <span>Next Run: <strong class="text-slate-300 font-medium">${nextRunFormatted}</strong></span>
            ${job.last_run_at ? `<span>Last Run: <strong class="text-slate-300 font-medium">${new Date(job.last_run_at).toLocaleString()}</strong></span>` : ''}
          </div>
        </div>

        <!-- Controls: On/Off Switch & Action Buttons -->
        <div class="flex items-center justify-between lg:justify-end gap-3 pt-3 lg:pt-0 border-t lg:border-t-0 border-slate-800/60">
          
          <!-- On / Off Switch -->
          <div class="flex items-center space-x-2 mr-2">
            <span class="text-xs font-medium ${job.enabled ? 'text-emerald-400' : 'text-slate-500'}">
              ${job.enabled ? 'Active' : 'Off'}
            </span>
            <label class="switch">
              <input type="checkbox" ${job.enabled ? 'checked' : ''} onchange="toggleJob(${job.id})">
              <span class="slider"></span>
            </label>
          </div>

          <!-- Run Now Button -->
          <button onclick="runJobNow(${job.id})" ${isRunning ? 'disabled' : ''} class="px-3 py-1.5 bg-brand-600/10 hover:bg-brand-600/20 text-brand-400 border border-brand-500/20 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition active:scale-95 disabled:opacity-50">
            <i data-lucide="${isRunning ? 'loader-2' : 'play'}" class="w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}"></i>
            <span>${isRunning ? 'Running...' : 'Run Now'}</span>
          </button>

          <!-- View Latest Log -->
          <button onclick="viewLatestLogForJob(${job.id}, '${escapeHtml(job.name)}')" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition">
            <i data-lucide="file-text" class="w-3.5 h-3.5"></i>
            <span>Logs</span>
          </button>

          <!-- Edit Button -->
          <button onclick="openEditJobModal(${job.id})" class="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition" title="Edit Job">
            <i data-lucide="pencil" class="w-4 h-4"></i>
          </button>

          <!-- Delete Button -->
          <button onclick="deleteJob(${job.id}, '${escapeHtml(job.name)}')" class="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-rose-500/10 transition" title="Delete Job">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>

      </div>
    </div>
  `;
}

async function toggleJob(id) {
  try {
    const res = await fetch(`/api/jobs/${id}/toggle`, { method: 'POST' });
    const data = await res.json();
    loadJobs(false);
    loadSystemMetrics();
  } catch (err) {
    alert('Failed to toggle job: ' + err.message);
  }
}

async function runJobNow(id) {
  try {
    const res = await fetch(`/api/jobs/${id}/run`, { method: 'POST' });
    loadJobs(false);
    loadSystemMetrics();
    setTimeout(() => {
      loadJobs(false);
      loadHistory(false);
    }, 1200);
  } catch (err) {
    alert('Failed to trigger job: ' + err.message);
  }
}

async function deleteJob(id, name) {
  if (!confirm(`Are you sure you want to delete job "${name}"?`)) return;
  try {
    await fetch(`/api/jobs/${id}`, { method: 'DELETE' });
    loadJobs();
    loadSystemMetrics();
  } catch (err) {
    alert('Failed to delete job: ' + err.message);
  }
}

// ==========================================
// RUN HISTORY & LOGS
// ==========================================
async function loadHistory(showLoading = true) {
  const tbody = document.getElementById('historyTableBody');
  const filter = document.getElementById('historyStatusFilter').value;

  try {
    const res = await fetch(`/api/history?status=${filter}&limit=40`);
    const history = await res.json();

    if (!history || history.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="px-5 py-8 text-center text-slate-500">No run history found</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = history.map(item => {
      const isRunning = item.status === 'running';
      const isSuccess = item.status === 'success';
      const isFailed = item.status === 'failed';
      const isTimeout = item.status === 'timeout';

      let badge = '';
      if (isRunning) {
        badge = '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/15 text-blue-400 border border-blue-500/30"><span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping"></span>Running</span>';
      } else if (isSuccess) {
        badge = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">Success</span>';
      } else if (isTimeout) {
        badge = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">Timeout</span>';
      } else {
        badge = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30">Failed</span>';
      }

      const startedFormatted = new Date(item.started_at).toLocaleString([], {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
      });

      return `
        <tr class="hover:bg-slate-800/30 transition">
          <td class="px-5 py-3">${badge}</td>
          <td class="px-5 py-3 font-medium text-white">${escapeHtml(item.job_name)}</td>
          <td class="px-5 py-3 text-slate-400 capitalize">${item.trigger_type}</td>
          <td class="px-5 py-3 text-slate-400 font-mono text-[11px]">${startedFormatted}</td>
          <td class="px-5 py-3 text-slate-400">${item.duration_seconds ? item.duration_seconds + 's' : '--'}</td>
          <td class="px-5 py-3 text-right">
            <button onclick="openLogModal(${item.id})" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-medium transition inline-flex items-center space-x-1">
              <i data-lucide="terminal" class="w-3 h-3"></i>
              <span>View Log</span>
            </button>
          </td>
        </tr>
      `;
    }).join('');

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-5 py-4 text-center text-rose-400">Error loading history: ${err.message}</td></tr>`;
  }
}

async function viewLatestLogForJob(jobId, jobName) {
  try {
    const res = await fetch(`/api/history?job_id=${jobId}&limit=1`);
    const history = await res.json();
    if (history && history.length > 0) {
      openLogModal(history[0].id);
    } else {
      alert(`No run logs found yet for "${jobName}". Try clicking "Run Now" first!`);
    }
  } catch (err) {
    alert('Failed to fetch latest log: ' + err.message);
  }
}

async function openLogModal(historyId) {
  currentModalHistoryId = historyId;
  const modal = document.getElementById('logModal');
  const titleEl = document.getElementById('logModalTitle');
  const subEl = document.getElementById('logModalSubtitle');
  const contentEl = document.getElementById('logModalContent');
  const badgeEl = document.getElementById('logModalStatusBadge');

  modal.classList.remove('hidden');
  contentEl.textContent = 'Loading execution output log...';

  async function fetchLog() {
    try {
      const res = await fetch(`/api/history/${historyId}`);
      const data = await res.json();

      titleEl.textContent = `${data.job_name} — Log`;
      subEl.textContent = `Run #${data.id} • Trigger: ${data.trigger_type} • Started: ${new Date(data.started_at).toLocaleString()}`;
      contentEl.textContent = data.output || '(No console output produced)';
      badgeEl.innerHTML = `Status: <strong class="text-white capitalize">${data.status}</strong> • Exit Code: ${data.exit_code !== null ? data.exit_code : '--'} • Duration: ${data.duration_seconds || '--'}s`;

      if (data.status === 'running') {
        if (!liveLogPollTimer) {
          liveLogPollTimer = setTimeout(fetchLog, 1500);
        }
      } else {
        clearTimeout(liveLogPollTimer);
        liveLogPollTimer = null;
      }
    } catch (err) {
      contentEl.textContent = 'Failed to load log: ' + err.message;
    }
  }

  fetchLog();
}

function closeLogModal() {
  document.getElementById('logModal').classList.add('hidden');
  if (liveLogPollTimer) {
    clearTimeout(liveLogPollTimer);
    liveLogPollTimer = null;
  }
  currentModalHistoryId = null;
}

function copyLogOutput() {
  const content = document.getElementById('logModalContent').textContent;
  navigator.clipboard.writeText(content).then(() => {
    const btnText = document.getElementById('copyBtnText');
    btnText.textContent = 'Copied!';
    setTimeout(() => { btnText.textContent = 'Copy'; }, 2000);
  });
}

// ==========================================
// JOB CREATE / EDIT MODAL
// ==========================================
function openNewJobModal() {
  document.getElementById('jobModalId').value = '';
  document.getElementById('jobModalTitle').textContent = 'New Scheduled Job';
  document.getElementById('jobModalName').value = '';
  document.getElementById('jobModalDesc').value = '';
  document.getElementById('jobModalCommand').value = '';
  document.getElementById('jobModalPreset').value = '0 0 * * *';
  document.getElementById('jobModalCron').value = '0 0 * * *';
  document.getElementById('jobModalWorkDir').value = '';
  document.getElementById('jobModalEnabled').checked = true;
  document.getElementById('jobModal').classList.remove('hidden');
}

function openEditJobModal(id) {
  const job = currentJobs.find(j => j.id === id);
  if (!job) return;

  document.getElementById('jobModalId').value = job.id;
  document.getElementById('jobModalTitle').textContent = 'Edit Job: ' + job.name;
  document.getElementById('jobModalName').value = job.name;
  document.getElementById('jobModalDesc').value = job.description || '';
  document.getElementById('jobModalCommand').value = job.command;
  document.getElementById('jobModalCron').value = job.cron_expression;
  document.getElementById('jobModalPreset').value = 'custom';
  document.getElementById('jobModalWorkDir').value = job.working_dir || '';
  document.getElementById('jobModalEnabled').checked = !!job.enabled;
  document.getElementById('jobModal').classList.remove('hidden');
}

function closeJobModal() {
  document.getElementById('jobModal').classList.add('hidden');
}

function applySchedulePreset() {
  const preset = document.getElementById('jobModalPreset').value;
  if (preset !== 'custom') {
    document.getElementById('jobModalCron').value = preset;
  }
}

async function saveJob(event) {
  event.preventDefault();
  const id = document.getElementById('jobModalId').value;
  const payload = {
    name: document.getElementById('jobModalName').value,
    description: document.getElementById('jobModalDesc').value,
    command: document.getElementById('jobModalCommand').value,
    cron_expression: document.getElementById('jobModalCron').value,
    working_dir: document.getElementById('jobModalWorkDir').value,
    enabled: document.getElementById('jobModalEnabled').checked
  };

  try {
    const url = id ? `/api/jobs/${id}` : '/api/jobs';
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Failed to save job');
    }
    closeJobModal();
    loadJobs();
    loadSystemMetrics();
  } catch (err) {
    alert('Error saving job: ' + err.message);
  }
}

// ==========================================
// BUILDINGLINK CONFIG TAB
// ==========================================
async function loadBLConfig() {
  try {
    const res = await fetch('/api/buildinglink/config');
    if (!res.ok) {
      throw new Error(`Server returned ${res.status}`);
    }
    const cfg = await res.json();
    document.getElementById('blUsername').value = cfg.username || '';
    document.getElementById('blPassword').value = cfg.password || '';
    document.getElementById('blAmenityId').value = cfg.amenity_id || '';
    const daysAheadEl = document.getElementById('blDaysAhead');
    if (daysAheadEl) {
      daysAheadEl.value = (cfg.days_ahead !== undefined) ? cfg.days_ahead.toString() : '1';
    }
    preferredTimes = cfg.preferred_times || ['19:00', '20:00', '18:00'];
    renderPreferredTimes();
  } catch (err) {
    console.error('Failed to load BuildingLink config', err);
  }
}

function renderPreferredTimes() {
  const container = document.getElementById('preferredTimesList');
  if (!container) return;
  if (!preferredTimes || preferredTimes.length === 0) {
    container.innerHTML = '<span class="text-xs text-slate-500 italic">No preferred times added yet. Add some below.</span>';
    return;
  }
  container.innerHTML = preferredTimes.map((time, idx) => `
    <span class="inline-flex items-center space-x-1.5 px-3 py-1 bg-brand-500/10 text-brand-300 border border-brand-500/20 rounded-lg text-xs font-mono font-medium">
      <span class="text-slate-400 font-sans text-[10px]">#${idx+1}</span>
      <span>${escapeHtml(time)}</span>
      <button type="button" onclick="removePreferredTime(${idx})" class="text-slate-400 hover:text-rose-400 ml-1">
        <i data-lucide="x" class="w-3.5 h-3.5"></i>
      </button>
    </span>
  `).join('');
  if (window.lucide) lucide.createIcons();
}

function addPreferredTime() {
  const input = document.getElementById('newTimeInput');
  const val = input.value.trim();
  if (!val) return;
  preferredTimes.push(val);
  input.value = '';
  renderPreferredTimes();
}

function removePreferredTime(index) {
  preferredTimes.splice(index, 1);
  renderPreferredTimes();
}

function togglePasswordVisibility(fieldId) {
  const f = document.getElementById(fieldId);
  f.type = f.type === 'password' ? 'text' : 'password';
}

async function saveBLConfig(event) {
  event.preventDefault();
  const payload = {
    username: document.getElementById('blUsername').value,
    password: document.getElementById('blPassword').value,
    amenity_id: document.getElementById('blAmenityId').value,
    amenity_name: "Badminton Court",
    preferred_times: preferredTimes,
    days_ahead: parseInt(document.getElementById('blDaysAhead')?.value || '1', 10),
    description: ""
  };

  try {
    const res = await fetch('/api/buildinglink/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Save failed');
    alert('BuildingLink configuration saved successfully!');
  } catch (err) {
    alert('Error saving configuration: ' + err.message);
  }
}

async function testDryRun() {
  const modal = document.getElementById('logModal');
  const titleEl = document.getElementById('logModalTitle');
  const subEl = document.getElementById('logModalSubtitle');
  const contentEl = document.getElementById('logModalContent');
  const badgeEl = document.getElementById('logModalStatusBadge');

  modal.classList.remove('hidden');
  titleEl.textContent = 'BuildingLink — Dry Run Check';
  subEl.textContent = 'Checking available badminton slots for tomorrow...';
  contentEl.textContent = 'Connecting to BuildingLink API...\nAuthenticating via PKCE...\nFetching available slots...';
  badgeEl.innerHTML = '<span class="text-blue-400 animate-pulse">Running Dry Run...</span>';

  try {
    const res = await fetch('/api/buildinglink/dry-run', { method: 'POST' });
    const data = await res.json();
    contentEl.textContent = data.output || 'No output produced';
    const isSuccess = data.exit_code === 0;
    badgeEl.innerHTML = `Status: <strong class="${isSuccess ? 'text-emerald-400' : 'text-rose-400'}">${isSuccess ? 'Success (Slots Checked)' : 'Failed'}</strong>`;
  } catch (err) {
    contentEl.textContent = 'Failed to execute dry run: ' + err.message;
    badgeEl.innerHTML = '<span class="text-rose-400">Error</span>';
  }
}

// Helpers
function escapeHtml(str) {
  if (!str) return '';
  return str.toString()
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
