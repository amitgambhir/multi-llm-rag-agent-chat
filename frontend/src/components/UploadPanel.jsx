import { useState, useCallback, useRef } from "react";
import { useDropzone } from "react-dropzone";
import StatusBadge from "./StatusBadge";
import { ingestDocument, ingestURL, getJobStatus } from "../api/client";

const POLL_INTERVAL_MS = 2000;
const ACCEPTED_TYPES = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/msword": [".doc"],
};

function JobCard({ job }) {
  return (
    <div
      style={{
        background: "#0f172a",
        border: "1px solid #1e293b",
        borderRadius: "8px",
        padding: "10px 12px",
        marginBottom: "8px",
        fontSize: "0.78rem",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "4px",
        }}
      >
        <span
          style={{
            color: "#94a3b8",
            maxWidth: "160px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={job.source}
        >
          {job.source}
        </span>
        <StatusBadge status={job.status} />
      </div>
      <div style={{ color: "#64748b" }}>{job.message}</div>
      {job.chunks_created != null && (
        <div style={{ color: "#10b981", marginTop: "2px" }}>
          {job.chunks_created} chunks stored
        </div>
      )}
      {job.error && (
        <div style={{ color: "#ef4444", marginTop: "2px" }}>{job.error}</div>
      )}
    </div>
  );
}

export default function UploadPanel() {
  const [jobs, setJobs] = useState([]);
  const [url, setUrl] = useState("");
  const [urlLoading, setUrlLoading] = useState(false);
  const [urlError, setUrlError] = useState("");
  const pollTimers = useRef({});

  function startPolling(jobId) {
    const timer = setInterval(async () => {
      try {
        const status = await getJobStatus(jobId);
        setJobs((prev) =>
          prev.map((j) => (j.job_id === jobId ? { ...j, ...status } : j))
        );
        if (status.status === "completed" || status.status === "failed") {
          clearInterval(pollTimers.current[jobId]);
          delete pollTimers.current[jobId];
        }
      } catch {
        clearInterval(pollTimers.current[jobId]);
        delete pollTimers.current[jobId];
      }
    }, POLL_INTERVAL_MS);
    pollTimers.current[jobId] = timer;
  }

  const onDrop = useCallback(async (acceptedFiles) => {
    for (const file of acceptedFiles) {
      const placeholder = {
        job_id: `local-${Date.now()}-${file.name}`,
        status: "pending",
        message: "Uploading…",
        source: file.name,
        chunks_created: null,
        error: null,
      };
      setJobs((prev) => [placeholder, ...prev]);

      try {
        const resp = await ingestDocument(file, (e) => {
          const pct = Math.round((e.loaded / e.total) * 100);
          setJobs((prev) =>
            prev.map((j) =>
              j.job_id === placeholder.job_id
                ? { ...j, message: `Uploading… ${pct}%` }
                : j
            )
          );
        });

        // Replace placeholder with real job data
        setJobs((prev) =>
          prev.map((j) =>
            j.job_id === placeholder.job_id
              ? { ...j, ...resp, source: file.name }
              : j
          )
        );
        startPolling(resp.job_id);
      } catch (err) {
        setJobs((prev) =>
          prev.map((j) =>
            j.job_id === placeholder.job_id
              ? {
                  ...j,
                  status: "failed",
                  message: "Upload failed.",
                  error: err.response?.data?.detail ?? err.message,
                }
              : j
          )
        );
      }
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    multiple: true,
  });

  async function handleURLIngest() {
    const trimmed = url.trim();
    if (!trimmed) return;
    setUrlError("");
    setUrlLoading(true);

    const placeholder = {
      job_id: `url-${Date.now()}`,
      status: "pending",
      message: "Submitting URL…",
      source: trimmed,
      chunks_created: null,
      error: null,
    };
    setJobs((prev) => [placeholder, ...prev]);

    try {
      const resp = await ingestURL(trimmed);
      setJobs((prev) =>
        prev.map((j) =>
          j.job_id === placeholder.job_id ? { ...j, ...resp, source: trimmed } : j
        )
      );
      startPolling(resp.job_id);
      setUrl("");
    } catch (err) {
      const msg = err.response?.data?.detail ?? err.message;
      setUrlError(msg);
      setJobs((prev) =>
        prev.map((j) =>
          j.job_id === placeholder.job_id
            ? { ...j, status: "failed", message: "URL ingest failed.", error: msg }
            : j
        )
      );
    } finally {
      setUrlLoading(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        padding: "20px",
        gap: "16px",
        overflowY: "auto",
      }}
    >
      <h2 style={{ margin: 0, color: "#f1f5f9", fontSize: "1rem" }}>
        Knowledge Base
      </h2>

      {/* Drag-and-drop zone */}
      <div
        {...getRootProps()}
        style={{
          border: `2px dashed ${isDragActive ? "#3b82f6" : "#334155"}`,
          borderRadius: "12px",
          padding: "24px 16px",
          textAlign: "center",
          cursor: "pointer",
          background: isDragActive ? "#1e3a5f30" : "#0f172a",
          transition: "all 0.2s",
          color: isDragActive ? "#60a5fa" : "#64748b",
          fontSize: "0.85rem",
        }}
      >
        <input {...getInputProps()} />
        <div style={{ fontSize: "2rem", marginBottom: "8px" }}>📄</div>
        {isDragActive ? (
          <p style={{ margin: 0 }}>Drop files here…</p>
        ) : (
          <>
            <p style={{ margin: "0 0 4px" }}>
              Drag & drop PDF or Word files here
            </p>
            <p style={{ margin: 0, fontSize: "0.75rem" }}>
              or click to browse
            </p>
          </>
        )}
      </div>

      {/* URL input */}
      <div>
        <label
          style={{
            display: "block",
            color: "#94a3b8",
            fontSize: "0.78rem",
            marginBottom: "6px",
          }}
        >
          OR ingest a webpage URL
        </label>
        <div style={{ display: "flex", gap: "8px" }}>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleURLIngest()}
            placeholder="https://example.com/page"
            style={{
              flex: 1,
              background: "#0f172a",
              border: "1px solid #334155",
              borderRadius: "8px",
              color: "#f1f5f9",
              fontSize: "0.82rem",
              padding: "8px 10px",
              outline: "none",
            }}
          />
          <button
            onClick={handleURLIngest}
            disabled={urlLoading || !url.trim()}
            style={{
              background: urlLoading || !url.trim() ? "#1e293b" : "#3b82f6",
              border: "none",
              borderRadius: "8px",
              color: urlLoading || !url.trim() ? "#475569" : "#fff",
              cursor: urlLoading || !url.trim() ? "not-allowed" : "pointer",
              fontSize: "0.82rem",
              padding: "0 14px",
              fontWeight: 600,
              transition: "all 0.15s",
            }}
          >
            {urlLoading ? "…" : "Add"}
          </button>
        </div>
        {urlError && (
          <p style={{ color: "#ef4444", fontSize: "0.75rem", margin: "4px 0 0" }}>
            {urlError}
          </p>
        )}
      </div>

      {/* Job list */}
      {jobs.length > 0 && (
        <div>
          <h3
            style={{
              margin: "0 0 8px",
              color: "#64748b",
              fontSize: "0.75rem",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Ingestion Jobs
          </h3>
          {jobs.map((job) => (
            <JobCard key={job.job_id} job={job} />
          ))}
        </div>
      )}
    </div>
  );
}
