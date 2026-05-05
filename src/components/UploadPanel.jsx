import { useEffect } from "react";
import { useUpload } from "../hooks/useUpload";
import { StepRow, ProgressBar, LogConsole } from "./ui/Primitives";
import { UPLOAD_PHASES } from "../constants";
import { formatBytes } from "../utils";

import { useFormBuilderContext } from "../context/FormBuilderContext";
import { useAppContext } from "../context/AppContext"


const STEPS = [
  { key: UPLOAD_PHASES.CREATING,   label: "Создание операции",   sub: "POST /api/operations → запись в БД" },
  { key: UPLOAD_PHASES.UPLOADING,  label: "Загрузка файла в S3", sub: null },
  { key: UPLOAD_PHASES.PROCESSING, label: "Запуск обработки",    sub: "POST /api/operations/{id}/process" },
];

const PHASE_ORDER = [UPLOAD_PHASES.CREATING, UPLOAD_PHASES.UPLOADING, UPLOAD_PHASES.PROCESSING];

function resolveStepStatus(phase, stepKey) {
  const cur = PHASE_ORDER.indexOf(phase);
  const me  = PHASE_ORDER.indexOf(stepKey);
  if (phase === UPLOAD_PHASES.DONE)                    return "done";
  if (phase === UPLOAD_PHASES.ERROR && me === cur)     return "error";
  if (cur > me)                                        return "done";
  if (cur === me)                                      return "loading";
  return "idle";
}

const BTN_LABEL = {
  [UPLOAD_PHASES.IDLE]:       "Загрузить и обработать",
  [UPLOAD_PHASES.CREATING]:   "Создание операции…",
  [UPLOAD_PHASES.UPLOADING]:  (p) => `Загрузка ${p}%…`,
  [UPLOAD_PHASES.PROCESSING]: "Запуск обработки…",
  [UPLOAD_PHASES.DONE]:       "✓ Успешно завершено",
  [UPLOAD_PHASES.ERROR]:      "Повторить попытку",
};

export function UploadPanel( {operationId} ) {
  const { formJson } = useFormBuilderContext();
  const { apiBase, activeUploadState, updateOperationUpload, activeOperation, activeProtocolState } = useAppContext();
  
  const { phase, progress, logs, isBusy, execute, cancel, reprocess } = useUpload(
    apiBase, formJson, operationId, activeUploadState,
  );

  // 🔹 Синхронизируем состояние обратно в контекст
  useEffect(() => {
    if (operationId) {
      updateOperationUpload(operationId, { phase, progress, logs });
    }
  }, [phase, progress, logs, operationId, updateOperationUpload]);

  // Если нет активной операции, ничего не рендерим
  if (!operationId) return null;

  const btnDisabled = isBusy || phase === UPLOAD_PHASES.DONE;
  const btnBg =
      phase === UPLOAD_PHASES.DONE  ? "#10B981" :
      phase === UPLOAD_PHASES.ERROR ? "#EF4444" :
      isBusy               ? "var(--color-border-secondary)" : "#3B82F6";
  const btnColor = isBusy && phase !== UPLOAD_PHASES.ERROR && phase !== UPLOAD_PHASES.DONE
      ? "var(--color-text-tertiary)" : "#fff";
  
  const btnLabel = typeof BTN_LABEL[phase] === "function"
      ? BTN_LABEL[phase](progress)
      : BTN_LABEL[phase] ?? BTN_LABEL[UPLOAD_PHASES.IDLE];
  
    /*const s3Sub = operationId
      ? `key: operations/${operationId.slice(0, 8)}…/${file.name}`
      : STEPS[1].sub;*/

  const handleClick = () => {
    if (phase === UPLOAD_PHASES.ERROR) { /* retry */ return; }
    if (!activeOperation || isBusy || phase === UPLOAD_PHASES.DONE) return;
    execute(activeOperation);
  };

  // ── Кнопка «Отменить» ────────────────────────────────────────────────────
  // Активна только пока идёт обработка на сервере (phase === DONE означает
  // что запрос ушёл и сервер работает) или во время PROCESSING.
  const cancelBtnActive =
    phase === UPLOAD_PHASES.DONE ||
    phase === UPLOAD_PHASES.PROCESSING;
  const cancelBtnDisabled = !cancelBtnActive || phase === UPLOAD_PHASES.CANCELLING;
 
  const handleCancel = () => {
    if (cancelBtnDisabled) return;
    cancel(activeOperation);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── File info ── */}
      <div style={{
        border: `2px solid ${phase === UPLOAD_PHASES.DONE ? "#10B981" : "var(--color-border-secondary)"}`,
        borderRadius: 12, padding: "16px", background: "var(--color-background-secondary)",
      }}>
        <div style={{ fontSize: 24, marginBottom: 6 }}></div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{activeOperation.filename}</div>
        <div style={{ fontSize: 11, color: "var(--color-text-tertiary)", marginTop: 3 }}>
          {formatBytes(activeOperation.fileSize)} · операция {activeOperation.id.slice(0, 8)}…
        </div>
      </div>

      {/* ── Steps ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {STEPS.map((step, i) => (
          <StepRow key={step.key} index={i} label={step.label} sub={step.sub} status={resolveStepStatus(phase, step.key)} />
        ))}
      </div>

      {/* ── Progress ── */}
      {phase === UPLOAD_PHASES.UPLOADING && <ProgressBar value={progress} />}

      {/* ── Action Button ── */}
      <button
        onClick={handleClick} 
        disabled={btnDisabled}
        style={{
          padding: "11px", borderRadius: 9, border: "none",
          cursor: btnDisabled ? "not-allowed" : "pointer",
          background: btnBg, color: btnColor,
          fontWeight: 600, fontSize: 13, transition: "all 0.15s",
        }}
      >
        {btnLabel}
      </button>

      {/* Cancel button — показываем только когда есть смысл */}
        {(phase === UPLOAD_PHASES.PROCESSING ||
          phase === UPLOAD_PHASES.DONE       ||
          phase === UPLOAD_PHASES.CANCELLING) && (
          <button
            onClick={handleCancel}
            disabled={cancelBtnDisabled}
            title="Отменить обработку"
            style={{
              padding: "11px 16px", borderRadius: 9, border: "none",
              cursor: cancelBtnDisabled ? "not-allowed" : "pointer",
              background: cancelBtnDisabled
                ? "var(--color-border-secondary)"
                : "#FEF2F2",
              color: cancelBtnDisabled ? "var(--color-text-tertiary)" : "#EF4444",
              fontWeight: 600, fontSize: 13, transition: "all 0.15s",
              flexShrink: 0,
            }}
            onMouseEnter={e => {
              if (!cancelBtnDisabled)
                e.currentTarget.style.background = "#FCA5A5";
            }}
            onMouseLeave={e => {
              if (!cancelBtnDisabled)
                e.currentTarget.style.background = "#FEF2F2";
            }}
          >
            {phase === UPLOAD_PHASES.CANCELLING ? "…" : "✕ Отменить"}
          </button>
        )
      }

      {/* ── Reprocess Button — только когда протокол успешно получен ── */}
      {activeProtocolState?.status === "completed" && (
        <button
          onClick={() => reprocess(activeOperation)}
          disabled={isBusy}
          style={{
            padding: "11px", borderRadius: 9, border: "none",
            cursor: isBusy ? "not-allowed" : "pointer",
            background: isBusy ? "var(--color-border-secondary)" : "#F0F9FF",
            color: isBusy ? "var(--color-text-tertiary)" : "#0369A1",
            fontWeight: 600, fontSize: 13, transition: "all 0.15s",
          }}
          onMouseEnter={e => {
            if (!isBusy) e.currentTarget.style.background = "#BAE6FD";
          }}
          onMouseLeave={e => {
            if (!isBusy) e.currentTarget.style.background = "#F0F9FF";
          }}
        >
          ↺ Обработать повторно
        </button>
      )}

      {/* ── Logs ── */}
      <LogConsole logs={logs} />
    </div>
  );
}
