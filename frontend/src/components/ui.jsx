// Small shared UI pieces used across pages: loading, empty, error, badges,
// and the confidence meter. Keeping them here keeps the pages readable.

export function Spinner() {
  return <span className="spinner" role="status" aria-label="Loading" />;
}

export function Loading({ label = "Loading..." }) {
  return (
    <div className="center-state">
      <Spinner />
      <p>{label}</p>
    </div>
  );
}

export function EmptyState({ icon = "•", title, message, action, compact = false }) {
  return (
    <div className={`center-state${compact ? " compact" : ""}`}>
      <div className="icon" aria-hidden="true">{icon}</div>
      <h3>{title}</h3>
      {message && <p>{message}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="center-state">
      <div className="icon" aria-hidden="true" style={{ background: "var(--danger-soft)", color: "var(--danger)" }}>!</div>
      <h3>Something went wrong</h3>
      <p>{message}</p>
      {onRetry && (
        <button className="btn btn-ghost btn-sm" onClick={onRetry}>Try again</button>
      )}
    </div>
  );
}

export function ErrorBanner({ message }) {
  return <div className="error-banner" role="alert">{message}</div>;
}

export function Badge({ children, tone = "muted" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

// Confidence as a coloured bar. Green when strong, amber mid, red when weak.
export function ConfidenceMeter({ value }) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0)) * 100;
  const color = pct >= 70 ? "var(--ok)" : pct >= 45 ? "var(--warn)" : "var(--danger)";
  return (
    <div className="meter" title="How strongly the answer matches the materials">
      <div className="meter-track">
        <div className="meter-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="meter-val" style={{ color }}>{Math.round(pct)}%</span>
    </div>
  );
}

export function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric", month: "short", day: "numeric",
    });
  } catch {
    return "";
  }
}

// Nice label for a material type value.
export function materialTypeLabel(type) {
  return { pdf: "PDF", syllabus: "Syllabus", note: "Note" }[type] || type;
}

// The actual file format (PDF / DOCX / PPTX) for the "Type" badge/column.
export function fileTypeLabel(fileType) {
  return (fileType || "").toUpperCase() || "FILE";
}

// Human-readable file size.
export function formatBytes(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// A single KPI tile for dashboards.
export function Kpi({ label, value }) {
  return (
    <div className="kpi">
      <div className="kpi-val">{value ?? "—"}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}
