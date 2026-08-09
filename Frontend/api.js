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
    url += `?${qs}`;
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

export const api = {
  register: ({ name, email, password }) =>
    request("/register", { method: "POST", body: { name, email, password } }),

  login: ({ email, password }) =>
    request("/login", { method: "POST", body: { email, password } }),

  me: (token) => request("/users/me", { token }),

  getQuestions: () => request("/assessment/questions"),

  submitAssessment: ({ userId, answers, token }) =>
    request("/assessment/submit", {
      method: "POST",
      query: { user_id: userId },
      token,
      body: { answers },
    }),
};

export { API_BASE_URL };
