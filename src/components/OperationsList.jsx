import { useState } from "react";
import { useAppContext } from "../context/AppContext";
import { UPLOAD_PHASES } from "../constants";
import { deleteOperation } from "../api/operations";

// ── Status badge helpers ──────────────────────────────────────────────────────
 
function deriveStatus(uploadState, protocolState) {
  const phase = uploadState?.phase ?? UPLOAD_PHASES.IDLE;
  if (phase === UPLOAD_PHASES.CREATING)   return { label: "Создание…",    color: "#3B82F6" };
  if (phase === UPLOAD_PHASES.UPLOADING)  return { label: `Загрузка ${Math.round(uploadState.progress ?? 0)}%`, color: "#3B82F6" };
  if (phase === UPLOAD_PHASES.PROCESSING) return { label: "Отправка…",    color: "#3B82F6" };
  if (phase === UPLOAD_PHASES.CANCELLING) return { label: "Отмена…",      color: "#F59E0B" };
  if (phase === UPLOAD_PHASES.ERROR)      return { label: "Ошибка",        color: "#EF4444" };
  if (phase === UPLOAD_PHASES.DONE) {
    const ps = protocolState?.status;
    if (ps === "polling")   return { label: "Обработка…",  color: "#F59E0B" };
    if (ps === "loading")   return { label: "Загрузка…",   color: "#F59E0B" };
    if (ps === "completed") return { label: "Готов",        color: "#10B981" };
    if (ps === "error")     return { label: "Ошибка",       color: "#EF4444" };
    return { label: "Запущено", color: "#10B981" };
  }
  return { label: "Ожидание", color: "#6B7280" };
}

function formatTime(date) {
  if (!date) return "";
  return new Date(date).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

// ── Delete button ─────────────────────────────────────────────────────────────
 
function DeleteButton({ onDelete, deleting }) {
  const [confirm, setConfirm] = useState(false);
 
  if (deleting) {
    return (
      <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", padding: "3px 6px" }}>
        …
      </span>
    );
  }
 
  if (confirm) {
    return (
      <div style={{ display: "flex", gap: 4 }} onClick={e => e.stopPropagation()}>
        <button
          onClick={() => { setConfirm(false); onDelete(); }}
          title="Подтвердить удаление"
          style={{
            padding: "2px 7px", fontSize: 10, fontWeight: 600,
            borderRadius: 5, border: "none", cursor: "pointer",
            background: "#EF4444", color: "#fff",
          }}
        >
          Да
        </button>
        <button
          onClick={() => setConfirm(false)}
          title="Отмена"
          style={{
            padding: "2px 6px", fontSize: 10,
            borderRadius: 5, border: "1px solid var(--color-border-secondary)",
            cursor: "pointer", background: "none", color: "var(--color-text-secondary)",
          }}
        >
          Нет
        </button>
      </div>
    );
  }
 
  return (
    <button
      onClick={e => { e.stopPropagation(); setConfirm(true); }}
      title="Удалить операцию"
      style={{
        background: "none", border: "none", cursor: "pointer",
        color: "var(--color-text-tertiary)", fontSize: 14,
        padding: "2px 5px", lineHeight: 1, borderRadius: 4,
        opacity: 0,  // покажем через CSS hover на родителе
      }}
      className="delete-btn"
    >
      ✕
    </button>
  );
}
 
// ── Main component ────────────────────────────────────────────────────────────
 
export function OperationsList({ onAddFile }) {
  const {
    apiBase,
    operations,
    activeOperationId, setActiveOperationId,
    operationUploads,
    operationProtocols,
    removeOperation,
  } = useAppContext();
 
  // Локальный словарь: { [opId]: true } — идёт запрос удаления
  const [deletingIds, setDeletingIds] = useState({});
 
  const handleDelete = async (op) => {
    setDeletingIds(prev => ({ ...prev, [op.id]: true }));
    try {
      await deleteOperation(apiBase, op.id, op.s3_key);
      removeOperation(op.id);
    } catch (err) {
      console.error("Ошибка удаления операции:", err);
      // Показываем ошибку и снимаем блокировку — пользователь может попробовать снова
      setDeletingIds(prev => { const s = { ...prev }; delete s[op.id]; return s; });
      alert(err.message); // можно заменить на toast-уведомление
    }
  };
 
  return (
    <>
      {/* Глобальный стиль: показываем кнопку удаления при наведении на карточку */}
      <style>{`
        .op-card:hover .delete-btn { opacity: 1 !important; }
        .op-card .delete-btn:hover { color: #EF4444 !important; background: #FEF2F2 !important; }
      `}</style>
 
      <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--color-background-primary)" }}>
 
        {/* Header */}
        <div style={{ padding: "14px 14px 10px", borderBottom: "1px solid var(--color-border-tertiary)", flexShrink: 0 }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: 0.8, textTransform: "uppercase",
            color: "var(--color-text-tertiary)", marginBottom: 10,
          }}>
            Операции
            {operations.length > 0 && (
              <span style={{
                marginLeft: 6, padding: "1px 6px", borderRadius: 99, fontSize: 9,
                background: "var(--color-border-tertiary)", color: "var(--color-text-secondary)",
              }}>
                {operations.length}
              </span>
            )}
          </div>
 
          {/* Add file button */}
          {/*<button
            onClick={onAddFile}
            style={{
              width: "100%", padding: "9px 12px", borderRadius: 8, border: "none",
              background: "#3B82F6", color: "#fff", fontWeight: 600, fontSize: 13,
              cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
              transition: "background 0.15s",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "#2563EB"}
            onMouseLeave={e => e.currentTarget.style.background = "#3B82F6"}
          >
            + Добавить файл
          </button>*/}
        </div>
 
        {/* List */}
        <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
          {operations.length === 0 && (
            <div style={{
              textAlign: "center", padding: "40px 16px",
              color: "var(--color-text-tertiary)", fontSize: 12, lineHeight: 1.6,
            }}>
              <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.4 }}>📂</div>
              Добавьте файл встречи,<br />чтобы начать работу
            </div>
          )}
 
          {[...operations].reverse().map(op => {
            const isActive  = op.id === activeOperationId;
            const isDeleting = !!deletingIds[op.id];
            const uploadState   = operationUploads[op.id]   ?? {};
            const protocolState = operationProtocols[op.id] ?? {};
            const st = deriveStatus(uploadState, protocolState);
 
            return (
              <div
                key={op.id}
                className="op-card"
                onClick={() => !isDeleting && setActiveOperationId(op.id)}
                style={{
                  padding: "10px 10px", borderRadius: 8, marginBottom: 4,
                  cursor: isDeleting ? "not-allowed" : "pointer",
                  transition: "background 0.12s",
                  background: isActive ? "#3B82F618" : "transparent",
                  border: `1.5px solid ${isActive ? "#3B82F6" : "transparent"}`,
                  opacity: isDeleting ? 0.5 : 1,
                  position: "relative",
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = "var(--color-background-secondary)"; }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
              >
                {/* Top row: filename + delete button */}
                <div style={{ display: "flex", alignItems: "flex-start", gap: 6, marginBottom: 5 }}>
                  <span style={{
                    fontSize: 12, fontWeight: 500, flex: 1,
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>
                    🎵 {op.filename}
                  </span>
                  <DeleteButton
                    onDelete={() => handleDelete(op)}
                    deleting={isDeleting}
                  />
                </div>
 
                {/* Status + time */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 99,
                    background: st.color + "22", color: st.color,
                  }}>
                    {st.label}
                  </span>
                  <span style={{ fontSize: 10, color: "var(--color-text-tertiary)" }}>
                    {formatTime(op.createdAt)}
                  </span>
                </div>
 
                {/* Upload progress bar */}
                {uploadState.phase === UPLOAD_PHASES.UPLOADING && (
                  <div style={{ height: 3, borderRadius: 2, background: "var(--color-border-tertiary)", overflow: "hidden", marginTop: 6 }}>
                    <div style={{
                      height: "100%", borderRadius: 2, background: "#3B82F6",
                      width: `${uploadState.progress ?? 0}%`, transition: "width 0.2s",
                    }} />
                  </div>
                )}
 
                {/* Operation ID */}
                {op.id && (
                  <div style={{ fontSize: 9, fontFamily: "monospace", color: "var(--color-text-tertiary)", marginTop: 4, opacity: 0.6 }}>
                    {op.id.slice(0, 16)}…
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}