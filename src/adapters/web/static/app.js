// CP Assistant — giao dien web noi bo. JavaScript thuan, khong framework, khong build.
//
// Truoc day day la mot ung dung React + TypeScript + Vite, keo theo Node va npm chi
// de ve mot khung chat. Ca trang co hai danh sach va mot o nhap; toan bo trang thai
// nam trong `state` duoi day. Doi lai, phia server thuan Python va sua giao dien la
// tai lai trang, khong phai build lai.
//
// HAI dieu de sai o day, ghi ra dau file:
//
//   1. Cau tra loi KHONG ve qua response cua POST /api/chat. Worker la mot process
//      khac, va POST phai tra 202 ngay. No ve qua SSE tren /api/stream/{thread_id}.
//
//   2. MOI van ban tu server deu di vao DOM qua textContent, khong bao gio qua
//      innerHTML. Cau tra loi cua bot chua noi dung tu web va tu tai lieu do nguoi
//      la soan — do la van ban khong tin cay, va nhet no vao innerHTML la mo cua XSS
//      ngay trong trang cua chinh minh. Ham `linkify` duoi day la cho DUY NHAT dung
//      toi cau truc DOM phuc tap hon mot node van ban, va no van dung createElement.

const SUGGESTIONS = [
  { title: 'Tra tài liệu nội bộ', text: 'Chính sách hoàn tiền của công ty quy định thế nào?' },
  { title: 'Tra cứu web', text: 'Tỷ giá USD sang VND hôm nay khoảng bao nhiêu?' },
  { title: 'Tìm bài báo khoa học', text: 'Tìm bài báo về retrieval augmented generation' },
  { title: 'Ghi nhớ cho lần sau', text: 'nhớ giúp: mình phụ trách phần backend' },
];

const state = {
  threadId: newThreadId(),
  threads: [],
  waiting: false,
  steps: [],
  renaming: null,
  stream: null,
  // Nguoi dung da tu cuon len de doc lai chua. Neu roi thi KHONG duoc keo man hinh
  // ve cuoi moi lan co su kien moi — do la cach nhanh nhat lam nguoi ta buc minh.
  pinned: true,
};

const el = {};
for (const id of [
  'app', 'sidebar', 'scrim', 'collapse', 'open-sidebar', 'new-chat', 'thread-list',
  'dot', 'status-text', 'theme', 'theme-icon', 'topbar-title', 'topbar-sub', 'scroll',
  'hero', 'suggestions', 'column', 'error', 'error-text', 'message-list', 'trace',
  'trace-head', 'trace-label', 'trace-steps', 'thinking', 'bottom', 'composer',
  'draft', 'send', 'stop',
]) {
  el[id.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = document.getElementById(id);
}

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

// --- Tien ich --------------------------------------------------------------

function icon(name, className = 'icon') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', className);
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

function iconButton(name, title, className = 'icon-btn') {
  const button = document.createElement('button');
  button.className = className;
  button.type = 'button';
  button.title = title;
  button.setAttribute('aria-label', title);
  button.append(icon(name));
  return button;
}

// Gio dia phuong, dang 24h. Ngay khac hom nay thi kem ngay/thang — de doc mot hoi
// thoai cu ma khong phai doan.
function formatTime(iso) {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return '';
  const now = new Date();
  const sameDay = at.toDateString() === now.toDateString();
  const time = at.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  return sameDay ? time : `${at.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })} ${time}`;
}

function formatRelative(iso) {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return '';
  const minutes = Math.round((Date.now() - at.getTime()) / 60000);
  if (minutes < 1) return 'vừa xong';
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.round(hours / 24);
  return days < 30 ? `${days} ngày trước` : at.toLocaleDateString('vi-VN');
}

// Bien URL thanh the <a> ma KHONG dung innerHTML.
//
// System prompt bat bot "de nguyen duong dan" khi dan nguon tu web, nen cau tra loi
// thuong xuyen co link — de nguyen dang van ban thi nguoi dung phai boi va chep tay.
// Doi lai, tuyet doi khong duoc dung innerHTML: van ban nay den tu ket qua tim kiem
// do nguoi la soan.
function linkify(text) {
  const fragment = document.createDocumentFragment();
  const pattern = /https?:\/\/[^\s<>()[\]{}"']+/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) fragment.append(text.slice(last, match.index));
    const a = document.createElement('a');
    a.href = match[0];
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = match[0];
    fragment.append(a);
    last = match.index + match[0].length;
  }
  if (last < text.length) fragment.append(text.slice(last));
  return fragment;
}

// --- Ve tin nhan -----------------------------------------------------------

function messageRow(text, fromBot, at) {
  const row = document.createElement('div');
  row.className = `msg-row ${fromBot ? 'bot' : 'user'}`;

  if (fromBot) {
    const avatar = document.createElement('span');
    avatar.className = 'avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = (el.topbarTitle.dataset.botInitial || 'C');
    row.append(avatar);
  }

  const body = document.createElement('div');
  body.className = 'msg-body';

  const bubble = document.createElement('div');
  bubble.className = 'msg';
  bubble.append(linkify(text));
  body.append(bubble);

  const foot = document.createElement('div');
  foot.className = 'msg-foot';
  if (at) {
    const time = document.createElement('span');
    time.className = 'msg-time';
    time.textContent = formatTime(at);
    foot.append(time);
  }
  if (fromBot) {
    const copy = iconButton('copy', 'Chép câu trả lời');
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        return; // Trinh duyet chan clipboard: khong bao gi ca, im lang la du.
      }
      const done = document.createElement('span');
      done.className = 'copied';
      done.textContent = 'Đã chép';
      copy.replaceWith(done);
      setTimeout(() => done.replaceWith(copy), 1600);
    });
    foot.append(copy);
  }
  body.append(foot);

  row.append(body);
  return row;
}

function renderMessages(messages) {
  el.messageList.replaceChildren(
    ...messages.map((m) => messageRow(m.text, m.fromBot, m.at)),
  );
  const empty = messages.length === 0 && !state.waiting;
  el.hero.hidden = !empty;
  el.column.hidden = empty;
  el.topbarSub.textContent = messages.length ? `${messages.length} tin nhắn` : '';
  state.pinned = true;
  scrollToBottom('auto');
}

function appendMessage(text, fromBot) {
  el.hero.hidden = true;
  el.column.hidden = false;
  el.messageList.append(messageRow(text, fromBot, new Date().toISOString()));
  scrollToBottom();
}

function scrollToBottom(behavior = 'smooth') {
  if (!state.pinned) return;
  el.bottom.scrollIntoView({ behavior, block: 'end' });
}

// --- Dau vet suy luan ------------------------------------------------------

function renderSteps() {
  const has = state.steps.length > 0;
  el.trace.hidden = !has;
  if (!has) {
    el.traceSteps.replaceChildren();
    return;
  }

  const tools = state.steps.filter((s) => s.kind === 'tool_call').length;
  el.traceLabel.textContent = state.waiting
    ? 'Đang tra cứu…'
    : `Đã tra cứu ${tools} lần`;

  el.traceSteps.replaceChildren(
    ...state.steps.map((s) => {
      const node = document.createElement('div');
      node.className = `step ${s.kind}${s.ok ? '' : ' failed'}`;
      const text = document.createElement('span');
      text.className = 'step-text';
      text.textContent = s.text;
      node.append(text);
      if (s.time) {
        const time = document.createElement('span');
        time.className = 'step-time';
        time.textContent = s.time;
        node.append(time);
      }
      return node;
    }),
  );
  scrollToBottom();
}

function setWaiting(waiting) {
  state.waiting = waiting;
  el.stop.hidden = !waiting;
  el.send.hidden = waiting;
  el.thinking.hidden = !waiting;
  el.draft.disabled = waiting;
  if (waiting) {
    el.hero.hidden = true;
    el.column.hidden = false;
    scrollToBottom();
  } else {
    el.draft.focus();
  }
}

function showError(text) {
  el.errorText.textContent = text ?? '';
  el.error.hidden = text === null;
}

// --- Danh sach hoi thoai ---------------------------------------------------

function renderThreads() {
  if (state.threads.length === 0) {
    const p = document.createElement('p');
    p.className = 'empty-list';
    p.textContent = 'Chưa có cuộc trò chuyện nào.';
    el.threadList.replaceChildren(p);
    return;
  }
  el.threadList.replaceChildren(...state.threads.map(threadRow));
}

// Nhan hien thi cua mot hoi thoai, theo thu tu uu tien:
//   1. Ten nguoi dung tu dat  — ho da noi ro ho muon goi no la gi
//   2. Cau hoi DAU TIEN       — nguoi ta nho minh da hoi gi, khong nho bot da dap gi
//   3. Tin nhan cuoi          — luoi cuoi cung, cho hoi thoai chi co tin cua bot
function threadLabel(thread) {
  return thread.title ?? thread.question ?? thread.lastText ?? 'Cuộc trò chuyện';
}

function threadRow(thread) {
  const row = document.createElement('div');
  row.className = `thread${thread.threadId === state.threadId ? ' active' : ''}`;
  const label = threadLabel(thread);

  if (state.renaming === thread.threadId) {
    const input = document.createElement('input');
    input.className = 'thread-rename';
    input.value = (thread.title ?? threadLabel(thread)).slice(0, 60);
    input.addEventListener('blur', () => commitRename(thread.threadId, input.value));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') commitRename(thread.threadId, input.value);
      if (e.key === 'Escape') { state.renaming = null; renderThreads(); }
    });
    row.append(input);
    queueMicrotask(() => { input.focus(); input.select(); });
    return row;
  }

  const open = document.createElement('button');
  open.className = 'thread-open';
  open.type = 'button';
  open.title = label;
  open.addEventListener('click', () => selectThread(thread.threadId));
  open.addEventListener('dblclick', () => { state.renaming = thread.threadId; renderThreads(); });

  const title = document.createElement('span');
  title.className = 'thread-title';
  title.textContent = label;

  const meta = document.createElement('span');
  meta.className = 'thread-meta';
  meta.textContent = `${formatRelative(thread.lastAt)} · ${thread.messageCount} tin`;

  open.append(title, meta);

  const actions = document.createElement('div');
  actions.className = 'thread-actions';

  const rename = iconButton('pencil', 'Đổi tên (hoặc nháy đúp)');
  rename.addEventListener('click', () => { state.renaming = thread.threadId; renderThreads(); });

  const remove = iconButton('trash', 'Xoá cuộc trò chuyện', 'icon-btn thread-delete');
  remove.addEventListener('click', async () => {
    await api.remove(thread.threadId);
    if (thread.threadId === state.threadId) selectThread(newThreadId());
    else await refreshThreads();
  });

  actions.append(rename, remove);
  row.append(open, actions);
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
  updateTitle();
}

function updateTitle() {
  const current = state.threads.find((t) => t.threadId === state.threadId);
  el.topbarTitle.textContent = current ? threadLabel(current) : 'Cuộc trò chuyện mới';
}

function commitRename(id, value) {
  state.renaming = null;
  const title = value.trim();
  // Bo trong thi giu ten cu, khong xoa ten dang co.
  if (title === '') { renderThreads(); return; }
  api.rename(id, title).then(refreshThreads);
}

// Hoi thoai dang mo nam trong URL (`#t=<id>`), nen no LUU DAU TRANG duoc, gui link
// cho nguoi khac tren cung may duoc, va nut Back cua trinh duyet chay dung.
// Khong co no thi tai lai trang la mat cho dang doc — chuyen xay ra suot.
function threadFromHash() {
  const match = location.hash.match(/^#t=(.+)$/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function selectThread(id, { pushHash = true } = {}) {
  state.threadId = id;
  if (pushHash && threadFromHash() !== id) location.hash = `t=${encodeURIComponent(id)}`;
  state.steps = [];
  setWaiting(false);
  showError(null);
  renderSteps();
  renderThreads();
  updateTitle();
  closeSidebarOnMobile();

  // Lich su doc tu Postgres, KHONG phai localStorage — tai lai trang hay doi may
  // van con day.
  try {
    renderMessages(await api.messages(id));
  } catch {
    renderMessages([]);
  }
  openStream(id);
}

function setStatus(kind, text) {
  el.dot.className = `dot ${kind}`;
  el.statusText.textContent = text;
}

function openStream(threadId) {
  if (state.stream !== null) state.stream.close();
  const source = new EventSource(`/api/stream/${encodeURIComponent(threadId)}`);

  source.onopen = () => setStatus('', 'Đã kết nối');
  // EventSource tu ket noi lai, nen day khong phai loi vinh vien — nhung nguoi dung
  // phai thay, vi trong luc mat ket noi thi cau tra loi se khong bao gio hien ra.
  source.onerror = () => setStatus('error', 'Mất kết nối, đang thử lại…');

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
        text: `Gọi ${event.tools.join(', ')}`,
        ok: true,
      });
      renderSteps();
      break;
    case 'observation':
      state.steps.push({
        kind: 'observation',
        text: event.ok ? `${event.tool} xong` : `${event.tool} lỗi`,
        time: `${(event.latency_ms / 1000).toFixed(1)}s`,
        ok: event.ok,
      });
      renderSteps();
      break;
    case 'final':
      appendMessage(event.text, true);
      setWaiting(false);
      // Giu lai dau vet de nguoi dung con xem bot da tra cuu gi, nhung gap lai:
      // no da xong viec, khong con la thu dang theo doi.
      collapseTrace();
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

function collapseTrace() {
  if (state.steps.length === 0) return;
  renderSteps();
  el.trace.classList.remove('open');
  el.traceHead.setAttribute('aria-expanded', 'false');
}

// --- Sidebar, nen sang/toi -------------------------------------------------

const MOBILE = '(max-width: 900px)';

function closeSidebarOnMobile() {
  if (window.matchMedia(MOBILE).matches) el.app.classList.add('sidebar-hidden');
}

function toggleSidebar() {
  el.app.classList.toggle('sidebar-hidden');
}

function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;

  const dark = theme
    ? theme === 'dark'
    : window.matchMedia('(prefers-color-scheme: dark)').matches;
  el.themeIcon.setAttribute('href', dark ? '#i-sun' : '#i-moon');
}

function toggleTheme() {
  const dark = document.documentElement.dataset.theme
    ? document.documentElement.dataset.theme === 'dark'
    : window.matchMedia('(prefers-color-scheme: dark)').matches;
  const next = dark ? 'light' : 'dark';
  applyTheme(next);
  try {
    localStorage.setItem('cp-theme', next);
  } catch {
    /* Trinh duyet chan localStorage: doi duoc trong phien nay, khong nho sang phien sau. */
  }
}

// --- O nhap ----------------------------------------------------------------

// textarea tu cao theo noi dung, chan tren o 200px (dat trong CSS). Phai reset ve
// 'auto' truoc khi doc scrollHeight, neu khong o chi phinh ra ma khong bao gio co lai.
function autoGrow() {
  el.draft.style.height = 'auto';
  el.draft.style.height = `${Math.min(el.draft.scrollHeight, 200)}px`;
}

async function submit(text) {
  if (text === '' || state.waiting) return;

  el.draft.value = '';
  autoGrow();
  el.send.disabled = true;
  showError(null);
  state.steps = [];
  renderSteps();
  el.trace.classList.add('open');
  el.traceHead.setAttribute('aria-expanded', 'true');
  state.pinned = true;
  appendMessage(text, false);
  setWaiting(true);

  try {
    await api.send(state.threadId, text);
  } catch (err) {
    showError(String(err));
    setWaiting(false);
  }
}

// --- Noi day ---------------------------------------------------------------

el.suggestions.replaceChildren(
  ...SUGGESTIONS.map((s) => {
    const button = document.createElement('button');
    button.className = 'suggestion';
    button.type = 'button';
    const b = document.createElement('b');
    b.textContent = s.title;
    const span = document.createElement('span');
    span.textContent = s.text;
    button.append(b, span);
    button.addEventListener('click', () => submit(s.text));
    return button;
  }),
);

el.draft.addEventListener('input', () => {
  el.send.disabled = el.draft.value.trim() === '';
  autoGrow();
});

// Enter gui, Shift+Enter xuong dong. Day la quy uoc cua moi cong cu chat; lam nguoc
// lai la bat nguoi dung hoc lai mot thoi quen da co.
el.draft.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    submit(el.draft.value.trim());
  }
});

el.composer.addEventListener('submit', (e) => {
  e.preventDefault();
  submit(el.draft.value.trim());
});

// Nguoi dung cuon len de doc lai thi thoi bam theo day. Cach day 120px tro xuong
// van coi la "dang o cuoi" — khong ai cuon chinh xac toi tung pixel.
el.scroll.addEventListener('scroll', () => {
  const { scrollTop, scrollHeight, clientHeight } = el.scroll;
  state.pinned = scrollHeight - scrollTop - clientHeight < 120;
});

el.newChat.addEventListener('click', () => selectThread(newThreadId()));
el.collapse.addEventListener('click', toggleSidebar);
el.openSidebar.addEventListener('click', toggleSidebar);
el.scrim.addEventListener('click', toggleSidebar);
el.theme.addEventListener('click', toggleTheme);
el.stop.addEventListener('click', () => api.stop(state.threadId));

el.traceHead.addEventListener('click', () => {
  const open = el.trace.classList.toggle('open');
  el.traceHead.setAttribute('aria-expanded', String(open));
});

document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    selectThread(newThreadId());
  }
  // Escape khi dang cho = dung. Cung phim ma nguoi ta van dung de huy moi thu khac.
  if (e.key === 'Escape' && state.waiting) api.stop(state.threadId);
});

el.topbarTitle.dataset.botInitial = document.querySelector('.logo-mark')?.textContent ?? 'C';

// Doc lai lua chon nen sang/toi de dat DUNG bieu tuong. The <html> da duoc dat tu
// trong <head> roi (tranh nhay trang), day chi la phan con lai cua cong viec do.
let savedTheme = null;
try {
  savedTheme = localStorage.getItem('cp-theme');
} catch {
  /* Trinh duyet chan localStorage: theo he dieu hanh, khong phai loi. */
}
applyTheme(savedTheme === 'dark' || savedTheme === 'light' ? savedTheme : null);

// Nut Back/Forward cua trinh duyet. `pushHash: false` de khong ghi de lich su bang
// chinh cai vua doc ra tu no.
window.addEventListener('hashchange', () => {
  const id = threadFromHash();
  if (id && id !== state.threadId) selectThread(id, { pushHash: false });
});

closeSidebarOnMobile();
refreshThreads();
selectThread(threadFromHash() ?? state.threadId);
