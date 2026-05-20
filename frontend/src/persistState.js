import { UPLOAD_PHASES } from "./constants";

const STORAGE_KEY = "app_state_v1";

// Фазы, которые нельзя возобновить после перезагрузки
const INTERRUPTIBLE_PHASES = new Set([
  UPLOAD_PHASES.UPLOADING,
  UPLOAD_PHASES.PROCESSING,
  UPLOAD_PHASES.CANCELLING,
]);

// ── Сериализация ─────────────────────────────────────────────────────────────

export function saveState({ operations, activeOperationId, operationForms, operationUploads, operationProtocols }) {
  try {
    const serialized = {
      operations: operations.map(({ file, s3_presigned_url, ...rest }) => rest), // File не сериализуем, presigned URL протухнет
      activeOperationId,
      operationForms,
      operationUploads: sanitizeUploads(operationUploads),
      operationProtocols: sanitizeProtocols(operationProtocols),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(serialized));
  } catch (err) {
    console.warn("[persistState] Не удалось сохранить состояние:", err);
  }
}

// ── Десериализация ───────────────────────────────────────────────────────────

export function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (err) {
    console.warn("[persistState] Не удалось прочитать состояние:", err);
    return null;
  }
}

// ── Санитизация при сохранении ───────────────────────────────────────────────

// Сбрасываем незавершённые фазы: UPLOADING/PROCESSING/CANCELLING → IDLE.
// IDLE и DONE оставляем как есть (DONE означает «запрос ушёл на сервер»,
// polling перезапустится автоматически при восстановлении).
function sanitizeUploads(operationUploads) {
  return Object.fromEntries(
    Object.entries(operationUploads).map(([id, upload]) => [
      id,
      {
        ...upload,
        phase: INTERRUPTIBLE_PHASES.has(upload.phase) ? UPLOAD_PHASES.IDLE : upload.phase,
        progress: 0,
        // Логи сохраняем — полезно видеть историю после перезагрузки
      },
    ])
  );
}

// Polling не переживает перезагрузку — сбрасываем "polling" → "idle".
// "completed" и "error" сохраняем: протокол уже получен и не изменится.
function sanitizeProtocols(operationProtocols) {
  return Object.fromEntries(
    Object.entries(operationProtocols).map(([id, protocol]) => [
      id,
      {
        ...protocol,
        status: protocol.status === "polling" ? "idle" : protocol.status,
      },
    ])
  );
}