// ─── Shared input style ───────────────────────────────────────────────────────
export const inputStyle = (extra = {}) => ({
  padding: "8px 11px", borderRadius: 7, outline: "none",
  border: "1px solid var(--color-border-secondary)",
  background: "var(--color-background-primary)",
  color: "var(--color-text-primary)", fontSize: 13,
  fontFamily: "inherit", width: "100%", boxSizing: "border-box",
  ...extra,
});

export const sectionLabel = {
  fontSize: 10, fontWeight: 600, letterSpacing: 0.8,
  textTransform: "uppercase", color: "var(--color-text-tertiary)", marginBottom: 10,
};