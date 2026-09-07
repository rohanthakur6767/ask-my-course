import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { Loading, ErrorState, EmptyState } from "../components/ui.jsx";

export default function StudentHome() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    setCourses(null);
    try {
      setCourses(await api.listCourses());
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Ask your course</h1>
          <p className="sub">Pick a course, then ask anything. Answers come only from its materials.</p>
        </div>
      </div>

      {courses === null && !error && <div className="card card-pad"><Loading label="Loading courses..." /></div>}
      {error && <div className="card card-pad"><ErrorState message={error} onRetry={load} /></div>}

      {courses && courses.length === 0 && (
        <div className="card card-pad">
          <EmptyState icon="?" title="No courses available" message="Ask your teacher to create a course and upload materials." />
        </div>
      )}

      {courses && courses.length > 0 && (
        <div className="grid">
          {courses.map((c) => (
            <div key={c.id} className="course-card" role="button" tabIndex={0}
                 onClick={() => navigate(`/student/courses/${c.id}`)}
                 onKeyDown={(e) => { if (e.key === "Enter") navigate(`/student/courses/${c.id}`); }}>
              <h3>{c.name}</h3>
              <p className="desc">{c.description || "No description."}</p>
              <div className="meta">Tap to ask a question</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
