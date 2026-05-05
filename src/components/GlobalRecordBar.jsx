import { useState } from "react";
import { useAppContext } from "../context/AppContext";
import { createOperation } from "../api/operations";
import { useRecording, REC_STATES } from "../hooks/useRecording";
 
function formatDuration(seconds) {
  const m = String(Math.floor(seconds / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}
 
/**
 * Компонент записи аудио с микрофона.
 * Встраивается в сайдбар рядом с GlobalUploadBar.
 *
 * Поток:
 *   1. start()         — запрашиваем getUserMedia, стартуем MediaRecorder
 *   2. stop()          — финализируем Blob → File
 *   3. createOperation — регистрируем на сервере, получаем operation_id + presigned URL
 *   4. addOperation    — добавляем в контекст (дальше работает стандартный UploadPanel)
 */
export function GlobalRecordBar() {
  const { apiBase, addOperation } = useAppContext();
  const { recState, duration, error, start, stop, cancel } = useRecording();
  const [creating, setCreating] = useState(false); // фаза после stop — регистрация операции
 
  const isRecording = recState === REC_STATES.RECORDING;
  const isStopping  = recState === REC_STATES.STOPPING;
  const isRequesting = recState === REC_STATES.REQUESTING;
  const isBusy = isRecording || isStopping || isRequesting || creating;
 
  const handleStartRecording = async () => {
    if (isBusy) return;
 
    let file;
    try {
      // start() возвращает промис, который резолвится в File после вызова stop()
      file = await start();
    } catch {
      // ошибка уже записана в error внутри хука
      return;
    }
 
    // Сюда попадаем после того как пользователь нажал «Стоп»
    setCreating(true);
    try {
      const { operation_id, s3Data } = await createOperation(apiBase, { filename: file.name });
      addOperation(file, operation_id, s3Data);
    } catch (err) {
      console.error("Ошибка создания операции после записи:", err);
      alert("Ошибка создания операции: " + err.message);
    } finally {
      setCreating(false);
    }
  };
 
  // ── Вычисляем текущий лейбл состояния ─────────────────────────────────────
  const statusLabel = creating      ? "Создание операции…"
                    : isStopping    ? "Завершаем запись…"
                    : isRecording   ? formatDuration(duration)
                    : isRequesting  ? "Запрашиваем микрофон…"
                    : null;
 
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
 
      {/* ── Основная карточка ────────────────────────────────────────────── */}
      <div
        style={{
          border: `2px solid ${isRecording ? "#EF4444" : "var(--color-border-secondary)"}`,
          borderRadius: 12,
          padding: "16px",
          background: isRecording
            ? "rgba(239,68,68,0.05)"
            : "var(--color-background-secondary)",
          transition: "border-color 0.2s, background 0.2s",
        }}
      >
        {/* Заголовок + пульсирующий индикатор */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          {isRecording && (
            <span
              style={{
                width: 8, height: 8, borderRadius: "50%",
                background: "#EF4444", flexShrink: 0,
                animation: "rec-pulse 1.2s ease-in-out infinite",
              }}
            />
          )}
          <span style={{ fontSize: 13, fontWeight: 500 }}>
            {isRecording ? "Запись идёт" : "Запись встречи"}
          </span>
          {statusLabel && (
            <span style={{
              marginLeft: "auto",
              fontSize: 12,
              fontFamily: isRecording ? "monospace" : "inherit",
              color: isRecording ? "#EF4444" : "var(--color-text-tertiary)",
              fontWeight: isRecording ? 600 : 400,
            }}>
              {statusLabel}
            </span>
          )}
        </div>
 
        {/* Кнопки */}
        <div style={{ display: "flex", gap: 8 }}>
          {!isRecording ? (
            // ── Кнопка «Начать запись» ──
            <button
              onClick={handleStartRecording}
              disabled={isBusy}
              style={{
                flex: 1, padding: "9px 12px", borderRadius: 8, border: "none",
                cursor: isBusy ? "not-allowed" : "pointer",
                background: isBusy ? "var(--color-border-secondary)" : "#EF4444",
                color: isBusy ? "var(--color-text-tertiary)" : "#fff",
                fontWeight: 600, fontSize: 12,
                display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                transition: "all 0.15s",
              }}
            >
              <span style={{ fontSize: 10 }}>●</span>
              {isRequesting ? "Ожидание…" : creating ? "Создание…" : "Начать запись"}
            </button>
          ) : (
            <>
              {/* ── Кнопка «Стоп» ── */}
              <button
                onClick={stop}
                disabled={isStopping}
                style={{
                  flex: 1, padding: "9px 12px", borderRadius: 8, border: "none",
                  cursor: isStopping ? "not-allowed" : "pointer",
                  background: isStopping ? "var(--color-border-secondary)" : "#1e293b",
                  color: isStopping ? "var(--color-text-tertiary)" : "#fff",
                  fontWeight: 600, fontSize: 12,
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                  transition: "all 0.15s",
                }}
              >
                <span style={{ fontSize: 10 }}>■</span>
                Остановить
              </button>
 
              {/* ── Кнопка «Отмена» ── */}
              <button
                onClick={cancel}
                title="Отменить запись без сохранения"
                style={{
                  padding: "9px 12px", borderRadius: 8, border: "none",
                  cursor: "pointer",
                  background: "transparent",
                  color: "var(--color-text-tertiary)",
                  fontWeight: 500, fontSize: 12,
                  transition: "all 0.15s",
                }}
                onMouseEnter={(e) => e.currentTarget.style.color = "#EF4444"}
                onMouseLeave={(e) => e.currentTarget.style.color = "var(--color-text-tertiary)"}
              >
                Отмена
              </button>
            </>
          )}
        </div>
      </div>
 
      {/* ── Ошибка (если есть) ──────────────────────────────────────────── */}
      {error && (
        <div style={{
          fontSize: 11, color: "#EF4444", padding: "8px 10px",
          background: "rgba(239,68,68,0.08)", borderRadius: 8,
          border: "1px solid rgba(239,68,68,0.2)",
          lineHeight: 1.5,
        }}>
          {error}
        </div>
      )}
 
      {/* ── CSS-анимация пульса (inline keyframes) ──────────────────────── */}
      <style>{`
        @keyframes rec-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.3; transform: scale(0.75); }
        }
      `}</style>
    </div>
  );
}