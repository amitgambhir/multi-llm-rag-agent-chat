import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000, // 2 min — LLM calls can be slow
});

// ── Ingestion ──────────────────────────────────────────────────────────────

export async function ingestDocument(file, onUploadProgress) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/ingest/document", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress,
  });
  return data; // { job_id, status, message }
}

export async function ingestURL(url) {
  const { data } = await api.post("/ingest/url", { url });
  return data; // { job_id, status, message }
}

export async function getJobStatus(jobId) {
  const { data } = await api.get(`/ingest/status/${jobId}`);
  return data; // { job_id, status, message, chunks_created, source, error }
}

// ── Chat ───────────────────────────────────────────────────────────────────

export async function sendMessage(query, sessionId) {
  const { data } = await api.post("/chat", { query, session_id: sessionId });
  return data; // ChatResponse
}

export async function clearHistory(sessionId) {
  const { data } = await api.post("/chat/clear", { session_id: sessionId });
  return data;
}

// ── Feedback ───────────────────────────────────────────────────────────────

export async function submitFeedback(responseId, rating, query, chunkIds) {
  const { data } = await api.post("/feedback", {
    response_id: responseId,
    rating,
    query,
    chunk_ids: chunkIds,
  });
  return data;
}
