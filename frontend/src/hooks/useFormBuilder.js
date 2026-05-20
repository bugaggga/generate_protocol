import { useState } from "react";
import { submitForm } from "../api/operations";
import { genBlockId } from "../utils";
import { DEFAULT_BLOCKS, BLOCK_TYPES } from "../constants";

export function useFormBuilder(apiBase, externalState = null, onUpdate = null) {
  // Если передано внешнее состояние — используем его
  const [internalBlocks, setInternalBlocks] = useState(DEFAULT_BLOCKS);
  const [internalFormName, setInternalFormName] = useState("Стандартный протокол совещания");
  const [selectedId, setSelectedId] = useState(null);



  // Определяем, какие значения использовать
  const blocks = externalState?.blocks || internalBlocks;
  const formName = externalState?.formName || internalFormName;
  
  const [submitting, setSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState(null);
  const [submitError, setSubmitError] = useState("");

  const setFormName = (name) => {
    if (onUpdate) {
      onUpdate({ formName: name });
    } else {
      setInternalFormName(name);
    }
  };

  const setBlocks = (updater) => {
  if (onUpdate) {
    const current = externalState?.blocks ?? internalBlocks;
    const next = typeof updater === "function" ? updater(current) : updater;
    onUpdate({ blocks: next });
  } else {
    setInternalBlocks(updater);
  }
};

  const formJson = {
    form_id: "protocol_form",
    name: formName,
    version: "1.0",
    blocks: blocks.map((b) => ({ ...b })),
  };

  const selectedBlock = blocks.find((b) => b.id === selectedId) ?? null;

  const addBlock = (type) => {
    const meta = BLOCK_TYPES.find((t) => t.type === type);
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
    setBlocks(prev => [...prev, newBlock]);
    setSelectedId(newBlock.id);
  };

  const deleteBlock = (id) => {
    setBlocks(prev => prev.filter(b => b.id !== id).map((b, i) => ({ ...b, order: i + 1 })));
    if (selectedId === id) setSelectedId(null);
  };

  const updateBlock = (updated) =>
    setBlocks(prev => prev.map(b => b.id === updated.id ? updated : b));

  const moveBlock = (index, direction) => {
    const next = index + direction;
    if (next < 0 || next >= blocks.length) return;
    const arr = [...blocks];
    [arr[index], arr[next]] = [arr[next], arr[index]];
    setBlocks(arr.map((b, i) => ({ ...b, order: i + 1 })));
  };

  const send = async (operationId = null) => {
    setSubmitting(true);
    setSubmitStatus(null);
    setSubmitError("");
    try {
      await submitForm(apiBase, formJson, operationId);
      setSubmitStatus("ok");
      setTimeout(() => setSubmitStatus(null), 4000);
    } catch (err) {
      setSubmitStatus("error");
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return {
    blocks, formName, setFormName,
    selectedId, setSelectedId, selectedBlock,
    formJson,
    submitting, submitStatus, submitError,
    addBlock, deleteBlock, updateBlock, moveBlock, send,
  };
}