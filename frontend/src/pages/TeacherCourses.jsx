import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { Loading, ErrorState, EmptyState, ErrorBanner, Kpi, formatDate } from "../components/ui.jsx";

export default function TeacherCourses() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState(null);   // null = still loading
  const [stats, setStats] = useState(null);
  const [loadError, setLoadError] = useState("");

  // Create-form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  async function load() {
    setLoadError("");
    setCourses(null);
    try {
      // Courses are critical for the page to work.
      setCourses(await api.listCourses());
    } catch (err) {
      setLoadError(err.message);
      return;
    }
    // Stats are a nice-to-have. A failure here must not break the dashboard;
    // the KPI tiles just show a dash until the value is available.
    api.getStats().then(setStats).catch(() => setStats(null));
  }
  useEffect(() => { load(); }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setSaveError("");
    if (!name.trim()) {
      setNameError("Please enter a course name.");
      return;
    }
    setNameError("");
    setSaving(true);
    try {
      const created = await api.createCourse({ name: name.trim(), description: description.trim() });
      setName("");
      setDescription("");
      setCourses((prev) => [created, ...(prev || [])]);
      navigate(`/teacher/courses/${created.id}`);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(course, e) {
    e.stopPropagation();   // don't open the course when clicking Delete
    if (!window.confirm(`Delete "${course.name}" and all its materials? This cannot be undone.`)) return;
    try {
      await api.deleteCourse(course.id);
      setCourses((prev) => (prev || []).filter((c) => c.id !== course.id));
      api.getStats().then(setStats).catch(() => {});   // refresh the KPIs
    } catch (err) {
      alert(err.message);
    }
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Teacher dashboard</h1>
          <p className="sub">Create a course, then upload materials for students to ask about.</p>
        </div>
      </div>

      <div className="kpi-row" style={{ marginBottom: "var(--s6)" }}>
        <Kpi label="Courses" value={stats?.courses} />
        <Kpi label="Materials" value={stats?.materials} />
        <Kpi label="Questions asked" value={stats?.questions} />
      </div>

      <div className="two-col">
        {/* Create panel */}
        <form className="card card-pad" onSubmit={handleCreate}>
          <div className="card-title">New course</div>
          <p className="card-sub" style={{ marginBottom: "var(--s4)" }}>Give it a clear name students will recognise.</p>

          <div className="field">
            <label htmlFor="c-name">Course name</label>
            <input
              id="c-name"
              className={`input ${nameError ? "invalid" : ""}`}
              value={name}
              placeholder="e.g. IB Biology"
              onChange={(e) => { setName(e.target.value); if (nameError) setNameError(""); }}
              disabled={saving}
            />
            {nameError && <span className="field-error">{nameError}</span>}
          </div>

          <div className="field">
            <label htmlFor="c-desc">Description <span className="hint">(optional)</span></label>
            <textarea
              id="c-desc"
              className="textarea"
              value={description}
              placeholder="A short summary of the course."
              onChange={(e) => setDescription(e.target.value)}
              disabled={saving}
            />
          </div>

          {saveError && <ErrorBanner message={saveError} />}

          <button className="btn btn-primary btn-block" disabled={saving} style={{ marginTop: "var(--s3)" }}>
            {saving ? "Creating..." : "Create course"}
          </button>
        </form>

        {/* Course list */}
        <div>
          {courses === null && !loadError && <div className="card card-pad"><Loading label="Loading courses..." /></div>}

          {loadError && <div className="card card-pad"><ErrorState message={loadError} onRetry={load} /></div>}

          {courses && courses.length === 0 && (
            <div className="card card-pad">
              <EmptyState icon="+" title="No courses yet" message="Create your first course with the form on the left." />
            </div>
          )}

          {courses && courses.length > 0 && (
            <div className="grid">
              {courses.map((c) => (
                <div key={c.id} className="course-card" onClick={() => navigate(`/teacher/courses/${c.id}`)}
                     role="button" tabIndex={0}
                     onKeyDown={(e) => { if (e.key === "Enter") navigate(`/teacher/courses/${c.id}`); }}>
                  <h3>{c.name}</h3>
                  <p className="desc">{c.description || "No description."}</p>
                  <div className="meta">
                    <span>Created {formatDate(c.created_at)}</span>
                    <button className="card-del" aria-label={`Delete ${c.name}`}
                            onClick={(e) => handleDelete(c, e)}
                            onKeyDown={(e) => e.stopPropagation()}>Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
