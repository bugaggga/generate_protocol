import { inputStyle, sectionLabel } from "./ui/styles";

/**
 * EditBlockPanel — панель редактирования свойств одного блока.
 * Только разметка. Логика мутаций живёт в useFormBuilder.
 */
export function EditBlockPanel({ block, onChange }) {

  const listEditor = (fieldKey) => (
    <div>
      {(block[fieldKey] ?? []).map((item, i) => (
        <div key={i} style={{ display: "flex", gap: 4, marginBottom: 5 }}>
          <input
            value={item.key}
            placeholder="key"
            onChange={(e) => {
              const arr = [...block[fieldKey]];
              arr[i] = { key: e.target.value };
              onChange({ ...block, [fieldKey]: arr });
            }}
            style={inputStyle({ flex: 1, fontFamily: "monospace", fontSize: 11 })}
          />
          <button
            onClick={() => onChange({ ...block, [fieldKey]: block[fieldKey].filter((_, j) => j !== i) })}
            style={{
              padding: "3px 8px", background: "none",
              border: "1px solid var(--color-border-tertiary)",
              borderRadius: 5, cursor: "pointer",
              color: "var(--color-text-tertiary)", fontSize: 12,
            }}>
            ✕
          </button>
        </div>
      ))}
      <button
        onClick={() => onChange({ ...block, [fieldKey]: [...(block[fieldKey] ?? []), { key: "" }] })}
        style={{
          fontSize: 11, padding: "3px 10px", borderRadius: 6, cursor: "pointer",
          background: "none", border: "1px dashed var(--color-border-secondary)",
          color: "var(--color-text-secondary)",
        }}>
        + Добавить
      </button>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      <div>
        <div style={sectionLabel}>Название</div>
        <input
          value={block.title}
          onChange={(e) => onChange({ ...block, title: e.target.value })}
          style={inputStyle({ 
            borderRadius: 0.5,
          })}
        />
      </div>

      <div>
        <div style={sectionLabel}>Инструкция для LLM</div>
        <textarea
          value={block.llm_instruction}
          rows={4}
          onChange={(e) => onChange({ ...block, llm_instruction: e.target.value })}
          style={inputStyle({ 
            fontFamily: "inherit", 
            resize: "vertical", 
            lineHeight: 1.55, 
            fontSize: 12,
          })}
        />
      </div>

      {block.type === "table" && (
        <div>
          <div style={sectionLabel}>Колонки таблицы</div>
          {listEditor("columns")}
        </div>
      )}

      {block.type === "fields" && (
        <div>
          <div style={sectionLabel}>Поля</div>
          {listEditor("fields")}
        </div>
      )}
    </div>
  );
}
