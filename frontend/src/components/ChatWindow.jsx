import { useState, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import MessageBubble from "./MessageBubble";
import { sendMessage, clearHistory } from "../api/client";

const SESSION_KEY = "rag_session_id";

function getOrCreateSessionId() {
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = uuidv4();
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export default function ChatWindow() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(getOrCreateSessionId);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    const query = input.trim();
    if (!query || loading) return;

    const userMsg = { role: "user", content: query };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const data = await sendMessage(query, sessionId);
      const assistantMsg = {
        role: "assistant",
        content: data.answer,
        responseId: data.response_id,
        llmUsed: data.llm_used,
        complexityScore: data.complexity_score,
        sources: data.sources,
        chunkIds: data.chunk_ids,
        query,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errMsg = {
        role: "assistant",
        content: `Error: ${err.response?.data?.detail ?? err.message ?? "Something went wrong."}`,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  async function handleClear() {
    if (loading) return;
    try {
      await clearHistory(sessionId);
    } catch (_) {
      // Best-effort
    }
    setMessages([]);
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#0f172a",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "14px 20px",
          borderBottom: "1px solid #1e293b",
          background: "#0f172a",
        }}
      >
        <div>
          <h2 style={{ margin: 0, color: "#f1f5f9", fontSize: "1rem" }}>
            Chat
          </h2>
          <p style={{ margin: 0, color: "#64748b", fontSize: "0.75rem" }}>
            Session: {sessionId.slice(0, 8)}…
          </p>
        </div>
        <button
          onClick={handleClear}
          disabled={loading || messages.length === 0}
          style={{
            background: "none",
            border: "1px solid #334155",
            borderRadius: "8px",
            color: messages.length === 0 ? "#334155" : "#94a3b8",
            cursor: messages.length === 0 ? "not-allowed" : "pointer",
            fontSize: "0.8rem",
            padding: "6px 12px",
            transition: "all 0.15s",
          }}
        >
          Clear History
        </button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {messages.length === 0 && !loading && (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              color: "#475569",
              textAlign: "center",
              gap: "8px",
            }}
          >
            <span style={{ fontSize: "2.5rem" }}>🤖</span>
            <p style={{ margin: 0, fontSize: "1rem" }}>
              Upload content in the sidebar, then ask a question.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {loading && (
          <div style={{ display: "flex", alignItems: "flex-start", marginBottom: "16px" }}>
            <div
              style={{
                background: "#1e293b",
                borderRadius: "18px 18px 18px 4px",
                padding: "12px 16px",
                color: "#94a3b8",
                fontSize: "0.92rem",
              }}
            >
              <span className="typing-dots">Thinking</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        style={{
          padding: "16px 20px",
          borderTop: "1px solid #1e293b",
          background: "#0f172a",
          display: "flex",
          gap: "10px",
        }}
      >
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          disabled={loading}
          rows={1}
          style={{
            flex: 1,
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "12px",
            color: "#f1f5f9",
            fontSize: "0.92rem",
            padding: "10px 14px",
            resize: "none",
            outline: "none",
            fontFamily: "inherit",
            lineHeight: 1.5,
            maxHeight: "120px",
            overflowY: "auto",
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          style={{
            background: loading || !input.trim() ? "#1e293b" : "#3b82f6",
            border: "none",
            borderRadius: "12px",
            color: loading || !input.trim() ? "#475569" : "#fff",
            cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            fontSize: "1.2rem",
            padding: "0 18px",
            transition: "all 0.15s",
            minWidth: "52px",
          }}
        >
          ➤
        </button>
      </div>
    </div>
  );
}
