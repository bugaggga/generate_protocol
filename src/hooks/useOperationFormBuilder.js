// hooks/useOperationFormBuilder.js
import { useState, useCallback } from "react";
import { useAppContext } from "../context/AppContext";
import { submitForm } from "../api/operations";
import { genBlockId } from "../utils";
import { BLOCK_TYPES } from "../constants";

export function useOperationFormBuilder(operationId) {
  const { apiBase, activeOperation, updateFormState, updateFormBlocks } = useAppContext();

  // 🔹 1. ВСЕ хуки объявляем СРАЗУ, без условий
  const [submitting, setSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState(null);
  const [submitError, setSubmitError] = useState("");

  // Безопасно извлекаем данные (без ошибки, если activeOperation === null)
  const isCurrentOp = activeOperation?.id === operationId;
  const formState = isCurrentOp ? activeOperation.formState : null;
  
  const blocks = formState?.blocks || [];
  const formName = formState?.formName || "";
  const selectedId = formState?.selectedId || null;

  const formJson = {
    form_id: "protocol_form",
    name: formName,
    version: "1.0",
    blocks: blocks.map(b => ({ ...b })),
  };

  const selectedBlock = blocks.find(b => b.id === selectedId) || null;

  // 🔹 2. useCallback тоже вызываются ВСЕГДА (защита внутри)
  const addBlock = useCallback((type) => {
    if (!isCurrentOp) return;
    const meta = BLOCK_TYPES.find(t => t.type === type);
    const newBlock = {
      id: genBlockId(),
      order: blocks.length + 1,
      type,
      title: meta.label,
      required: false,
      llm_instruction: "",
      ...(type === "table" ? { columns: [{ key: "item" }] } : {}),
      ...(type === "fields" ? { fields: [{ key: "field1" }] } : {}),
    };
    updateFormBlocks(operationId, [...blocks, newBlock]);
    updateFormState(operationId, { selectedId: newBlock.id });
  }, [blocks, isCurrentOp, operationId, updateFormBlocks, updateFormState]);

  const deleteBlock = useCallback((id) => {
    if (!isCurrentOp) return;
    const newBlocks = blocks.filter(b => b.id !== id).map((b, i) => ({ ...b, order: i + 1 }));
    updateFormBlocks(operationId, newBlocks);
    if (selectedId === id) updateFormState(operationId, { selectedId: null });
  }, [blocks, selectedId, isCurrentOp, operationId, updateFormBlocks, updateFormState]);

  const updateBlock = useCallback((updated) => {
    if (!isCurrentOp) return;
    updateFormBlocks(operationId, blocks.map(b => b.id === updated.id ? updated : b));
  }, [blocks, isCurrentOp, operationId, updateFormBlocks]);

  const moveBlock = useCallback((index, direction) => {
    if (!isCurrentOp) return;
    const next = index + direction;
    if (next < 0 || next >= blocks.length) return;
    const arr = [...blocks];
    [arr[index], arr[next]] = [arr[next], arr[index]];
    updateFormBlocks(operationId, arr.map((b, i) => ({ ...b, order: i + 1 })));
  }, [blocks, isCurrentOp, operationId, updateFormBlocks]);

  const setSelectedId = useCallback((id) => {
    if (!isCurrentOp) return;
    updateFormState(operationId, { selectedId: id });
  }, [isCurrentOp, operationId, updateFormState]);

  const send = useCallback(async (opId = operationId) => {
    setSubmitting(true);
    setSubmitStatus(null);
    setSubmitError("");
    try {
      await submitForm(apiBase, formJson, opId);
      setSubmitStatus("ok");
      setTimeout(() => setSubmitStatus(null), 4000);
    } catch (err) {
      setSubmitStatus("error");
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  }, [apiBase, formJson, operationId]);

  // 🔹 3. УСЛОВНЫЙ RETURN только ПОСЛЕ всех хуков
  if (!isCurrentOp) {
    return {
      blocks: [], formName: "", formJson: {}, selectedId: null, selectedBlock: null,
      addBlock: () => {}, deleteBlock: () => {}, updateBlock: () => {},
      moveBlock: () => {}, setSelectedId: () => {}, send: () => {},
      submitting: false, submitStatus: null, submitError: "",
    };
  }

  // 🔹 4. Нормальный возврат для активной операции
  return {
    blocks, formName, formJson, selectedId, setSelectedId, selectedBlock,
    addBlock, deleteBlock, updateBlock, moveBlock, send,
    submitting, submitStatus, submitError,
  };
}