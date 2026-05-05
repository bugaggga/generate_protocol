import { useRef, useState } from "react";
import { useAppContext } from "../context/AppContext";
import { createOperation } from "../api/operations";
import { ACCEPTED_FORMATS } from "../constants";

export function GlobalUploadBar() {
  const { apiBase, addOperation } = useAppContext();
  const inputRef = useRef(null);
  const [loading, setLoading] = useState(false);

  const handleFile = async (file) => {
    if (!file || loading) return;
    setLoading(true);
    try {
      // 1. Создаем запись в БД
      const {operation_id, s3Data}  = await createOperation(apiBase, { filename: file.name });
      
      // 2. Добавляем в список операций в контексте
      addOperation(file, operation_id, s3Data);
      
    } catch (err) {
      console.error("Error creating operation:", err);
      alert("Ошибка создания операции: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => { 
        e.preventDefault();
        handleFile(e.dataTransfer.files[0]);
        if (inputRef.current) inputRef.current.value = ""; 
      }}
      style={{
        border: "2px dashed var(--color-border-secondary)",
        borderRadius: 12, padding: "16px", cursor: "pointer",
        background: "var(--color-background-secondary)",
        display: "flex", alignItems: "center", gap: 12,
        opacity: loading ? 0.5 : 1, transition: "0.2s"
      }}
    >
      <input
        ref={inputRef} type="file" style={{ display: "none" }}
        accept={ACCEPTED_FORMATS}
        onChange={(e) => {
          handleFile(e.target.files[0]);
          e.target.value = "";
        }}
      />
      <span style={{ fontSize: 24 }}>➕</span>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Загрузить новый файл</div>
        <div style={{ fontSize: 11, color: "var(--color-text-tertiary)" }}>MP3, WAV, MP4...</div>
      </div>
    </div>
  );
}