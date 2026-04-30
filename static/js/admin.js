let allLogs    = [];
let allUsers   = [];
let allSearches = [];

const ACTION_COLORS = {
  LOGIN:      { bg: 'rgba(34,197,94,0.15)',   color: '#4ade80' },
  LOGIN_FAIL: { bg: 'rgba(245,0,87,0.15)',    color: '#ff6b9d' },
  REGISTER:   { bg: 'rgba(108,99,255,0.15)',  color: '#a78bfa' },
  LOGOUT:     { bg: 'rgba(156,163,175,0.15)', color: '#9ca3af' },
  SEARCH:     { bg: 'rgba(251,191,36,0.15)',  color: '#fbbf24' },
  VISIT:      { bg: 'rgba(56,189,248,0.15)',  color: '#38bdf8' },
  CHAT:       { bg: 'rgba(167,139,250,0.15)', color: '#c4b5fd' },
};

function actionBadge(action) {
  const c = ACTION_COLORS[action] || { bg: 'rgba(255,255,255,0.1)', color: '#fff' };
  return `<span class="action-badge" style="background:${c.bg};color:${c.color};">${action}</span>`;
}

function fmtTime(dt) {
  return new Date(dt).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
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

    // Logs
    allLogs = data.logs;
    document.getElementById('activityCount').textContent = allLogs.length;
    renderActivity(allLogs);

    // Users
    allUsers = data.users;
    document.getElementById('usersCount').textContent = allUsers.length;
    renderUsers(allUsers);

    // Searches
    allSearches = data.top_searches;
    renderSearches(allSearches);

  } catch (e) {
    console.error('Failed to load admin data', e);
  }
}

function renderActivity(logs) {
  const tbody = document.getElementById('activityBody');
  if (!logs.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No activity yet.</td></tr>';
    return;
  }
  tbody.innerHTML = logs.map(l => `
    <tr>
      <td class="text-muted" style="white-space:nowrap;font-size:0.8rem;">${fmtTime(l.created_at)}</td>
      <td><strong>${escHtml(l.username || '—')}</strong></td>
      <td>${actionBadge(l.action)}</td>
      <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
          title="${escHtml(l.detail || '')}">${escHtml(l.detail || '—')}</td>
      <td class="text-muted" style="font-size:0.8rem;">${escHtml(l.ip || '—')}</td>
    </tr>`).join('');
}

function filterActivity() {
  const action = document.getElementById('actionFilter').value;
  const filtered = action ? allLogs.filter(l => l.action === action) : allLogs;
  renderActivity(filtered);
}

function renderUsers(users) {
  const tbody = document.getElementById('usersBody');
  if (!users.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No users yet.</td></tr>';
    return;
  }
  tbody.innerHTML = users.map((u, i) => `
    <tr>
      <td class="text-muted">${i + 1}</td>
      <td><strong>${escHtml(u.username)}</strong></td>
      <td class="text-muted">${escHtml(u.email)}</td>
      <td><span class="badge-count">${u.note_count}</span></td>
      <td class="text-muted" style="font-size:0.8rem;">${u.last_login ? fmtTime(u.last_login) : 'Never'}</td>
      <td class="text-muted" style="font-size:0.8rem;">${fmtTime(u.created_at)}</td>
      <td>
        ${u.is_admin
          ? '<span class="action-badge" style="background:rgba(108,99,255,0.2);color:#a78bfa;">Admin</span>'
          : `<button class="action-btn" style="font-size:0.75rem;" onclick="makeAdmin(${u.id}, this)">Make Admin</button>`
        }
      </td>
    </tr>`).join('');
}

function filterUsers() {
  const q = document.getElementById('userSearch').value.toLowerCase();
  const filtered = allUsers.filter(u =>
    u.username.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
  );
  renderUsers(filtered);
}

async function makeAdmin(uid, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  await fetch(`/admin/make_admin/${uid}`, { method: 'POST' });
  await loadData();
}

function renderSearches(searches) {
  const el = document.getElementById('searchesList');
  if (!searches.length) {
    el.innerHTML = '<p class="text-muted text-center mt-3">No searches yet.</p>';
    return;
  }
  const max = searches[0].cnt;
  el.innerHTML = searches.map((s, i) => `
    <div class="search-bar-row">
      <div class="search-rank">${i + 1}</div>
      <div class="flex-grow-1">
        <div class="d-flex justify-content-between mb-1">
          <span style="font-size:0.9rem;">${escHtml(s.detail)}</span>
          <span class="text-muted" style="font-size:0.8rem;">${s.cnt}x</span>
        </div>
        <div class="search-progress">
          <div class="search-progress-fill" style="width:${Math.round((s.cnt/max)*100)}%"></div>
        </div>
      </div>
    </div>`).join('');
}

function switchTab(tab) {
  document.querySelectorAll('.admin-tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(`tab-${tab}`).style.display = 'block';
  event.target.classList.add('active');
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Auto-refresh every 30 seconds
loadData();
setInterval(loadData, 30000);
