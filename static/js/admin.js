let allLogs = [], allUsers = [], allSearches = [];
let activityChartInst = null, modeChartInst = null;

const ACTION_COLORS = {
  LOGIN:           { bg: 'rgba(34,197,94,0.15)',   color: '#66bb6a' },
  LOGIN_FAIL:      { bg: 'rgba(245,0,87,0.15)',    color: '#ff5722' },
  REGISTER:        { bg: 'rgba(255,107,0,0.15)',  color: '#ff9a00' },
  LOGOUT:          { bg: 'rgba(156,163,175,0.15)', color: '#9ca3af' },
  SEARCH:          { bg: 'rgba(251,191,36,0.15)',  color: '#ffa726' },
  VISIT:           { bg: 'rgba(56,189,248,0.15)',  color: '#ff9a00' },
  CHAT:            { bg: 'rgba(167,139,250,0.15)', color: '#ffb74d' },
  FORGOT_PASSWORD: { bg: 'rgba(251,191,36,0.15)',  color: '#ffa726' },
  PASSWORD_RESET:  { bg: 'rgba(34,197,94,0.15)',   color: '#66bb6a' },
  BLOCKED:         { bg: 'rgba(245,0,87,0.2)',      color: '#ff5722' },
};

function actionBadge(action) {
  const c = ACTION_COLORS[action] || { bg: 'rgba(255,255,255,0.1)', color: '#fff' };
  return `<span class="action-badge" style="background:${c.bg};color:${c.color};">${action}</span>`;
}

function fmtTime(dt) {
  if (!dt || dt === 'N/A' || dt === 'None') return '—';
  try {
    return new Date(dt).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
  } catch(e) { return '—'; }
}

function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function loadData() {
  try {
    const res  = await fetch('/admin/stats');
    const data = await res.json();

    // Stats
    document.getElementById('s-users').textContent    = data.stats.total_users;
    document.getElementById('s-logins').textContent   = data.stats.total_logins;
    document.getElementById('s-searches').textContent = data.stats.total_searches;
    document.getElementById('s-notes').textContent    = data.stats.total_notes;
    document.getElementById('s-chats').textContent    = data.stats.total_chats;
    document.getElementById('s-fails').textContent    = data.stats.total_fails;

    // Last updated
    document.getElementById('lastUpdated').textContent = 'Updated ' + new Date().toLocaleTimeString('en-IN');

    // Logs
    allLogs = data.logs;
    document.getElementById('activityCount').textContent = allLogs.length;
    filterActivity();

    // Users
    allUsers = data.users;
    document.getElementById('usersCount').textContent = allUsers.length;
    renderUsers(allUsers);

    // Searches
    allSearches = data.top_searches;
    renderSearches(allSearches);

    // Charts
    renderActivityChart(data.daily);
    renderModeChart(data.mode_usage);

  } catch (e) {
    console.error('Failed to load admin data', e);
  }
}

// ── Activity Chart ──
function renderActivityChart(daily) {
  const labels = daily.map(d => d.day);
  const values = daily.map(d => d.cnt);

  if (activityChartInst) activityChartInst.destroy();
  activityChartInst = new Chart(document.getElementById('activityChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Actions',
        data: values,
        borderColor: '#ff6b00',
        backgroundColor: 'rgba(108,99,255,0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointBackgroundColor: '#ff9a00',
        pointRadius: 4
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8888aa' }, grid: { color: 'rgba(42,42,74,0.5)' } },
        y: { ticks: { color: '#8888aa' }, grid: { color: 'rgba(42,42,74,0.5)' }, beginAtZero: true }
      }
    }
  });
}

// ── Mode Chart ──
function renderModeChart(m) {
  if (!m) return;
  const labels = ['Default', 'Exam', 'Revision', 'Deep', 'Viva', 'Quiz'];
  const values = [m.default_mode||0, m.exam||0, m.revision||0, m.deep||0, m.viva||0, m.quiz||0];
  const colors = ['#ff6b00','#ffa726','#66bb6a','#ff9a00','#ff9a00','#ff5722'];

  if (modeChartInst) modeChartInst.destroy();
  modeChartInst = new Chart(document.getElementById('modeChart'), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#8888aa', font: { size: 11 }, padding: 8 } }
      }
    }
  });
}

// ── Activity Table ──
function filterActivity() {
  const action = document.getElementById('actionFilter').value;
  const search = (document.getElementById('activitySearch')?.value || '').toLowerCase();
  let filtered = allLogs;
  if (action) filtered = filtered.filter(l => l.action === action);
  if (search) filtered = filtered.filter(l => (l.username||'').toLowerCase().includes(search));
  renderActivity(filtered);
}

function renderActivity(logs) {
  const tbody = document.getElementById('activityBody');
  if (!logs.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No activity found.</td></tr>';
    return;
  }
  tbody.innerHTML = logs.map(l => `
    <tr>
      <td class="text-muted" style="white-space:nowrap;font-size:0.8rem;">${fmtTime(l.created_at)}</td>
      <td><strong>${escHtml(l.username || '—')}</strong></td>
      <td>${actionBadge(l.action)}</td>
      <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
          title="${escHtml(l.detail||'')}">${escHtml(l.detail||'—')}</td>
      <td class="text-muted" style="font-size:0.8rem;">${escHtml(l.ip||'—')}</td>
    </tr>`).join('');
}

// ── Users Table ──
function renderUsers(users) {
  const tbody = document.getElementById('usersBody');
  if (!users.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No users yet.</td></tr>';
    return;
  }
  tbody.innerHTML = users.map((u, i) => `
    <tr>
      <td class="text-muted">${i+1}</td>
      <td><strong>${escHtml(u.username)}</strong></td>
      <td class="text-muted" style="font-size:0.82rem;">${escHtml(u.email)}</td>
      <td><span class="badge-count">${u.note_count}</span></td>
      <td class="text-muted" style="font-size:0.8rem;">${fmtTime(u.last_login)}</td>
      <td class="text-muted" style="font-size:0.8rem;">${fmtTime(u.created_at)}</td>
      <td>
        ${u.is_admin
          ? '<span class="action-badge" style="background:rgba(255,107,0,0.2);color:#ff9a00;">Admin</span>'
          : `<button class="action-btn" style="font-size:0.75rem;padding:0.3rem 0.7rem;" onclick="makeAdmin(${u.id},this)">Make Admin</button>`}
      </td>
    </tr>`).join('');
}

function filterUsers() {
  const q = document.getElementById('userSearch').value.toLowerCase();
  renderUsers(allUsers.filter(u => u.username.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)));
}

async function makeAdmin(uid, btn) {
  btn.disabled = true; btn.textContent = '...';
  await fetch(`/admin/make_admin/${uid}`, { method: 'POST' });
  await loadData();
}

// ── Top Searches ──
function renderSearches(searches) {
  const el = document.getElementById('searchesList');
  if (!searches.length) { el.innerHTML = '<p class="text-muted text-center mt-3">No searches yet.</p>'; return; }
  const max = searches[0].cnt;
  el.innerHTML = searches.map((s, i) => `
    <div class="search-bar-row">
      <div class="search-rank">${i+1}</div>
      <div class="flex-grow-1">
        <div class="d-flex justify-content-between mb-1">
          <span style="font-size:0.88rem;">${escHtml(s.detail)}</span>
          <span class="text-muted" style="font-size:0.8rem;">${s.cnt}x</span>
        </div>
        <div class="search-progress">
          <div class="search-progress-fill" style="width:${Math.round((s.cnt/max)*100)}%"></div>
        </div>
      </div>
    </div>`).join('');
}

// ── Tabs ──
function switchTab(tab, btn) {
  document.querySelectorAll('.admin-tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(`tab-${tab}`).style.display = 'block';
  btn.classList.add('active');
  if (tab === 'flags') loadFlags();
}

// Init + auto-refresh
loadData();
setInterval(loadData, 30000);

// ── Feature Flags ──
const FLAG_LABELS = {
  quiz_mode:     '🧩 Quiz Mode',
  viva_mode:     '🎤 Viva Mode',
  exam_mode:     '🎯 Exam Mode',
  revision_mode: '⚡ Revision Mode',
  deep_mode:     '🔬 Deep Learning Mode',
  smart_linking: '🔗 Smart Linking',
  btech:         '🎓 B.Tech Section',
  chat:          '💬 AI Chatbot',
};

async function loadFlags() {
  const res  = await fetch('/admin/flags');
  const data = await res.json();
  const el   = document.getElementById('flagsList');
  el.innerHTML = Object.entries(FLAG_LABELS).map(([key, label]) => `
    <div class="d-flex justify-content-between align-items-center py-2" style="border-bottom:1px solid var(--card-border);">
      <span style="font-size:0.95rem;">${label}</span>
      <label class="flag-toggle">
        <input type="checkbox" id="flag_${key}" ${data[key] ? 'checked' : ''}>
        <span class="flag-slider"></span>
      </label>
    </div>`).join('');
}

async function saveFlags() {
  const payload = {};
  Object.keys(FLAG_LABELS).forEach(key => {
    const el = document.getElementById(`flag_${key}`);
    if (el) payload[key] = el.checked;
  });
  const res = await fetch('/admin/flags', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (data.ok) showToast('Feature flags saved!');
}

function showToast(msg) {
  const wrap = document.getElementById('toastWrap') || document.body;
  const el = document.createElement('div');
  el.className = 'toast-msg';
  el.textContent = msg;
  el.style.cssText = 'position:fixed;top:1.5rem;right:1.5rem;background:#1a1a2e;border:1px solid #ff6b00;color:#e0e0ff;padding:0.7rem 1.2rem;border-radius:10px;z-index:9999;font-size:0.85rem;';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2500);
}

// Load flags when tab opens
const origSwitch = switchTab;
