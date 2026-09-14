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
        <div style={{ display: "flex", gap: "var(--s2)" }}>
          <Link className="btn btn-ghost btn-sm" to={`/teacher/courses/${courseId}/insights`}>Common doubts</Link>
          <Link className="btn btn-ghost btn-sm" to={`/student/courses/${courseId}`}>Open student view</Link>
        </div>
      </div>

      <div className="two-col">
        <div className="stack">
          <FolderUploadPanel courseId={courseId} onDone={load} />
          <UploadPanel courseId={courseId} onDone={load} />
        </div>

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
        Upload your first material on the left. Analyze it and we detect the units
        and lessons for you, then embed everything so students get answers with
        exact citations.
      </p>
      <ol className="gs-steps">
        <li><span className="gs-num">1</span> Choose a PDF: lecture notes, a chapter, or the syllabus.</li>
        <li><span className="gs-num">2</span> Analyze: we propose the units and lessons; you confirm.</li>
        <li><span className="gs-num">3</span> Students ask questions and get grounded answers.</li>
      </ol>
    </div>
  );
}

function UploadPanel({ courseId, onDone }) {
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [type, setType] = useState("pdf");

  const [step, setStep] = useState("choose");   // "choose" | "review"
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  // analyze results (for the review step)
  const [filePath, setFilePath] = useState("");
  const [fileName, setFileName] = useState("");
  const [segments, setSegments] = useState([]);

  // manual "single lesson" fallback
  const [unit, setUnit] = useState("");
  const [lesson, setLesson] = useState("");

  function pickFile(f) {
    if (!f) return;
    const isPdf = f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) { setError("Please choose a PDF file."); return; }
    setError("");
    setResult(null);
    setFile(f);
  }

  function clearFile() {
    setFile(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  function backToChoose() {
    setStep("choose");
    setSegments([]);
    setFilePath("");
    setFileName("");
    setError("");
  }

  async function handleAnalyze() {
    if (!file) { setError("Please choose a PDF first."); return; }
    setError(""); setResult(null); setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.analyze(courseId, fd);
      setFilePath(res.file_path);
      setFileName(res.file_name);
      setSegments(res.outline || []);
      setStep("review");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (segments.length === 0) { setError("Add at least one unit and lesson."); return; }
    setError(""); setBusy(true);
    try {
      const res = await api.ingestStructured(courseId, {
        file_path: filePath,
        file_name: fileName,
        material_type: type,
        outline: segments,
      });
      setResult(res);
      backToChoose();
      clearFile();
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleManualUpload(e) {
    e.preventDefault();
    if (!file) { setError("Please choose a PDF first."); return; }
    setError(""); setResult(null); setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("unit_name", unit.trim());
      fd.append("lesson_name", lesson.trim());
      fd.append("material_type", type);
      const res = await api.ingest(courseId, fd);
      setResult(res);
      clearFile();
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // --- segment editing (review step) ---
  const updateSeg = (i, field, value) =>
    setSegments((s) => s.map((seg, idx) => (idx === i ? { ...seg, [field]: value } : seg)));
  const removeSeg = (i) => setSegments((s) => s.filter((_, idx) => idx !== i));
  const addSeg = () => setSegments((s) => [...s, { unit: "", lesson: "", page_start: 1, page_end: 1 }]);

  // ================= REVIEW STEP =================
  if (step === "review") {
    return (
      <div className="card card-pad">
        <div className="card-title">Confirm the structure</div>
        <p className="card-sub" style={{ marginBottom: "var(--s4)" }}>
          We detected these units and lessons in <strong>{fileName}</strong>. Edit anything,
          then confirm to ingest.
        </p>

        <div className="outline">
          {segments.map((seg, i) => (
            <div key={i} className="outline-seg">
              <span className="lbl">Unit</span>
              <input className="input" value={seg.unit}
                     onChange={(e) => updateSeg(i, "unit", e.target.value)} disabled={busy} />
              <span className="lbl">Lesson</span>
              <input className="input" value={seg.lesson}
                     onChange={(e) => updateSeg(i, "lesson", e.target.value)} disabled={busy} />
              <div className="foot">
                <span className="pages">
                  pages
                  <input className="input" type="number" min="1" value={seg.page_start}
                         onChange={(e) => updateSeg(i, "page_start", Number(e.target.value) || 1)} disabled={busy} />
                  to
                  <input className="input" type="number" min="1" value={seg.page_end}
                         onChange={(e) => updateSeg(i, "page_end", Number(e.target.value) || 1)} disabled={busy} />
                </span>
                <button type="button" className="outline-del" aria-label="Remove"
                        onClick={() => removeSeg(i)} disabled={busy}>✕</button>
              </div>
            </div>
          ))}
        </div>

        <button type="button" className="btn btn-ghost btn-sm btn-block" onClick={addSeg}
                disabled={busy} style={{ marginTop: "var(--s3)" }}>
          + Add unit / lesson
        </button>

        {error && <div style={{ marginTop: "var(--s3)" }}><ErrorBanner message={error} /></div>}

        <div style={{ display: "flex", gap: "var(--s2)", marginTop: "var(--s4)" }}>
          <button type="button" className="btn btn-ghost" onClick={backToChoose} disabled={busy}>Back</button>
          <button type="button" className="btn btn-primary" style={{ flex: 1 }} onClick={handleConfirm} disabled={busy}>
            {busy ? "Ingesting..." : "Confirm and ingest"}
          </button>
        </div>
      </div>
    );
  }

  // ================= CHOOSE STEP =================
  return (
    <div className="card card-pad">
      <div className="card-title">Upload material</div>
      <p className="card-sub" style={{ marginBottom: "var(--s4)" }}>
        Add a PDF. Analyze it to detect units and lessons automatically.
      </p>

      <div className="field">
        <label>PDF file</label>
        <div
          className={`dropzone ${dragOver ? "over" : ""}`}
          role="button" tabIndex={0}
          aria-label="Choose a PDF file or drop one here"
          onClick={() => !busy && fileRef.current?.click()}
          onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !busy) { e.preventDefault(); fileRef.current?.click(); } }}
          onDragOver={(e) => { e.preventDefault(); if (!busy) setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); if (!busy) pickFile(e.dataTransfer.files?.[0]); }}
        >
          <input ref={fileRef} type="file" accept="application/pdf,.pdf" hidden
                 onChange={(e) => pickFile(e.target.files?.[0])} disabled={busy} />
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
        <label htmlFor="type">Type</label>
        <select id="type" className="select" value={type} onChange={(e) => setType(e.target.value)} disabled={busy}>
          <option value="pdf">PDF document</option>
          <option value="syllabus">Syllabus</option>
          <option value="note">Important topics note</option>
        </select>
      </div>

      {error && <ErrorBanner message={error} />}
      {result && (
        <div className="notice-ok" style={{ marginTop: "var(--s2)" }}>
          Added {result.chunks_created} chunk{result.chunks_created === 1 ? "" : "s"}
          {result.materials_created ? ` across ${result.materials_created} lesson${result.materials_created === 1 ? "" : "s"}` : ""}.
        </div>
      )}

      <button type="button" className="btn btn-primary btn-block" onClick={handleAnalyze} disabled={busy}
              style={{ marginTop: "var(--s3)" }}>
        {busy ? "Analyzing..." : "Analyze with AI"}
      </button>

      <div className="or-divider">or add as a single lesson</div>

      <form onSubmit={handleManualUpload}>
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
        <button className="btn btn-ghost btn-block" disabled={busy}>
          {busy ? "Working..." : "Upload as one lesson"}
        </button>
      </form>
    </div>
  );
}

const FOLDER_SUPPORTED = ["pdf", "docx", "pptx"];

function FolderUploadPanel({ courseId, onDone }) {
  const inputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(null);   // { done, total, current }

  // webkitdirectory isn't a standard React prop, so set it on the DOM element.
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.setAttribute("webkitdirectory", "");
      inputRef.current.setAttribute("directory", "");
    }
  }, []);

  function pick(fileList) {
    const kept = Array.from(fileList || []).filter((f) =>
      FOLDER_SUPPORTED.includes((f.name.split(".").pop() || "").toLowerCase())
    );
    setError(kept.length === 0 ? "No PDF, DOCX, or PPTX files found in that folder." : "");
    setResult(null);
    setFiles(kept);
  }

  async function upload() {
    if (files.length === 0) { setError("Choose a folder first."); return; }
    setBusy(true); setError(""); setResult(null);

    // Upload ONE FILE AT A TIME. This way a single unreadable file (e.g. a
    // cloud-only OneDrive file, or one open in Word/PowerPoint) fails on its own
    // with a clear message, instead of killing the whole batch.
    const ingested = [];
    const failed = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      setProgress({ done: i, total: files.length, current: f.name });
      try {
        const fd = new FormData();
        fd.append("files", f);
        fd.append("paths", f.webkitRelativePath || f.name);
        const res = await api.ingestFolder(courseId, fd);
        (res.ingested || []).forEach((x) => ingested.push(x));
        (res.failed || []).forEach((x) => failed.push(x));
      } catch (err) {
        // fetch itself threw: the browser could not read/send this file.
        failed.push({
          file: f.name,
          error: err.message === "Cannot reach the server. Is the backend running?"
            ? "Could not read this file (it may be cloud-only/OneDrive, or open in another app)."
            : err.message,
        });
      }
    }

    setProgress(null);
    setResult({
      files_ingested: ingested.length,
      files_failed: failed.length,
      total_chunks: ingested.reduce((a, x) => a + (x.chunks || 0), 0),
      ingested, failed,
    });
    setFiles([]);
    if (inputRef.current) inputRef.current.value = "";
    onDone();
    setBusy(false);
  }

  return (
    <div className="card card-pad">
      <div className="card-title">Upload a course folder</div>
      <p className="card-sub" style={{ marginBottom: "var(--s4)" }}>
        Pick a folder of PDF, Word, and PowerPoint files. Sub-folders become units.
      </p>

      <input ref={inputRef} type="file" multiple hidden
             onChange={(e) => pick(e.target.files)} disabled={busy} />

      {files.length === 0 ? (
        <button type="button" className="btn btn-primary btn-block"
                onClick={() => inputRef.current?.click()} disabled={busy}>
          Choose folder
        </button>
      ) : (
        <>
          <div className="card-sub" style={{ marginBottom: "var(--s2)" }}>
            {files.length} supported file{files.length === 1 ? "" : "s"} selected
          </div>
          <div style={{ display: "flex", gap: "var(--s2)" }}>
            <button type="button" className="btn btn-ghost" onClick={() => setFiles([])} disabled={busy}>
              Clear
            </button>
            <button type="button" className="btn btn-primary" style={{ flex: 1 }} onClick={upload} disabled={busy}>
              {busy
                ? (progress ? `Uploading ${progress.done + 1}/${progress.total}...` : "Uploading...")
                : `Upload ${files.length} file${files.length === 1 ? "" : "s"}`}
            </button>
          </div>
        </>
      )}

      {error && <div style={{ marginTop: "var(--s3)" }}><ErrorBanner message={error} /></div>}
      {result && (
        <div className="notice-ok" style={{ marginTop: "var(--s3)" }}>
          Ingested {result.files_ingested} file{result.files_ingested === 1 ? "" : "s"} ({result.total_chunks} chunks).
          {result.files_failed > 0 ? ` ${result.files_failed} skipped.` : ""}
        </div>
      )}
      {result && result.failed && result.failed.length > 0 && (
        <ul className="foldl-fail">
          {result.failed.map((f, i) => <li key={i}>{f.file}: {f.error}</li>)}
        </ul>
      )}
    </div>
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
