// One place for all backend calls. Every request goes through request(),
// so error handling and the base URL live in a single spot.

const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

// The backend's origin (BASE without the trailing /api/v1), used to build absolute
// links to uploaded files (media) that the backend serves.
export const FILE_BASE = BASE.replace(/\/api\/v1\/?$/, "");

// Turn a source link into an absolute URL the browser can open.
// Already-absolute (cloud storage) links are returned as-is.
export function fileUrl(link) {
  if (!link) return "";
  if (/^https?:\/\//i.test(link)) return link;
  return FILE_BASE + link;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, options);
  } catch {
    // Network-level failure: server down, wrong port, no connection.
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }

  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  const body = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    // The backend returns { error: "..." } or DRF's { detail: "..." }.
    const message =
      (body && (body.error || body.detail)) || `Request failed (${res.status})`;
    throw new ApiError(message, res.status);
  }
  return body;
}

export const api = {
  getStats: () => request("/stats"),

  listCourses: () => request("/courses"),

  createCourse: (data) =>
    request("/courses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  deleteCourse: (courseId) =>
    request(`/courses/${courseId}`, { method: "DELETE" }),

  getStructure: (courseId) => request(`/courses/${courseId}/structure`),

  listMaterials: (courseId) => request(`/courses/${courseId}/materials`),

  getHistory: (courseId, limit = 20) =>
    request(`/courses/${courseId}/history?limit=${limit}`),

  getSuggestions: (courseId) => request(`/courses/${courseId}/suggestions`),

  getInsights: (courseId) => request(`/courses/${courseId}/insights`),

  // --- Structure editing (rename / add / move / delete) ---
  createUnit: (courseId, name) =>
    request(`/courses/${courseId}/units`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  renameUnit: (unitId, name) =>
    request(`/units/${unitId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  deleteUnit: (unitId) => request(`/units/${unitId}`, { method: "DELETE" }),

  createLesson: (unitId, name) =>
    request(`/units/${unitId}/lessons`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  updateLesson: (lessonId, data) =>
    request(`/lessons/${lessonId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteLesson: (lessonId) => request(`/lessons/${lessonId}`, { method: "DELETE" }),

  updateMaterial: (materialId, data) =>
    request(`/materials/${materialId}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteMaterial: (materialId) => request(`/materials/${materialId}`, { method: "DELETE" }),

  ask: (courseId, question, topK = 5, conversationId = null) =>
    request(`/courses/${courseId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: topK, conversation_id: conversationId }),
    }),

  // formData carries the file plus unit_name, lesson_name, material_type.
  // We do NOT set Content-Type; the browser adds the multipart boundary.
  ingest: (courseId, formData) =>
    request(`/courses/${courseId}/ingest`, { method: "POST", body: formData }),

  // Upload a whole folder: formData carries many "files" (+ optional "paths").
  ingestFolder: (courseId, formData) =>
    request(`/courses/${courseId}/ingest-folder`, { method: "POST", body: formData }),

  // Step 1 of auto-structure: upload a PDF, get back a proposed outline.
  analyze: (courseId, formData) =>
    request(`/courses/${courseId}/analyze`, { method: "POST", body: formData }),

  // Step 2 of auto-structure: confirm the (edited) outline and ingest.
  ingestStructured: (courseId, payload) =>
    request(`/courses/${courseId}/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
};
