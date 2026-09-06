// Giao dien web noi bo — JavaScript thuan, khong framework, khong buoc build.
//
// Truoc day day la mot ung dung React + TypeScript + Vite, keo theo Node va npm chi
// de ve mot khung chat. Ca trang co hai danh sach va mot o nhap; toan bo trang thai
// nam trong `state` duoi day. Doi lai, phia server thuan Python va sua giao dien la
// tai lai trang, khong phai build lai.
//
// Cau tra loi KHONG ve qua response cua POST /api/chat: worker la mot process khac,
// va POST phai tra 202 ngay. No ve qua SSE tren /api/stream/{thread_id}.

const state = {
  threadId: newThreadId(),
  threads: [],
  waiting: false,
  steps: [],
  renaming: null,
  stream: null,
};

const el = {
  threadList: document.getElementById('thread-list'),
  messages: document.getElementById('messages'),
  messageList: document.getElementById('message-list'),
  steps: document.getElementById('steps'),
  bottom: document.getElementById('bottom'),
  hero: document.getElementById('hero'),
  error: document.getElementById('error'),
  draft: document.getElementById('draft'),
  send: document.getElementById('send'),
  stop: document.getElementById('stop'),
};

function newThreadId() {
  return `web-${crypto.randomUUID()}`;
}

// --- Goi API ---------------------------------------------------------------

async function json(response) {
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

const api = {
  threads: () => fetch('/api/threads').then(json),
  messages: (id) => fetch(`/api/threads/${encodeURIComponent(id)}/messages`).then(json),
  send: (id, text) =>
    fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threadId: id, text }),
    }).then(json),
  stop: (id) => fetch(`/api/threads/${encodeURIComponent(id)}/stop`, { method: 'POST' }),
  remove: (id) => fetch(`/api/threads/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  rename: (id, title) =>
    fetch(`/api/threads/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }),
};

// --- Ve giao dien ----------------------------------------------------------

// textContent chu KHONG innerHTML: cau tra loi cua bot va tin cua nguoi dung deu la
// van ban khong tin cay. Nhet vao innerHTML la mo cua cho XSS ngay trong trang cua
// chinh minh.
function bubble(text, fromBot) {
  const node = document.createElement('div');
  node.className = `msg ${fromBot ? 'bot' : 'user'}`;
  node.textContent = text;
  return node;
}

function renderMessages(messages) {
  el.messageList.replaceChildren(...messages.map((m) => bubble(m.text, m.fromBot)));
  const empty = messages.length === 0 && !state.waiting;
  el.hero.hidden = !empty;
  el.messages.hidden = empty;
  el.bottom.scrollIntoView({ behavior: 'smooth' });
}

function appendMessage(text, fromBot) {
  el.hero.hidden = true;
  el.messages.hidden = false;
  el.messageList.append(bubble(text, fromBot));
  el.bottom.scrollIntoView({ behavior: 'smooth' });
}

function renderSteps() {
  el.steps.hidden = state.steps.length === 0;
  el.steps.replaceChildren(
    ...state.steps.map((s) => {
      const node = document.createElement('div');
      node.className = `step ${s.kind}${s.ok ? '' : ' failed'}`;
      node.textContent = s.text;
      return node;
    }),
  );
  el.bottom.scrollIntoView({ behavior: 'smooth' });
}

function setWaiting(waiting) {
  state.waiting = waiting;
  el.stop.hidden = !waiting;
  el.send.hidden = waiting;
  el.draft.disabled = waiting;
}

function showError(text) {
  el.error.textContent = text;
  el.error.hidden = text === null;
}

function renderThreads() {
  if (state.threads.length === 0) {
    const p = document.createElement('p');
    p.className = 'empty';
    p.textContent = 'Chưa có cuộc trò chuyện nào.';
    el.threadList.replaceChildren(p);
    return;
  }
  el.threadList.replaceChildren(...state.threads.map(threadRow));
}

function threadRow(thread) {
  const row = document.createElement('div');
  row.className = `thread${thread.threadId === state.threadId ? ' active' : ''}`;
  const label = thread.title ?? thread.lastText;

  if (state.renaming === thread.threadId) {
    const input = document.createElement('input');
    input.className = 'thread-rename';
    input.value = thread.title ?? thread.lastText.slice(0, 60);
    input.addEventListener('blur', () => commitRename(thread.threadId, input.value));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') commitRename(thread.threadId, input.value);
      if (e.key === 'Escape') { state.renaming = null; renderThreads(); }
    });
    row.append(input);
    queueMicrotask(() => input.focus());
    return row;
  }

  const open = document.createElement('button');
  open.className = 'thread-open';
  open.title = label;
  open.addEventListener('click', () => selectThread(thread.threadId));
  open.addEventListener('dblclick', () => { state.renaming = thread.threadId; renderThreads(); });
  const span = document.createElement('span');
  span.className = 'thread-text';
  span.textContent = label;
  open.append(span);

  const rename = document.createElement('button');
  rename.className = 'thread-action';
  rename.title = 'Đổi tên (hoặc nháy đúp)';
  rename.textContent = '✎';
  rename.addEventListener('click', () => { state.renaming = thread.threadId; renderThreads(); });

  const remove = document.createElement('button');
  remove.className = 'thread-action thread-delete';
  remove.title = 'Xoá cuộc trò chuyện';
  remove.textContent = '✕';
  remove.addEventListener('click', async () => {
    await api.remove(thread.threadId);
    if (thread.threadId === state.threadId) selectThread(newThreadId());
    else await refreshThreads();
  });

  row.append(open, rename, remove);
  return row;
}

// --- Hanh dong -------------------------------------------------------------

async function refreshThreads() {
  try {
    state.threads = await api.threads();
  } catch {
    state.threads = [];
  }
  renderThreads();
}

function commitRename(id, value) {
  state.renaming = null;
  const title = value.trim();
  // Bo trong thi giu ten cu, khong xoa ten dang co.
  if (title === '') { renderThreads(); return; }
  api.rename(id, title).then(refreshThreads);
}

async function selectThread(id) {
  state.threadId = id;
  state.steps = [];
  setWaiting(false);
  showError(null);
  renderSteps();
  renderThreads();

  // Lich su doc tu Postgres, KHONG phai localStorage — tai lai trang hay doi may
  // van con day.
  try {
    renderMessages(await api.messages(id));
  } catch {
    renderMessages([]);
  }
  openStream(id);
}

function openStream(threadId) {
  if (state.stream !== null) state.stream.close();
  const source = new EventSource(`/api/stream/${encodeURIComponent(threadId)}`);
  source.onmessage = (ev) => {
    let event;
    try {
      event = JSON.parse(ev.data);
    } catch {
      return; // Bo qua mot khung hong thay vi lam sap ca giao dien.
    }
    handleEvent(event);
  };
  state.stream = source;
}

function handleEvent(event) {
  switch (event.type) {
    case 'thought':
      state.steps.push({ kind: 'thought', text: event.text, ok: true });
      renderSteps();
      break;
    case 'tool_call':
      state.steps.push({
        kind: 'tool_call',
        text: `Đang tra cứu: ${event.tools.join(', ')}`,
        ok: true,
      });
      renderSteps();
      break;
    case 'observation':
      state.steps.push({
        kind: 'observation',
        text: event.ok
          ? `${event.tool} xong (${(event.latency_ms / 1000).toFixed(1)}s)`
          : `${event.tool} lỗi`,
        ok: event.ok,
      });
      renderSteps();
      break;
    case 'final':
      appendMessage(event.text, true);
      state.steps = [];
      renderSteps();
      setWaiting(false);
      refreshThreads();
      break;
    case 'error':
      showError(event.text);
      state.steps = [];
      renderSteps();
      setWaiting(false);
      break;
    default:
      break; // 'typing' va cac su kien sau nay: khong can lam gi.
  }
}

// --- Noi day -------------------------------------------------------------

el.draft.addEventListener('input', () => {
  el.send.disabled = el.draft.value.trim() === '';
});

document.getElementById('new-chat').addEventListener('click', () => {
  selectThread(newThreadId());
});

el.stop.addEventListener('click', () => api.stop(state.threadId));

document.getElementById('composer').addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = el.draft.value.trim();
  if (text === '' || state.waiting) return;

  el.draft.value = '';
  el.send.disabled = true;
  showError(null);
  state.steps = [];
  renderSteps();
  appendMessage(text, false);
  setWaiting(true);

  try {
    await api.send(state.threadId, text);
  } catch (err) {
    showError(String(err));
    setWaiting(false);
  }
});

refreshThreads();
selectThread(state.threadId);
