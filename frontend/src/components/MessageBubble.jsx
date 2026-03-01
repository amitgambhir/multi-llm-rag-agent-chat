import ReactMarkdown from "react-markdown";
import FeedbackButtons from "./FeedbackButtons";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        marginBottom: "16px",
      }}
    >
      {/* Role label */}
      <span
        style={{
          fontSize: "0.72rem",
          color: "#6b7280",
          marginBottom: "4px",
          paddingLeft: isUser ? 0 : "4px",
          paddingRight: isUser ? "4px" : 0,
        }}
      >
        {isUser ? "You" : `Assistant · via ${message.llmUsed ?? "LLM"}`}
      </span>

      {/* Bubble */}
      <div
        style={{
          maxWidth: "80%",
          padding: "12px 16px",
          borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
          background: isUser ? "#3b82f6" : "#1e293b",
          color: "#f1f5f9",
          fontSize: "0.92rem",
          lineHeight: 1.6,
          boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
        }}
      >
        {isUser ? (
          <span>{message.content}</span>
        ) : (
          <ReactMarkdown
            components={{
              p: ({ children }) => <p style={{ margin: "0 0 8px" }}>{children}</p>,
              code: ({ children }) => (
                <code
                  style={{
                    background: "#0f172a",
                    borderRadius: "4px",
                    padding: "1px 5px",
                    fontSize: "0.85em",
                    fontFamily: "monospace",
                  }}
                >
                  {children}
                </code>
              ),
              pre: ({ children }) => (
                <pre
                  style={{
                    background: "#0f172a",
                    borderRadius: "8px",
                    padding: "12px",
                    overflowX: "auto",
                    fontSize: "0.85em",
                    margin: "8px 0",
                  }}
                >
                  {children}
                </pre>
              ),
            }}
          >
            {message.content}
          </ReactMarkdown>
        )}
      </div>

      {/* Sources (AI only) */}
      {!isUser && message.sources && message.sources.length > 0 && (
        <details
          style={{
            maxWidth: "80%",
            marginTop: "4px",
            fontSize: "0.75rem",
            color: "#94a3b8",
            cursor: "pointer",
          }}
        >
          <summary style={{ paddingLeft: "4px" }}>
            {message.sources.length} source{message.sources.length > 1 ? "s" : ""}
            {message.complexityScore !== undefined && (
              <span style={{ marginLeft: "8px", color: "#64748b" }}>
                · complexity {(message.complexityScore * 100).toFixed(0)}%
              </span>
            )}
          </summary>
          <div style={{ paddingLeft: "4px", marginTop: "4px" }}>
            {message.sources.map((src, i) => (
              <div
                key={i}
                style={{
                  background: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "6px",
                  padding: "6px 10px",
                  marginBottom: "4px",
                }}
              >
                <div style={{ color: "#60a5fa", marginBottom: "2px" }}>
                  {src.source} — score {src.score}
                </div>
                <div style={{ color: "#94a3b8" }}>{src.content}</div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* RLHF feedback (AI only) */}
      {!isUser && message.responseId && (
        <div style={{ paddingLeft: "4px" }}>
          <FeedbackButtons
            responseId={message.responseId}
            query={message.query}
            chunkIds={message.chunkIds ?? []}
          />
        </div>
      )}
    </div>
  );
}
