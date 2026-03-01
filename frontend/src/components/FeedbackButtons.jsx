import { useState } from "react";
import { submitFeedback } from "../api/client";

export default function FeedbackButtons({ responseId, query, chunkIds }) {
  const [submitted, setSubmitted] = useState(null); // 1 | -1 | null
  const [loading, setLoading] = useState(false);

  async function handleFeedback(rating) {
    if (submitted !== null || loading) return;
    setLoading(true);
    try {
      await submitFeedback(responseId, rating, query, chunkIds);
      setSubmitted(rating);
    } catch (err) {
      console.error("Feedback error:", err);
    } finally {
      setLoading(false);
    }
  }

  const btnBase = {
    background: "none",
    border: "1px solid transparent",
    borderRadius: "6px",
    cursor: submitted !== null ? "default" : "pointer",
    fontSize: "1.1rem",
    padding: "3px 8px",
    transition: "all 0.15s",
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px" }}>
      <span style={{ fontSize: "0.72rem", color: "#6b7280" }}>
        {submitted === null ? "Was this helpful?" : submitted === 1 ? "Thanks for the feedback!" : "Sorry about that!"}
      </span>
      {submitted === null && (
        <>
          <button
            onClick={() => handleFeedback(1)}
            disabled={loading}
            style={{
              ...btnBase,
              color: "#10b981",
              borderColor: "#10b98140",
            }}
            title="Thumbs up"
          >
            👍
          </button>
          <button
            onClick={() => handleFeedback(-1)}
            disabled={loading}
            style={{
              ...btnBase,
              color: "#ef4444",
              borderColor: "#ef444440",
            }}
            title="Thumbs down"
          >
            👎
          </button>
        </>
      )}
      {submitted === 1 && <span style={{ fontSize: "1.1rem" }}>👍</span>}
      {submitted === -1 && <span style={{ fontSize: "1.1rem" }}>👎</span>}
    </div>
  );
}
