// ── Helpers ──
function showToast(msg) {
  const wrap = document.getElementById('toastWrap');
  const el = document.createElement('div');
  el.className = 'toast-msg';
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 2500);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Shared note renderer (used by both pages) ──
function renderNotes(raw, targetId) {
  const lines = raw.split('\n');
  let html = '';
  lines.forEach(line => {
    const escaped = line
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>');

    if (/^#{1,2}\s/.test(line)) {
      html += `<h5 class="notes-heading">${escaped.replace(/^#{1,2}\s/, '')}</h5>`;
    } else if (/^###\s/.test(line)) {
      html += `<h6 class="notes-subheading">${escaped.replace(/^###\s/, '')}</h6>`;
    } else if (/^\s*[-*•]\s/.test(line)) {
      html += `<div class="notes-bullet"><i class="fa fa-circle-dot me-2"></i>${escaped.replace(/^\s*[-*•]\s/, '')}</div>`;
    } else if (/^\d+\.\s/.test(line)) {
      html += `<div class="notes-bullet"><i class="fa fa-circle-dot me-2"></i>${escaped}</div>`;
    } else if (line.trim() === '') {
      html += '<div class="notes-spacer"></div>';
    } else {
      html += `<p class="notes-para">${escaped}</p>`;
    }
  });
  document.getElementById(targetId).innerHTML = html;
}

// ── Notes ──
async function getNotes() {
  const topic = document.getElementById('topic').value.trim();
  if (!topic) { showToast('Please enter a topic first'); return; }

  document.getElementById('notesLoader').style.display = 'block';
  document.getElementById('notesSection').style.display = 'none';

  try {
    const res = await fetch('/get_notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic })
    });
    const data = await res.json();
    if (data.error) { showToast(data.error); return; }
    renderNotes(data.notes, 'notesContent');
    document.getElementById('notesSection').style.display = 'block';
    document.getElementById('notesSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    showToast('Failed to generate notes');
  } finally {
    document.getElementById('notesLoader').style.display = 'none';
  }
}

function copyNotes() {
  const text = document.getElementById('notesContent').innerText;
  navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard!'));
}

function downloadPDF() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  const topic = document.getElementById('topic').value || 'Notes';
  const text  = document.getElementById('notesContent').innerText;

  doc.setFontSize(16);
  doc.setFont('helvetica', 'bold');
  doc.text(topic, 14, 18);

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  const lines = doc.splitTextToSize(text, 182);
  doc.text(lines, 14, 28);
  doc.save(`${topic}.pdf`);
  showToast('PDF downloaded!');
}

// ── Chat ──
function toggleChat() {
  const box = document.getElementById('chatBox');
  const isHidden = box.style.display === 'none' || box.style.display === '';
  box.style.display = isHidden ? 'block' : 'none';
  if (isHidden) document.getElementById('msg').focus();
}

function openChat() {
  document.getElementById('chatBox').style.display = 'block';
  document.getElementById('msg').focus();
}

function appendMsg(text, type) {
  const body = document.getElementById('chatBody');
  const el = document.createElement('div');
  el.className = type === 'user' ? 'msg-user' : 'msg-bot';
  el.textContent = text;
  body.appendChild(el);
  body.scrollTop = body.scrollHeight;
}

function showTyping() {
  const body = document.getElementById('chatBody');
  const el = document.createElement('div');
  el.className = 'msg-bot';
  el.id = 'typingIndicator';
  el.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
  body.appendChild(el);
  body.scrollTop = body.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

async function sendMsg() {
  const input = document.getElementById('msg');
  const msg = input.value.trim();
  if (!msg) return;

  input.value = '';
  appendMsg(msg, 'user');
  showTyping();

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    removeTyping();
    appendMsg(data.reply || data.error, 'bot');
  } catch (e) {
    removeTyping();
    appendMsg('Something went wrong. Try again.', 'bot');
  }
}

// ── History Drawer ──
let allHistory = [];

async function toggleHistory() {
  const drawer  = document.getElementById('historyDrawer');
  const overlay = document.getElementById('historyOverlay');
  const isOpen  = drawer.classList.contains('open');

  if (isOpen) {
    drawer.classList.remove('open');
    overlay.style.display = 'none';
  } else {
    drawer.classList.add('open');
    overlay.style.display = 'block';
    await loadHistory();
  }
}

async function loadHistory() {
  const list = document.getElementById('historyList');
  list.innerHTML = '<p class="text-muted text-center mt-4">Loading...</p>';
  try {
    const res  = await fetch('/history');
    const data = await res.json();
    allHistory = data.history || [];
    renderHistoryList(allHistory);
  } catch (e) {
    list.innerHTML = '<p class="text-muted text-center mt-4">Failed to load history.</p>';
  }
}

function renderHistoryList(items) {
  const list = document.getElementById('historyList');
  if (!items.length) {
    list.innerHTML = '<p class="text-muted text-center mt-4">No history yet. Generate some notes!</p>';
    return;
  }
  list.innerHTML = items.map(h => `
    <div class="history-item" onclick="loadFromHistory(${h.id})">
      <button class="del-btn" onclick="deleteHistory(event, ${h.id}, this)">
        <i class="fa fa-trash"></i>
      </button>
      <h6>${escHtml(h.topic)}</h6>
      <p>${escHtml(h.notes.slice(0, 80))}...</p>
      <div class="history-date"><i class="fa fa-clock me-1"></i>${new Date(h.created_at).toLocaleString()}</div>
    </div>`).join('');
}

function filterHistory() {
  const q = document.getElementById('historySearch').value.toLowerCase();
  const filtered = allHistory.filter(h => h.topic.toLowerCase().includes(q));
  renderHistoryList(filtered);
}

function loadFromHistory(id) {
  const item = allHistory.find(h => h.id === id);
  if (!item) return;
  // only works on index page
  const topicEl = document.getElementById('topic');
  const notesEl = document.getElementById('notesContent');
  const section = document.getElementById('notesSection');
  if (topicEl && notesEl && section) {
    topicEl.value = item.topic;
    renderNotes(item.notes, 'notesContent');
    section.style.display = 'block';
    toggleHistory();
    section.scrollIntoView({ behavior: 'smooth' });
  }
}

async function deleteHistory(e, id, btn) {
  e.stopPropagation();
  await fetch(`/history/${id}`, { method: 'DELETE' });
  allHistory = allHistory.filter(h => h.id !== id);
  btn.closest('.history-item').remove();
  showToast('Deleted');
}
