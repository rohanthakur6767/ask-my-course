import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { Loading, ErrorState, EmptyState, Badge, Kpi } from "../components/ui.jsx";

export default function TeacherInsights() {
  const { courseId } = useParams();

  const [courseName, setCourseName] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    setData(null);
    try {
      const [insights, structure] = await Promise.all([
        api.getInsights(courseId),
        api.getStructure(courseId).catch(() => ({ name: "" })),
      ]);
      setCourseName(structure.name || "");
      setData(insights);
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => { load(); }, [courseId]);

  return (
    <div>
      <div className="crumb">
        <Link to="/teacher">Teacher</Link>
        <span>/</span>
        <Link to={`/teacher/courses/${courseId}`}>{courseName || "Course"}</Link>
        <span>/</span>
        <span>Common doubts</span>
      </div>

      <div className="page-head">
        <div>
          <h1>Common doubts</h1>
          <p className="sub">What students actually ask, and where the course has gaps.</p>
        </div>
        <Link className="btn btn-ghost btn-sm" to={`/teacher/courses/${courseId}`}>Back to course</Link>
      </div>

      {!data && !error && <div className="card card-pad"><Loading label="Reading the questions..." /></div>}
      {error && <div className="card card-pad"><ErrorState message={error} onRetry={load} /></div>}

      {data && data.total_questions === 0 && (
        <div className="card card-pad">
          <EmptyState
            icon="?"
            title="No questions yet"
            message="Once students start asking, their most common questions and any content gaps will show up here."
          />
        </div>
      )}

      {data && data.total_questions > 0 && (
        <>
          <div className="kpi-row" style={{ marginBottom: "var(--s6)" }}>
            <Kpi label="Questions asked" value={data.total_questions} />
            <Kpi label="Answered" value={data.answered_count} />
            <Kpi label="Content gaps" value={data.refused_count} />
            <Kpi label="Avg confidence" value={`${Math.round((data.avg_confidence || 0) * 100)}%`} />
          </div>

          <div className="two-col">
            {/* Gaps first: this is the most useful column for a teacher. */}
            <div className="card card-pad">
              <div className="row-between" style={{ marginBottom: "var(--s2)" }}>
                <div className="card-title" style={{ margin: 0 }}>Content gaps</div>
                <Badge tone="warn">{data.gaps.length}</Badge>
              </div>
              <p className="card-sub" style={{ marginBottom: "var(--s4)" }}>
                Questions the assistant refused, because the answer is not in the materials.
                These are the topics worth adding next.
              </p>
              {data.gaps.length === 0 ? (
                <EmptyState compact icon="✓" title="No gaps"
                  message="Every question was answered from the course materials." />
              ) : (
                <div className="stack" style={{ gap: "var(--s3)" }}>
                  {data.gaps.map((g, i) => (
                    <div key={i} className="recent-item">
                      <div style={{ fontWeight: 600 }}>{g.question}</div>
                      <Badge tone="warn">{g.count > 1 ? `${g.count}× asked` : "asked"}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card card-pad">
              <div className="row-between" style={{ marginBottom: "var(--s2)" }}>
                <div className="card-title" style={{ margin: 0 }}>Most asked</div>
                <Badge tone="brand">{data.top_questions.length}</Badge>
              </div>
              <p className="card-sub" style={{ marginBottom: "var(--s4)" }}>
                The questions students ask most often in this course.
              </p>
              {data.top_questions.length === 0 ? (
                <EmptyState compact icon="?" title="Nothing yet"
                  message="Questions will appear here as students ask them." />
              ) : (
                <div className="stack" style={{ gap: "var(--s3)" }}>
                  {data.top_questions.map((q, i) => (
                    <div key={i} className="recent-item">
                      <div style={{ fontWeight: 600 }}>{q.question}</div>
                      <Badge tone={q.count > 1 ? "ok" : "muted"}>
                        {q.count > 1 ? `${q.count}×` : "1×"}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
