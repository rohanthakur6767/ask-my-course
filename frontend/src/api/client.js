// One place for all backend calls. Every request goes through request(),
// so error handling and the base URL live in a single spot.

const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

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

  getStructure: (courseId) => request(`/courses/${courseId}/structure`),

  listMaterials: (courseId) => request(`/courses/${courseId}/materials`),

  getHistory: (courseId, limit = 20) =>
    request(`/courses/${courseId}/history?limit=${limit}`),

  ask: (courseId, question, topK = 5) =>
    request(`/courses/${courseId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: topK }),
    }),

  // formData carries the file plus unit_name, lesson_name, material_type.
  // We do NOT set Content-Type; the browser adds the multipart boundary.
  ingest: (courseId, formData) =>
    request(`/courses/${courseId}/ingest`, { method: "POST", body: formData }),
};
