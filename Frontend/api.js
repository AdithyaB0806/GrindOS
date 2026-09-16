// api.js — thin client for the GrindOS FastAPI backend.
// Set VITE_API_URL in a .env file at your project root to point at your
// deployed backend. Defaults to a local dev server.

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body, token, query } = {}) {
  let url = `${API_BASE_URL}${path}`;
  if (query) {
    const qs = new URLSearchParams(query).toString();
    if (qs) url += `?${qs}`;
  }

  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new ApiError(
      "Couldn't reach the GrindOS server. Is the backend running?",
      0,
      null
    );
  }

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    const detail =
      (payload && (payload.detail || payload.message)) || res.statusText;
    throw new ApiError(detail, res.status, payload);
  }

  return payload;
}

async function requestBlob(path, token) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const payload = await res.json();
      detail = payload.detail || payload.message || detail;
    } catch {
      /* not json */
    }
    throw new ApiError(detail, res.status, null);
  }
  const disposition = res.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "resume.docx";
  const blob = await res.blob();
  return { blob, filename };
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  register: ({ name, email, password }) =>
    request("/register", { method: "POST", body: { name, email, password } }),

  login: ({ email, password }) =>
    request("/login", { method: "POST", body: { email, password } }),

  me: (token) => request("/users/me", { token }),

  getQuestions: () => request("/assessment/questions"),

  // All routes below authenticate via the Bearer token (get_current_user on
  // the backend) — there's no user_id param, the JWT carries the identity.

  submitAssessment: ({ answers, token }) =>
    request("/assessment/submit", {
      method: "POST",
      token,
      body: { answers },
    }),

  generateRecommendation: (token) =>
    request("/recommendations/generate", { method: "POST", token }),

  regenerateRecommendation: ({ token, feedback }) =>
    request("/recommendations/generate", {
      method: "POST",
      token,
      query: {
        regenerate: "true",
        ...(feedback ? { feedback } : {}),
      },
    }),

  getRecommendation: (token) => request("/recommendations/", { token }),

  // ---- Roadmap ----

  generateRoadmap: ({ token, careerTitle, regenerate = false } = {}) =>
    request("/roadmap/generate", {
      method: "POST",
      token,
      query: {
        ...(careerTitle ? { career_title: careerTitle } : {}),
        ...(regenerate ? { regenerate: "true" } : {}),
      },
    }),

  getRoadmap: (token) => request("/roadmap/", { token }),

  updateRoadmapItemStatus: ({ token, itemId, status }) =>
    request(`/roadmap/items/${itemId}/status`, {
      method: "PATCH",
      token,
      body: { status },
    }),

  // ---- Skills ----

  listSkills: (token) => request("/skills/", { token }),

  getSkillsDashboard: (token) => request("/skills/dashboard", { token }),

  addSkill: ({ token, name }) =>
    request("/skills/", { method: "POST", token, body: { name } }),

  updateSkillStatus: ({ token, skillId, status }) =>
    request(`/skills/${skillId}/status`, {
      method: "PATCH",
      token,
      body: { status },
    }),

  deleteSkill: ({ token, skillId }) =>
    request(`/skills/${skillId}`, { method: "DELETE", token }),

  getRoadmapItemGuide: ({ token, itemId }) =>
    request(`/roadmap/items/${itemId}/guide`, { token }),

  getRoadmapItemChat: ({ token, itemId }) =>
    request(`/roadmap/items/${itemId}/chat`, { token }),

  askRoadmapItemDoubt: ({ token, itemId, question }) =>
    request(`/roadmap/items/${itemId}/ask`, {
      method: "POST",
      token,
      body: { question },
    }),

  getDashboardSummary: (token) => request("/dashboard/summary", { token }),

  listJobs: (token) => request("/jobs/", { token }),

  getJobsDashboard: (token) => request("/jobs/dashboard", { token }),

  createJob: ({ token, ...body }) =>
    request("/jobs/", { method: "POST", token, body }),

  updateJob: ({ token, jobId, ...body }) =>
    request(`/jobs/${jobId}`, { method: "PATCH", token, body }),

  deleteJob: ({ token, jobId }) =>
    request(`/jobs/${jobId}`, { method: "DELETE", token }),

  getInterview: (token) => request("/interview/", { token }),

  generateInterview: ({ token, regenerate = false } = {}) =>
    request("/interview/generate", {
      method: "POST",
      token,
      query: regenerate ? { regenerate: "true" } : {},
    }),

  updateInterviewStatus: ({ token, questionId, status }) =>
    request(`/interview/questions/${questionId}/status`, {
      method: "PATCH",
      token,
      body: { status },
    }),

  // ---- Resume studio ----

  getResume: (token) => request("/resume/", { token }),

  buildResume: ({ token, data }) =>
    request("/resume/build", { method: "POST", token, body: data }),

  downloadBuiltResume: async (token) => {
    const { blob, filename } = await requestBlob("/resume/build/download", token);
    triggerDownload(blob, filename);
  },

  uploadResume: async ({ token, file }) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE_URL}/resume/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    const isJson = res.headers.get("content-type")?.includes("application/json");
    const payload = isJson ? await res.json().catch(() => null) : null;
    if (!res.ok) {
      const detail = (payload && (payload.detail || payload.message)) || res.statusText;
      throw new ApiError(detail, res.status, payload);
    }
    return payload;
  },

  tailorResume: ({ token, jdText }) =>
    request("/resume/tailor", { method: "POST", token, body: { jd_text: jdText } }),

  downloadTailoredResume: async (token) => {
    const { blob, filename } = await requestBlob("/resume/tailor/download", token);
    triggerDownload(blob, filename);
  },

  checkAts: ({ token, jdText }) =>
    request("/resume/ats-check", { method: "POST", token, body: { jd_text: jdText || null } }),

  generateCoverLetter: ({ token, jdText, company, role }) =>
    request("/resume/cover-letter", {
      method: "POST",
      token,
      body: { jd_text: jdText, company: company || null, role: role || null },
    }),

  getCoverLetter: (token) => request("/resume/cover-letter", { token }),

  // ---- Mock interview ----

  getMockInterview: (token) => request("/mock-interview/", { token }),

  generateMockInterview: ({ token, regenerate = false } = {}) =>
    request("/mock-interview/generate", {
      method: "POST",
      token,
      query: regenerate ? { regenerate: "true" } : {},
    }),

  answerMockQuestion: ({ token, questionId, answer }) =>
    request(`/mock-interview/questions/${questionId}/answer`, {
      method: "POST",
      token,
      body: { answer },
    }),
};

export { API_BASE_URL };