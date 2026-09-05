import { useCallback, useEffect, useRef, useState } from 'react';
import { api, openStream, type Message, type ThreadSummary } from './api.js';

const newThreadId = (): string => `web-${crypto.randomUUID()}`;

export function App(): JSX.Element {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [threadId, setThreadId] = useState<string>(newThreadId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshThreads = useCallback(() => {
    api.threads().then(setThreads).catch(() => setThreads([]));
  }, []);

  useEffect(refreshThreads, [refreshThreads]);

  // Doi thread thi tai lai lich su TU POSTGRES — khong phai localStorage, nen
  // tai lai trang hay doi may van con day.
  useEffect(() => {
    setMessages([]);
    setWaiting(false);
    api.messages(threadId).then(setMessages).catch(() => setMessages([]));
  }, [threadId]);

  // Mot SSE cho moi thread. Cau tra loi ve qua day chu khong qua response cua POST:
  // worker la process khac, va POST phai tra 202 ngay.
  useEffect(() => {
    return openStream(threadId, (event) => {
      if (event.type === 'final') {
        setMessages((prev) => [...prev, { text: event.text, fromBot: true, at: new Date().toISOString() }]);
        setWaiting(false);
        refreshThreads();
      } else if (event.type === 'error') {
        setError(event.text);
        setWaiting(false);
      }
    });
  }, [threadId, refreshThreads]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, waiting]);

  async function submit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    const text = draft.trim();
    if (text === '' || waiting) return;

    setDraft('');
    setError(null);
    setMessages((prev) => [...prev, { text, fromBot: false, at: new Date().toISOString() }]);
    setWaiting(true);

    try {
      await api.send(threadId, text);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setWaiting(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <button className="new-chat" onClick={() => setThreadId(newThreadId())}>
          + Cuộc trò chuyện mới
        </button>

        <div className="section-label">Gần đây</div>
        <nav className="thread-list">
          {threads.length === 0 && <p className="empty">Chưa có cuộc trò chuyện nào.</p>}
          {threads.map((t) => (
            <button
              key={t.threadId}
              className={`thread${t.threadId === threadId ? ' active' : ''}`}
              onClick={() => setThreadId(t.threadId)}
              title={t.lastText}
            >
              <span className="thread-text">{t.lastText}</span>
              <span className="thread-count">{t.messageCount}</span>
            </button>
          ))}
        </nav>

        <div className="brand">Chiến Assistant</div>
      </aside>

      <main className="main">
        {messages.length === 0 && !waiting ? (
          <div className="hero">
            <h1>Hôm nay bạn cần gì?</h1>
          </div>
        ) : (
          <div className="messages">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.fromBot ? 'bot' : 'user'}`}>
                {m.text}
              </div>
            ))}
            {waiting && <div className="msg bot thinking">Đang trả lời…</div>}
            <div ref={bottomRef} />
          </div>
        )}

        {error !== null && <div className="error">{error}</div>}

        <form className="composer" onSubmit={submit}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Hỏi bất cứ điều gì"
            autoFocus
          />
          <button type="submit" disabled={waiting || draft.trim() === ''}>
            Gửi
          </button>
        </form>
      </main>
    </div>
  );
}
