import { useRef, useEffect } from "react";
import { createContext, useContext, useState, useCallback } from "react";
import { DEFAULT_BLOCKS, UPLOAD_PHASES } from "../constants";
import { getOperationResult, getProtocolMarkdown } from "../api/operations";
import { markdownToHtml } from "../utils"

import { loadState, saveState } from "../persistState";

// eslint-disable-next-line react-refresh/only-export-components
export const AppContext = createContext(null);

// eslint-disable-next-line react-refresh/only-export-components
export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be used within AppProvider");
  return ctx;
}

export function AppProvider({ children }) {
  const [apiBase, setApiBase] = useState("http://127.0.0.1:80");

  // ── Восстанавливаем состояние из localStorage при первом рендере ──────────
  const _persisted = loadState();

  const [operations, setOperations]               = useState(_persisted?.operations          ?? []);
  const [activeOperationId, setActiveOperationId] = useState(_persisted?.activeOperationId   ?? null);
  const [operationForms, setOperationForms]       = useState(_persisted?.operationForms      ?? {});
  const [operationUploads, setOperationUploads]   = useState(_persisted?.operationUploads    ?? {});
  const [operationProtocols, setOperationProtocols] = useState(_persisted?.operationProtocols ?? {});

  // ── Сохраняем состояние в localStorage с дебаунсом 600мс ─────────────────
  // Дебаунс нужен чтобы не писать в storage на каждый тик прогресс-бара.
  useEffect(() => {
    const timer = setTimeout(() => {
      saveState({ operations, activeOperationId, operationForms, operationUploads, operationProtocols });
    }, 600);
    return () => clearTimeout(timer);
  }, [operations, activeOperationId, operationForms, operationUploads, operationProtocols]);

  // ── Polling ───────────────────────────────────────────────────────────────
  // Polling живёт здесь, а не в компоненте/хуке.
  // Это значит:
  //  - переключение операций не убивает и не запускает новый polling;
  //  - создание новой операции не влияет на polling старой;
  //  - новая операция со status="idle" не получает polling пока сама не станет DONE.
 
  const pollingTimers  = useRef({});        // { [opId]: intervalId }
  const pollingStarted = useRef(new Set()); // guard — не стартовать дважды
  const apiBaseRef     = useRef(apiBase);
  useEffect(() => { apiBaseRef.current = apiBase; }, [apiBase]);

  // При первом рендере заполняем guard для операций, у которых протокол уже
  // завершён (restored из localStorage). Без этого polling-эффект перезапишет
  // status:"completed" → "polling" и протокол пропадёт с экрана.
  useEffect(() => {
    Object.entries(operationProtocols).forEach(([opId, protocol]) => {
      if (protocol.status === "completed" || protocol.status === "error") {
        pollingStarted.current.add(opId);
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // только на mount — operationProtocols намеренно не в deps
 
  // Чистим все таймеры при размонтировании провайдера
  useEffect(() => {
    const timers = pollingTimers.current;
    return () => Object.values(timers).forEach(clearInterval);
  }, []);
 
  // Реагируем на смену фазы upload у любой операции.
  // Как только phase === DONE — стартуем polling ровно один раз (guard через Set).
  useEffect(() => {
    Object.entries(operationUploads).forEach(([opId, uploadState]) => {
      if (uploadState.phase !== UPLOAD_PHASES.DONE) return;
      if (pollingStarted.current.has(opId))         return; // уже запущен
 
      pollingStarted.current.add(opId);
 
      // Помечаем протокол этой конкретной операции как "в ожидании"
      setOperationProtocols(prev => ({
        ...prev,
        [opId]: { ...(prev[opId] ?? {}), status: "polling" },
      }));
 
      pollingTimers.current[opId] = setInterval(async () => {
        try {
          const data = await getOperationResult(apiBaseRef.current, opId);
 
          if (data.status === "completed" || data.status === "done") {
            clearInterval(pollingTimers.current[opId]);
            delete pollingTimers.current[opId];
 
            setOperationProtocols(prev => ({
              ...prev,
              [opId]: { ...(prev[opId] ?? {}), status: "loading" },
            }));
 
            try {
              const markdown = await getProtocolMarkdown(apiBaseRef.current, opId);
              setOperationProtocols(prev => ({
                ...prev,
                [opId]: {
                  ...(prev[opId] ?? {}),
                  status: "completed",
                  protocolHtml: markdownToHtml(markdown),
                },
              }));
            } catch (err) {
              setOperationProtocols(prev => ({
                ...prev,
                [opId]: {
                  ...(prev[opId] ?? {}),
                  status: "error",
                  error: "Ошибка загрузки протокола: " + err.message,
                },
              }));
            }
 
          } else if (data.status === "failed" || data.status === "error") {
            clearInterval(pollingTimers.current[opId]);
            delete pollingTimers.current[opId];
            setOperationProtocols(prev => ({
              ...prev,
              [opId]: {
                ...(prev[opId] ?? {}),
                status: "error",
                error: "Обработка завершилась с ошибкой",
              },
            }));
          }
          // data.status === "processing" → продолжаем ждать, ничего не делаем
        } catch (err) {
          console.warn(`[polling] ${opId.slice(0, 8)}… error (will retry):`, err.message);
        }
      }, 3000);
    });
  }, [operationUploads]);


  // ── CRUD operations ────────────────────────────────────────────────────────────
  const addOperation = useCallback((fileData, operationId, s3Data) => {
    const newOp = {
      id: operationId,
      filename: fileData.name,
      fileSize: fileData.size,
      s3_key: s3Data.s3_key,
      s3_presigned_url: s3Data.s3_presigned_url,
      phase: "idle",
      progress: 0,
      logs: [],
      file: fileData,
    };

    setOperations(prev => [...prev, newOp]);

    setOperationForms(prev => ({
      ...prev,
      [operationId]: {
        blocks: DEFAULT_BLOCKS,
        formName: "Стандартный протокол совещания",
        selectedId: null,
      },
    }));

    setOperationUploads(prev => ({
      ...prev,
      [operationId]: { phase: "idle", progress: 0, logs: [] },
    }));

    // Инициализируем пустой протокол для операции
    setOperationProtocols(prev => ({
      ...prev,
      [operationId]: { status: "idle", protocolHtml: null, error: null },
    }));

    setActiveOperationId(operationId);
  }, []);

  const updateOperation = useCallback((id, updates) => {
    setOperations(prev => prev.map(op => op.id === id ? { ...op, ...updates } : op));
  }, []);

  const updateOperationForm = useCallback((operationId, updates) => {
    setOperationForms(prev => ({
      ...prev,
      [operationId]: { ...(prev[operationId] || {}), ...updates },
    }));
  }, []);

  const updateOperationUpload = useCallback((operationId, updates) => {
    setOperationUploads(prev => ({
      ...prev,
      [operationId]: { ...(prev[operationId] || {}), ...updates },
    }));
  }, []);

  // Обновление состояния протокола конкретной операции
  const updateOperationProtocol = useCallback((operationId, updates) => {
    setOperationProtocols(prev => ({
      ...prev,
      [operationId]: { ...(prev[operationId] || {}), ...updates },
    }));
  }, []);

  // Останавливает polling для операции и сбрасывает её в исходное состояние.
  // Вызывается из useUpload после успешного запроса на отмену.
  const cancelPolling = useCallback((operationId) => {
    // Останавливаем таймер
    if (pollingTimers.current[operationId]) {
      clearInterval(pollingTimers.current[operationId]);
      delete pollingTimers.current[operationId];
    }
    // Убираем из guard-сета — операцию можно будет запустить повторно
    pollingStarted.current.delete(operationId);
 
    // Сбрасываем протокол в idle — панель покажет "запустите обработку"
    setOperationProtocols(prev => ({
      ...prev,
      [operationId]: { status: "idle", protocolHtml: null, error: null },
    }));
  }, []);

  /**
  * Удаляет операцию из всех словарей контекста.
  * Вызывается после успешного DELETE-запроса на сервер.
  */
  const removeOperation = useCallback((operationId) => {
    // Останавливаем polling если он идёт
    if (pollingTimers.current[operationId]) {
      clearInterval(pollingTimers.current[operationId]);
      delete pollingTimers.current[operationId];
    }
    pollingStarted.current.delete(operationId);
 
  // Убираем из всех словарей состояния
  setOperations(prev => prev.filter(op => op.id !== operationId));
  setOperationForms(prev => { const s = { ...prev }; delete s[operationId]; return s; });
  setOperationUploads(prev => { const s = { ...prev }; delete s[operationId]; return s; });
  setOperationProtocols(prev => { const s = { ...prev }; delete s[operationId]; return s; });
 
  // Если удаляемая операция была активной — переключаемся на последнюю оставшуюся
  setActiveOperationId(prev => {
    if (prev !== operationId) return prev;
    const remaining = operations.filter(op => op.id !== operationId);
    return remaining.length > 0 ? remaining[remaining.length - 1].id : null;
  });
}, [operations]);

  const activeOperation     = operations.find(op => op.id === activeOperationId) || null;
  const activeFormState     = activeOperationId ? (operationForms[activeOperationId]    || {}) : {};
  const activeUploadState   = activeOperationId ? (operationUploads[activeOperationId]  || {}) : {};
  const activeProtocolState = activeOperationId ? (operationProtocols[activeOperationId] || {}) : {};

  return (
    <AppContext.Provider value={{
      apiBase, setApiBase,
      operations, activeOperationId, setActiveOperationId, activeOperation,
      addOperation, updateOperation,
      operationForms, activeFormState, updateOperationForm,
      operationUploads, activeUploadState, updateOperationUpload,
      // протокол
      operationProtocols,
      activeProtocolState,
      updateOperationProtocol,
      cancelPolling, removeOperation
    }}>
      {children}
    </AppContext.Provider>
  );
}