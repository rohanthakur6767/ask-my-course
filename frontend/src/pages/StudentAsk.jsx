import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { Spinner, ErrorBanner, Badge, ConfidenceMeter } from "../components/ui.jsx";

export default function StudentAsk() {
  const { courseId } = useParams();

  const [courseName, setCourseName] = useState("");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  // Load the course name and recent history once.
  useEffect(() => {
    let alive = true;
    api.getStructure(courseId).then((s) => { if (alive) setCourseName(s.name); }).catch(() => {});
    api.getHistory(courseId, 10).then((h) => { if (alive) setHistory(h); }).catch(() => {});
    return () => { alive = false; };
  }, [courseId]);

  async function handleAsk(e) {
    e.preventDefault();
    setAskError("");
    if (!question.trim()) {
      setAskError("Please type a question first.");
      return;
    }
    setAsking(true);
    setResult(null);
    try {
      const res = await api.ask(courseId, question.trim());
      setResult(res);
      // Refresh the recent list so this question appears.
      api.getHistory(courseId, 10).then(setHistory).catch(() => {});
    } catch (err) {
      setAskError(err.message);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div>
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
      </div>

      <form className="card card-pad" onSubmit={handleAsk}>
        <div className="field" style={{ marginBottom: "var(--s3)" }}>
          <label htmlFor="q">Your question</label>
          <textarea
            id="q"
            className="textarea"
            value={question}
            placeholder="e.g. What are the main functions of the cell membrane?"
            onChange={(e) => { setQuestion(e.target.value); if (askError) setAskError(""); }}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleAsk(e); }}
            disabled={asking}
          />
          <span className="hint">Tip: press Ctrl/Cmd + Enter to ask.</span>
        </div>

        {askError && <ErrorBanner message={askError} />}

        <button className="btn btn-primary" disabled={asking} style={{ marginTop: "var(--s2)" }}>
          {asking ? <span className="spin-row"><Spinner /> Thinking...</span> : "Ask"}
        </button>
      </form>

      {result && <AnswerCard result={result} />}

      {history.length > 0 && (
        <div className="card card-pad" style={{ marginTop: "var(--s5)" }}>
          <div className="card-title" style={{ marginBottom: "var(--s3)" }}>Recent questions</div>
          <div className="stack" style={{ gap: "var(--s3)" }}>
            {history.map((h) => (
              <div key={h.id} className="recent-item">
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>{truncate(h.question, 90)}</div>
                  <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
                    {h.guardrail_triggered ? "Not found in materials" : truncate(h.answer, 120)}
                  </div>
                </div>
                {h.guardrail_triggered
                  ? <Badge tone="warn">refused</Badge>
                  : <Badge tone="ok">{Math.round((h.confidence || 0) * 100)}%</Badge>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AnswerCard({ result }) {
  const { answer, sources = [], confidence, guardrail_triggered } = result;

  if (guardrail_triggered) {
    return (
      <div className="card card-pad" style={{ marginTop: "var(--s5)" }}>
        <div className="row-between" style={{ marginBottom: "var(--s3)" }}>
          <div className="card-title" style={{ margin: 0 }}>Answer</div>
          <Badge tone="warn">Not in materials</Badge>
        </div>
        <div className="answer-refused">{answer}</div>
      </div>
    );
  }

  return (
    <div className="card card-pad" style={{ marginTop: "var(--s5)" }}>
      <div className="row-between" style={{ marginBottom: "var(--s3)" }}>
        <div className="card-title" style={{ margin: 0 }}>Answer</div>
        <div style={{ width: 180 }}>
          <ConfidenceMeter value={confidence} />
        </div>
      </div>

      <div className="answer">{answer}</div>

      {sources.length > 0 && (
        <div style={{ marginTop: "var(--s5)" }}>
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
  );
}

function truncate(text, n) {
  if (!text) return "";
  return text.length > n ? text.slice(0, n) + "..." : text;
}
