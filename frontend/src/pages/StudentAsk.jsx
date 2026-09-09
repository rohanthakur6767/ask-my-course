import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
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

  // Restore an in-progress conversation for this course (survives a page refresh).
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storeKey) || "null");
      if (saved && saved.conversationId) {
        convId.current = saved.conversationId;
        setMessages(saved.messages || []);
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
      setMessages((prev) => [...prev, { role: "assistant", result: res }]);
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
            : <AnswerBubble key={i} result={m.result} />
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

function AnswerBubble({ result }) {
  const { answer, sources = [], confidence, guardrail_triggered } = result;
  const [copied, setCopied] = useState(false);

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

        <div className="answer"><ReactMarkdown>{answer}</ReactMarkdown></div>

        {hasSources && (
          <div style={{ marginTop: "var(--s4)" }}>
            <div className="card-sub" style={{ marginBottom: "var(--s2)", fontWeight: 600 }}>Sources</div>
            <div className="sources">
              {sources.map((s, i) => (
                <div key={i} className="source">
                  <div>
                    <span className="path">{s.unit} &rsaquo; {s.lesson}</span>
                    {s.page != null && <span className="page"> · page {s.page}</span>}
                  </div>
                  <Badge tone="muted">{Math.round((s.relevance_score || 0) * 100)}% match</Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
