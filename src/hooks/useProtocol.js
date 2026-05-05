import { useAppContext } from "../context/AppContext";

/**
 * useProtocol — только читает состояние протокола из контекста.
 * Никакого polling здесь нет — он полностью вынесен в AppContext.
 * Это значит, что монтирование/размонтирование ProtocolPanel
 * никак не влияет на ход polling.
 */
export function useProtocol(operationId) {
  const { operationProtocols } = useAppContext();
 
  return operationProtocols[operationId] ?? {
    status:      "idle",
    protocolHtml: null,
    error:       null,
  };
}