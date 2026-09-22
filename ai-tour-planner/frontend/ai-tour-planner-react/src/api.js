import { auth } from "./firebase";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const user = auth.currentUser;

  if (!user) {
    throw new Error("Please sign in with Google");
  }

  const token = await user.getIdToken();

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;

    try {
      const body = await response.json();
      detail = body.detail || body.message || detail;
    } catch {}

    throw new Error(detail);
  }

  return response.json();
}

export const api = {
  sessions: () => request("/sessions"),

  messages: (id) =>
    request(`/sessions/${encodeURIComponent(id)}/messages`),

  deleteSession: (id) =>
    request(`/sessions/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),

  chat: (session_id, message) =>
    request("/chat", {
      method: "POST",
      body: JSON.stringify({
        session_id,
        message,
      }),
    }),
};