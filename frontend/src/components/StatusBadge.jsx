const STATUS_CONFIG = {
  pending:    { label: "Queued",      color: "#f59e0b" },
  processing: { label: "Processing…", color: "#3b82f6" },
  completed:  { label: "Completed",   color: "#10b981" },
  failed:     { label: "Failed",      color: "#ef4444" },
};

export default function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "2px 10px",
        borderRadius: "999px",
        fontSize: "0.75rem",
        fontWeight: 600,
        color: cfg.color,
        background: `${cfg.color}20`,
        border: `1px solid ${cfg.color}50`,
      }}
    >
      {status === "processing" && (
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: cfg.color,
            animation: "pulse 1.2s infinite",
          }}
        />
      )}
      {cfg.label}
    </span>
  );
}
