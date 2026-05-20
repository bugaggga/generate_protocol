import { useRef, useEffect } from "react";

// ─── Step row ─────────────────────────────────────────────────────────────────
const STEP_STYLES = {
  done:    { bg: "#10B981", border: "#10B981", fg: "#fff", labelColor: "var(--color-text-primary)" },
  loading: { bg: "#3B82F6", border: "#3B82F6", fg: "#fff", labelColor: "var(--color-text-primary)" },
  error:   { bg: "#EF4444", border: "#EF4444", fg: "#fff", labelColor: "#EF4444" },
  idle:    { bg: "transparent", border: "var(--color-border-secondary)", fg: "var(--color-text-tertiary)", labelColor: "var(--color-text-tertiary)" },
};

export function StepRow({ index, label, sub, status }) {
  const c = STEP_STYLES[status] ?? STEP_STYLES.idle;
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
      <div style={{
        width: 28, height: 28, borderRadius: "50%", flexShrink: 0, marginTop: 1,
        border: `2px solid ${c.border}`, background: c.bg, color: c.fg,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700, transition: "all 0.25s",
      }}>
        {status === "done" ? "✓" : status === "error" ? "✕" : status === "loading" ? "…" : index + 1}
      </div>
      <div style={{ paddingTop: 2 }}>
        <div style={{ fontSize: 13, fontWeight: status === "loading" ? 500 : 400, color: c.labelColor }}>
          {label}
        </div>
        {sub && (
          <div style={{ fontSize: 11, color: "var(--color-text-tertiary)", marginTop: 2, fontFamily: "monospace" }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Progress bar ─────────────────────────────────────────────────────────────
export function ProgressBar({ value }) {
  return (
    <div>
      <div style={{ height: 5, borderRadius: 3, background: "var(--color-border-tertiary)", overflow: "hidden" }}>
        <div style={{
          height: "100%", borderRadius: 3, background: "#3B82F6",
          width: `${value}%`, transition: "width 0.2s",
        }} />
      </div>
      <div style={{ fontSize: 11, color: "var(--color-text-tertiary)", textAlign: "right", marginTop: 4 }}>
        {value}% загружено
      </div>
    </div>
  );
}

// ─── Log console ──────────────────────────────────────────────────────────────
const LOG_COLORS = {
  info:    "#94a3b8",
  success: "#4ade80",
  warn:    "#fbbf24",
  error:   "#f87171",
};

export function LogConsole({ logs }) {
  const ref = useRef();
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  if (!logs.length) return null;

  return (
    <div ref={ref} style={{
      background: "#0d1117", borderRadius: 8, padding: "10px 12px",
      border: "1px solid #2a2e45", maxHeight: 150, overflowY: "auto",
    }}>
      {logs.map((l, i) => (
        <div key={i} style={{
          fontSize: 11, lineHeight: 1.6, fontFamily: "monospace",
          color: LOG_COLORS[l.type] ?? LOG_COLORS.info,
        }}>
          <span style={{ opacity: 0.4, marginRight: 8 }}>{l.time}</span>
          {l.msg}
        </div>
      ))}
    </div>
  );
}


