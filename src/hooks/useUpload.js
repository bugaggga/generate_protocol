import { useState, useEffect, useRef } from "react";
import { triggerProcessing, cancelOperation, uploadFileWithProgressAndRetry } from "../api/operations";
import { now } from "../utils";
import { UPLOAD_PHASES } from "../constants";
import { useAppContext } from "../context/AppContext"

export function useUpload(apiBase, formJson, operationId, activeUploadState) {
  const { updateOperationUpload, cancelPolling  } = useAppContext();

  const [phase, setPhase] = useState(activeUploadState?.phase ?? UPLOAD_PHASES.IDLE);
  const [progress, setProgress] = useState(activeUploadState?.progress ?? 0);
  const [logs, setLogs] = useState(activeUploadState?.logs ?? []);

  const formJsonRef = useRef(formJson);

  useEffect(() => {
    formJsonRef.current = formJson;
  }, [formJson]);

  // При смене operationId восстанавливаем состояние из контекста
  useEffect(() => {
    setPhase(activeUploadState?.phase       ?? UPLOAD_PHASES.IDLE);
    setProgress(activeUploadState?.progress ?? 0);
    setLogs(activeUploadState?.logs         ?? []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operationId]);

  // Синхронизируем локальное состояние обратно в контекст.
  // AppContext читает operationUploads[opId].phase чтобы стартовать polling.
  useEffect(() => {
    if (!operationId) return;
    updateOperationUpload(operationId, { phase, progress, logs });
  }, [phase, progress, logs, operationId, updateOperationUpload]);
 
  const log = (msg, type = "info") =>
    setLogs(prev => [...prev.slice(-50), { msg, type, time: now() }]);
 
  const execute = async (op) => {
    if (!op) return;
    try {
      setPhase(UPLOAD_PHASES.UPLOADING);
      log("Загрузка файла в S3...");
 
      //await uploadFileWithProgress(op.file, op.s3_presigned_url, p => setProgress(p));
      await uploadFileWithProgressAndRetry(
      apiBase,
      op.file,
      op.s3_presigned_url,
      op.s3_key,
      (p) => setProgress(p)
    );
      log("Файл загружен. Запускаем обработку...", "success");
 
      setPhase(UPLOAD_PHASES.PROCESSING);
      await triggerProcessing(apiBase, op.id, formJsonRef.current, op.s3_key);
 
      // setPhase(DONE) → useEffect синхронизирует в контекст →
      // AppContext видит phase=DONE → запускает polling для op.id
      setPhase(UPLOAD_PHASES.DONE);
      log("Обработка запущена. Ожидаем протокол...", "success");
    } catch (err) {
      setPhase(UPLOAD_PHASES.ERROR);
      log(err.message, "error");
    }
  };

  const cancel = async (op) => {
    if (!op) return;
    try {
      setPhase(UPLOAD_PHASES.CANCELLING);
      log("Отмена обработки...");
 
      await cancelOperation(apiBase, op.id);
 
      // Останавливаем polling и сбрасываем протокол через контекст
      cancelPolling(op.id);
 
      // Сбрасываем фазу в IDLE — кнопка запуска снова становится активной
      setPhase(UPLOAD_PHASES.IDLE);
      setProgress(0);
      log("Обработка отменена. Можно запустить повторно.", "warn");
    } catch (err) {
      // Если отмена не удалась — возвращаем в DONE (polling продолжается)
      setPhase(UPLOAD_PHASES.DONE);
      log("Не удалось отменить: " + err.message, "error");
    }
  };

  // Повторный запуск обработки без повторной загрузки файла в S3.
  // Файл уже лежит в S3 по op.s3_key — просто снова вызываем triggerProcessing.
  const reprocess = async (op) => {
    if (!op) return;
    try {
      // cancelPolling сбрасывает pollingStarted guard в AppContext и протокол → idle.
      // Без этого повторный setPhase(DONE) не запустит новый polling (guard уже стоит).
      cancelPolling(op.id);
 
      setPhase(UPLOAD_PHASES.PROCESSING);
      log("Повторный запуск обработки...");
 
      await triggerProcessing(apiBase, op.id, formJsonRef.current, op.s3_key);
 
      // setPhase(DONE) → useEffect → AppContext видит DONE → стартует polling
      setPhase(UPLOAD_PHASES.DONE);
      log("Обработка запущена повторно. Ожидаем протокол...", "success");
    } catch (err) {
      setPhase(UPLOAD_PHASES.ERROR);
      log(err.message, "error");
    }
  };
 
  const isBusy = [
    UPLOAD_PHASES.CREATING,
    UPLOAD_PHASES.UPLOADING,
    UPLOAD_PHASES.PROCESSING,
    UPLOAD_PHASES.CANCELLING,
  ].includes(phase);
 
  return { phase, progress, logs, isBusy, execute, cancel, reprocess };
}