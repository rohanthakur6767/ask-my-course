import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, fileUrl } from "../api/client.js";
import ReactMarkdown from "react-markdown";
import { Spinner, ErrorBanner, Badge, ConfidenceMeter } from "../components/ui.jsx";

// A conversation is a thread of turns that share one conversation_id, so the
// backend can feed the last few turns to the model and understand follow-ups
// like "explain that more simply".
function newConversationId() {
  if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
  // Fallback for older/non-secure contexts.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    return (ch === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export default function StudentAsk() {
  const { courseId } = useParams();
  const storeKey = `amc.chat.${courseId}`;

  const [courseName, setCourseName] = useState("");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");
  const [messages, setMessages] = useState([]);      // { role: "user"|"assistant", ... }
  const [suggestions, setSuggestions] = useState([]);

  const convId = useRef(null);
  const bottomRef = useRef(null);
  const scrollToBottom = () => bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });

  // Restore an in-progress conversation for this course (survives a page refresh).
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storeKey) || "null");
      if (saved && saved.conversationId) {
        convId.current = saved.conversationId;
        // Restored answers show instantly (only freshly-asked ones "type").
        setMessages((saved.messages || []).map((m) => ({ ...m, animate: false })));
      }
    } catch { /* ignore malformed storage */ }
    if (!convId.current) convId.current = newConversationId();
  }, [storeKey]);

  // Load the course name and starter questions once.
  useEffect(() => {
    let alive = true;
    api.getStructure(courseId).then((s) => { if (alive) setCourseName(s.name); }).catch(() => {});
    api.getSuggestions(courseId).then((r) => { if (alive) setSuggestions(r.questions || []); }).catch(() => {});
    return () => { alive = false; };
  }, [courseId]);

  // Persist the thread so a refresh does not lose the conversation.
  useEffect(() => {
    try {
      sessionStorage.setItem(storeKey, JSON.stringify({
        conversationId: convId.current,
        messages,
      }));
    } catch { /* storage full or blocked; not critical */ }
  }, [messages, storeKey]);

  // Keep the newest turn in view.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, asking]);

  async function runAsk(text) {
    const q = (text || "").trim();
    if (!q || asking) {
      if (!q) setAskError("Please type a question first.");
      return;
    }
    setAskError("");
    setQuestion("");
    setAsking(true);
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    try {
      const res = await api.ask(courseId, q, 5, convId.current);
      // The backend echoes the conversation_id; keep ours in sync.
      if (res.conversation_id) convId.current = res.conversation_id;
      setMessages((prev) => [...prev, { role: "assistant", result: res, animate: true }]);
    } catch (err) {
      setAskError(err.message);
    } finally {
      setAsking(false);
    }
  }

  function handleAsk(e) {
    e.preventDefault();
    runAsk(question);
  }

  function newChat() {
    convId.current = newConversationId();
    setMessages([]);
    setAskError("");
    setQuestion("");
    try { sessionStorage.removeItem(storeKey); } catch { /* ignore */ }
  }

  const empty = messages.length === 0;

  return (
    <div className="chat-page">
      <div className="crumb">
        <Link to="/student">Courses</Link>
        <span>/</span>
        <span>{courseName || "Course"}</span>
      </div>

      <div className="page-head">
        <div>
          <h1>{courseName || "Ask a question"}</h1>
          <p className="sub">Answers are drawn only from this course's materials, with sources.</p>
        </div>
        {!empty && (
          <button className="btn btn-ghost btn-sm" onClick={newChat} disabled={asking}>
            New chat
          </button>
        )}
      </div>

      <div className="thread">
        {empty && !asking && (
          <div className="chat-welcome">
            <div className="cw-icon" aria-hidden="true">✦</div>
            <h3>Ask this course anything</h3>
            <p>Every answer is grounded in the uploaded materials and cites its Unit, Lesson, and Page. Ask a follow-up and it remembers the conversation.</p>
            {suggestions.length > 0 && (
              <div className="chips" style={{ justifyContent: "center", marginTop: "var(--s4)" }}>
                {suggestions.map((s, i) => (
                  <button key={i} type="button" className="chip" onClick={() => runAsk(s)} disabled={asking}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user"
            ? <UserBubble key={i} text={m.text} />
            : <AnswerBubble key={i} result={m.result} animate={m.animate} onGrow={scrollToBottom} />
        )}

        {asking && <ThinkingBubble />}

        <div ref={bottomRef} />
      </div>

      <form className="composer" onSubmit={handleAsk}>
        {askError && <div style={{ marginBottom: "var(--s3)" }}><ErrorBanner message={askError} /></div>}
        <div className="composer-row">
          <textarea
            className="textarea composer-input"
            value={question}
            placeholder="Ask a question about this course..."
            onChange={(e) => { setQuestion(e.target.value); if (askError) setAskError(""); }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleAsk(e); }
            }}
            rows={1}
            disabled={asking}
          />
          <button className="btn btn-primary composer-send" disabled={asking || !question.trim()}>
            {asking ? <Spinner /> : "Ask"}
          </button>
        </div>
        <span className="hint">Press Enter to send · Shift + Enter for a new line</span>
      </form>
    </div>
  );
}

function UserBubble({ text }) {
  return (
    <div className="turn turn-user">
      <div className="bubble bubble-user">{text}</div>
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="turn turn-assistant">
      <div className="bubble bubble-assistant bubble-thinking">
        <span className="spin-row"><Spinner /> Searching the course materials...</span>
      </div>
    </div>
  );
}

// Reveal `text` progressively for a "typing" feel. Freshly-asked answers animate;
// restored ones (animate=false) and reduced-motion users see it instantly.
function useTypedReveal(text, animate, onGrow) {
  const [n, setN] = useState(animate ? 0 : text.length);
  useEffect(() => {
    if (!animate ||
        (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) {
      setN(text.length);
      return;
    }
    let i = 0;
    const step = Math.max(1, Math.ceil(text.length / 75));  // reveal in ~75 ticks (~1.5s)
    const id = setInterval(() => {
      i += step;
      if (i >= text.length) { setN(text.length); clearInterval(id); }
      else { setN(i); if (onGrow) onGrow(); }
    }, 20);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, animate]);
  return { shown: text.slice(0, n), done: n >= text.length };
}

function AnswerBubble({ result, animate = false, onGrow }) {
  const { answer, sources = [], confidence, guardrail_triggered } = result;
  const [copied, setCopied] = useState(false);
  const { shown, done } = useTypedReveal(answer, animate && !guardrail_triggered, onGrow);

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard blocked (e.g. non-HTTPS context); ignore quietly */ }
  }

  if (guardrail_triggered) {
    return (
      <div className="turn turn-assistant">
        <div className="bubble bubble-assistant">
          <div className="row-between" style={{ marginBottom: "var(--s2)" }}>
            <span className="bubble-tag">Answer</span>
            <Badge tone="warn">Not in materials</Badge>
          </div>
          <div className="answer-refused">{answer}</div>
        </div>
      </div>
    );
  }

  const hasSources = sources.length > 0;
  // Only list sources strong enough to be worth showing. The guardrail already
  // guarantees the best match is >= 0.5, so at least one source always remains.
  const shownSources = sources.filter((s) => (s.relevance_score || 0) >= 0.5);

  return (
    <div className="turn turn-assistant">
      <div className="bubble bubble-assistant">
        <div className="row-between" style={{ marginBottom: "var(--s2)" }}>
          <span className="bubble-tag">Answer</span>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--s3)" }}>
            {hasSources && <div style={{ width: 130 }}><ConfidenceMeter value={confidence} /></div>}
            <button className="btn btn-ghost btn-sm" onClick={copyAnswer}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>

        <div className="answer">
          <ReactMarkdown>{shown}</ReactMarkdown>
          {!done && <span className="type-cursor" aria-hidden="true" />}
        </div>

        {done && shownSources.length > 0 && (
          <div style={{ marginTop: "var(--s4)" }}>
            <div className="card-sub" style={{ marginBottom: "var(--s2)", fontWeight: 600 }}>Sources</div>
            <div className="sources">
              {shownSources.map((s, i) => {
                // "Open" points at a viewable PDF at the exact page/slide (native for
                // PDFs, a converted copy for Word/PowerPoint); "Download" is the original.
                const open = fileUrl(s.link);
                const download = fileUrl(s.source_url);
                return (
                  <div key={i} className="source">
                    <div style={{ minWidth: 0 }}>
                      <span className="src-num">Source {i + 1}:</span>{" "}
                      <span className="path">{s.file_name || `${s.unit} › ${s.lesson}`}</span>
                      {s.location_label && <span className="page"> &mdash; {s.location_label}</span>}
                      {(open || download) && (
                        <span className="src-actions">
                          {open && <a href={open} target="_blank" rel="noopener noreferrer">Open</a>}
                          {download && <a href={download} download>Download</a>}
                        </span>
                      )}
                    </div>
                    <Badge tone="muted">{Math.round((s.relevance_score || 0) * 100)}% match</Badge>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
