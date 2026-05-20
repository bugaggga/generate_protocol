import { useState } from "react";
import { EditBlockPanel } from "./EditBlockPanel";
import { inputStyle } from "./ui/styles";
import { BLOCK_TYPES } from "../constants";
import { useFormBuilderContext } from "../context/FormBuilderContext";

/**
 * FormPanel — панель конструктора формы протокола.
 * Только разметка + вызовы методов хука useFormBuilder.
 */
export function FormPanel({ operationId }) {
  const [addMenuOpen, setAddMenuOpen] = useState(false);

  const {
    blocks, formName, setFormName,
    selectedId, setSelectedId, selectedBlock,
    submitting, submitStatus, submitError,
    addBlock, deleteBlock, updateBlock, moveBlock, send,
  } = useFormBuilderContext();

  const handleAddBlock = (type) => {
    addBlock(type);
    setAddMenuOpen(false);
  };

  const submitBg =
    submitStatus === "ok"    ? "#10B981" :
    submitStatus === "error" ? "#EF4444" :
    submitting               ? "var(--color-border-secondary)" : "#6366F1";

  const submitLabel =
    submitStatus === "ok"    ? "✓ Форма отправлена" :
    submitStatus === "error" ? `✕ ${submitError}` :
    submitting               ? "Отправка…" : "Отправить форму";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 12 }}>

      {/* ── Form name ── */}
      <input
        value={formName}
        onChange={(e) => setFormName(e.target.value)}
        placeholder="Название шаблона протокола"
        style={inputStyle({ fontSize: 14, fontWeight: 500, padding: "10px 13px" })}
      />

      {/* ── Block list + edit panel ── */}
      <div style={{ display: "flex", gap: 12, flex: 1, minHeight: 0 }}>

        {/* Block list */}
        <div style={{ flex: 1, minWidth: 0, overflowY: "auto" }}>
          {blocks.map((block, i) => {
            const meta = BLOCK_TYPES.find((t) => t.type === block.type);
            const selected = selectedId === block.id;
            return (
              <div
                key={block.id}
                onClick={() => setSelectedId(block.id)}
                style={{
                  border: `1.5px solid ${selected ? "#6366F1" : "var(--color-border-tertiary)"}`,
                  borderRadius: 9, padding: "9px 11px", marginBottom: 7,
                  background: selected ? "#6366F108" : "var(--color-background-secondary)",
                  cursor: "pointer", display: "flex", alignItems: "center", gap: 9,
                  transition: "border-color 0.12s",
                }}>

                {/* Move arrows */}
                <div style={{ display: "flex", flexDirection: "column" }}>
                  {[[-1, "▲"], [1, "▼"]].map(([dir, sym]) => (
                    <button
                      key={dir}
                      onClick={(e) => { e.stopPropagation(); moveBlock(i, dir); }}
                      disabled={dir === -1 ? i === 0 : i === blocks.length - 1}
                      style={{
                        background: "none", border: "none", cursor: "pointer",
                        color: "var(--color-text-tertiary)", fontSize: 10,
                        padding: "0 2px", lineHeight: 1.3,
                      }}>
                      {sym}
                    </button>
                  ))}
                </div>

                <span style={{ fontSize: 12, color: "var(--color-text-tertiary)", minWidth: 16, textAlign: "center" }}>
                  {i + 1}
                </span>
                <span style={{ fontSize: 16, color: meta?.color }}>{meta?.icon}</span>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span style={{ fontSize: 13, fontWeight: 500 }}>{block.title}</span>
                    {block.required && (
                      <span style={{ fontSize: 9, color: "#EF4444", fontWeight: 700, letterSpacing: 0.3 }}>
                        ОБЯ
                      </span>
                    )}
                  </div>
                  <div style={{
                    fontSize: 11, color: "var(--color-text-tertiary)", marginTop: 2,
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>
                    {block.llm_instruction || "нет инструкции для LLM"}
                  </div>
                </div>

                <button
                  onClick={(e) => { e.stopPropagation(); deleteBlock(block.id); }}
                  style={{
                    background: "none", border: "none", cursor: "pointer",
                    color: "var(--color-text-tertiary)", fontSize: 14,
                    padding: "2px 5px", lineHeight: 1,
                  }}>
                  ✕
                </button>
              </div>
            );
          })}

          {/* Add block menu */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setAddMenuOpen((v) => !v)}
              style={{
                width: "100%", padding: 9, border: "1.5px dashed var(--color-border-secondary)",
                borderRadius: 9, background: "none", cursor: "pointer", fontSize: 12,
                color: "var(--color-text-secondary)", display: "flex",
                alignItems: "center", justifyContent: "center", gap: 5,
              }}>
              + Добавить блок
            </button>
            {addMenuOpen && (
              <div style={{
                position: "absolute", top: "calc(100% + 5px)", left: 0, zIndex: 30, width: "100%",
                background: "var(--color-background-primary)",
                border: "1px solid var(--color-border-secondary)",
                borderRadius: 9, padding: 5, boxShadow: "0 6px 20px #0003",
              }}>
                {BLOCK_TYPES.map((t) => (
                  <button
                    key={t.type}
                    onClick={() => handleAddBlock(t.type)}
                    style={{
                      display: "flex", alignItems: "center", gap: 10, width: "100%",
                      padding: "8px 11px", background: "none", border: "none",
                      cursor: "pointer", borderRadius: 7, textAlign: "left",
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = "var(--color-background-secondary)"}
                    onMouseLeave={(e) => e.currentTarget.style.background = "none"}>
                    <span style={{ color: t.color, fontSize: 17, width: 22 }}>{t.icon}</span>
                    <span style={{ fontSize: 13 }}>{t.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Edit panel */}
        {selectedBlock && (
          <div style={{
            width: 260, flexShrink: 0, padding: "12px 14px", overflowY: "auto",
            border: "1px solid var(--color-border-tertiary)", borderRadius: 10,
            background: "var(--color-background-secondary)",
          }}>
            <EditBlockPanel block={selectedBlock} onChange={updateBlock} />
          </div>
        )}
      </div>

      {/* ── Footer: stats + submit ── */}
      <div style={{
        borderTop: "1px solid var(--color-border-tertiary)", paddingTop: 12,
        display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
      }}>
        <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", flex: 1 }}>
          {blocks.length} блоков
          {operationId && (
            <span>
              {" "}· операция{" "}
              <span style={{ fontFamily: "monospace" }}>{operationId.slice(0, 8)}…</span>
            </span>
          )}
        </span>
        <button
          onClick={() => send(operationId)}
          disabled={submitting || submitStatus === "ok"}
          style={{
            padding: "9px 20px", borderRadius: 8, border: "none", whiteSpace: "nowrap",
            cursor: submitting || submitStatus === "ok" ? "not-allowed" : "pointer",
            background: submitBg,
            color: submitting ? "var(--color-text-tertiary)" : "#fff",
            fontWeight: 600, fontSize: 13, transition: "all 0.15s",
          }}>
          {submitLabel}
        </button>
      </div>
    </div>
  );
}
