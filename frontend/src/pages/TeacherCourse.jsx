import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
import {
  Loading, ErrorState, EmptyState, ErrorBanner, Badge,
  formatDate, formatBytes, materialTypeLabel,
} from "../components/ui.jsx";

export default function TeacherCourse() {
  const { courseId } = useParams();

  const [structure, setStructure] = useState(null);
  const [materials, setMaterials] = useState(null);
  const [loadError, setLoadError] = useState("");

  async function load() {
    setLoadError("");
    setStructure(null);
    setMaterials(null);
    try {
      const [s, m] = await Promise.all([
        api.getStructure(courseId),
        api.listMaterials(courseId),
      ]);
      setStructure(s);
      setMaterials(m);
    } catch (err) {
      setLoadError(err.message);
    }
  }
  useEffect(() => { load(); }, [courseId]);

  if (loadError) {
    return (
      <div>
        <Crumb />
        <div className="card card-pad"><ErrorState message={loadError} onRetry={load} /></div>
      </div>
    );
  }
  if (!structure) {
    return (
      <div>
        <Crumb />
        <div className="card card-pad"><Loading label="Loading course..." /></div>
      </div>
    );
  }

  const isEmpty = (structure.units || []).length === 0;

  return (
    <div>
      <Crumb name={structure.name} />
      <div className="page-head">
        <div>
          <h1>{structure.name}</h1>
          <p className="sub">{structure.description || "Upload materials, then check the structure below."}</p>
        </div>
        <Link className="btn btn-ghost btn-sm" to={`/student/courses/${courseId}`}>Open student view</Link>
      </div>

      <div className="two-col">
        <UploadPanel courseId={courseId} onDone={load} />

        <div className="stack">
          {isEmpty ? (
            <GetStarted />
          ) : (
            <>
              <StructureCard structure={structure} />
              <MaterialsCard materials={materials} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Crumb({ name }) {
  return (
    <div className="crumb">
      <Link to="/teacher">Teacher</Link>
      <span>/</span>
      <span>{name || "Course"}</span>
    </div>
  );
}

function GetStarted() {
  return (
    <div className="card card-pad getstarted">
      <div className="gs-icon" aria-hidden="true">✦</div>
      <h2 className="gs-title">Bring this course to life</h2>
      <p className="gs-text">
        Upload your first material on the left. We split it into passages, embed them, and make
        them searchable, so students get answers with exact citations.
      </p>
      <ol className="gs-steps">
        <li><span className="gs-num">1</span> Upload a PDF: lecture notes, a chapter, or the syllabus.</li>
        <li><span className="gs-num">2</span> We process and index it automatically.</li>
        <li><span className="gs-num">3</span> Students ask questions and get grounded answers.</li>
      </ol>
    </div>
  );
}

function UploadPanel({ courseId, onDone }) {
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [unit, setUnit] = useState("");
  const [lesson, setLesson] = useState("");
  const [type, setType] = useState("pdf");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  function pickFile(f) {
    if (!f) return;
    const isPdf = f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setError("Please choose a PDF file.");
      return;
    }
    setError("");
    setResult(null);
    setFile(f);
  }

  function clearFile() {
    setFile(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handleUpload(e) {
    e.preventDefault();
    setError("");
    setResult(null);

    if (!file) {
      setError("Please choose a PDF file to upload.");
      return;
    }

    const fd = new FormData();
    fd.append("file", file);
    fd.append("unit_name", unit.trim());
    fd.append("lesson_name", lesson.trim());
    fd.append("material_type", type);

    setBusy(true);
    try {
      const res = await api.ingest(courseId, fd);
      setResult(res);
      clearFile();       // keep unit/lesson so several files land together
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card card-pad" onSubmit={handleUpload}>
      <div className="card-title">Upload material</div>
      <p className="card-sub" style={{ marginBottom: "var(--s4)" }}>
        Add a PDF. It is split, embedded, and made searchable for students.
      </p>

      <div className="field">
        <label>PDF file</label>
        <div
          className={`dropzone ${dragOver ? "over" : ""}`}
          role="button"
          tabIndex={0}
          aria-label="Choose a PDF file or drop one here"
          onClick={() => !busy && fileRef.current?.click()}
          onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !busy) { e.preventDefault(); fileRef.current?.click(); } }}
          onDragOver={(e) => { e.preventDefault(); if (!busy) setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); if (!busy) pickFile(e.dataTransfer.files?.[0]); }}
        >
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            hidden
            onChange={(e) => pickFile(e.target.files?.[0])}
            disabled={busy}
          />
          {file ? (
            <div className="dz-file">
              <span className="dz-doc" aria-hidden="true">PDF</span>
              <div className="dz-meta">
                <div className="dz-name">{file.name}</div>
                <div className="dz-size">{formatBytes(file.size)}</div>
              </div>
              <button type="button" className="dz-clear" aria-label="Remove file"
                      onClick={(e) => { e.stopPropagation(); clearFile(); }} disabled={busy}>✕</button>
            </div>
          ) : (
            <div className="dz-empty">
              <div className="dz-icon" aria-hidden="true">⇪</div>
              <div><span className="dz-strong">Choose a PDF</span> or drag it here</div>
              <div className="dz-hint">PDF files only</div>
            </div>
          )}
        </div>
      </div>

      <div className="field">
        <label htmlFor="unit">Unit <span className="hint">(optional)</span></label>
        <input id="unit" className="input" value={unit} placeholder="e.g. Cell Biology"
               onChange={(e) => setUnit(e.target.value)} disabled={busy} />
      </div>

      <div className="field">
        <label htmlFor="lesson">Lesson <span className="hint">(optional)</span></label>
        <input id="lesson" className="input" value={lesson} placeholder="e.g. Organelles"
               onChange={(e) => setLesson(e.target.value)} disabled={busy} />
      </div>

      <div className="field">
        <label htmlFor="type">Type</label>
        <select id="type" className="select" value={type} onChange={(e) => setType(e.target.value)} disabled={busy}>
          <option value="pdf">PDF document</option>
          <option value="syllabus">Syllabus</option>
          <option value="note">Important topics note</option>
        </select>
        <span className="hint">Leave unit and lesson blank for course-wide files like a syllabus.</span>
      </div>

      {error && <ErrorBanner message={error} />}
      {result && (
        <div className="notice-ok" style={{ marginTop: "var(--s2)" }}>
          Added {result.chunks_created} chunk{result.chunks_created === 1 ? "" : "s"} from {result.pages_processed} page{result.pages_processed === 1 ? "" : "s"}.
        </div>
      )}

      <button className="btn btn-primary btn-block" disabled={busy} style={{ marginTop: "var(--s3)" }}>
        {busy ? "Processing..." : "Upload and ingest"}
      </button>
    </form>
  );
}

function StructureCard({ structure }) {
  const units = structure.units || [];
  return (
    <div className="card card-pad">
      <div className="card-title">Course structure</div>
      <div className="tree" style={{ marginTop: "var(--s3)" }}>
        {units.map((u) => (
          <div key={u.id} className="tree-unit">
            <div className="row">{u.name}</div>
            <div style={{ padding: "6px 10px 10px" }}>
              {(u.lessons || []).map((l) => (
                <div key={l.id} className="tree-lesson">
                  <div className="row">{l.name}</div>
                  {(l.materials || []).map((m) => (
                    <div key={m.id} className="tree-material">
                      <span className="doc" aria-hidden="true">▸</span>
                      <span>{m.file_name}</span>
                      <Badge tone="muted">{materialTypeLabel(m.material_type)}</Badge>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MaterialsCard({ materials }) {
  if (!materials) return null;
  return (
    <div className="card card-pad">
      <div className="row-between" style={{ marginBottom: "var(--s3)" }}>
        <div className="card-title" style={{ margin: 0 }}>Materials</div>
        <Badge tone="brand">{materials.length} total</Badge>
      </div>
      {materials.length === 0 ? (
        <EmptyState compact icon="⇪" title="No materials yet" message="Upload your first file on the left." />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>File</th><th>Unit</th><th>Lesson</th><th>Type</th>
                <th className="num">Chunks</th><th>Added</th>
              </tr>
            </thead>
            <tbody>
              {materials.map((m) => (
                <tr key={m.id}>
                  <td>{m.file_name}</td>
                  <td>{m.unit}</td>
                  <td>{m.lesson}</td>
                  <td>{materialTypeLabel(m.material_type)}</td>
                  <td className="num">{m.chunk_count}</td>
                  <td>{formatDate(m.uploaded_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
