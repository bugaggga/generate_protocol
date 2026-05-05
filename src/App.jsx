import { GlobalUploadBar } from "./components/GlobalUploadBar";
import { GlobalRecordBar } from "./components/GlobalRecordBar"
import { OperationsList } from "./components/OperationsList";
import { FormPanel } from "./components/FormPanel";
import { UploadPanel } from "./components/UploadPanel";
import { ProtocolPanel } from "./components/ProtocolPanel";
import { inputStyle } from "./components/ui/styles";
import { FormBuilderContext } from "./context/FormBuilderContext";
import { AppProvider, useAppContext } from "./context/AppContext";
import { useFormBuilder} from "./hooks/useFormBuilder"

function ActiveOperationView({ operation, apiBase }) {
  const { activeFormState, updateOperationForm } = useAppContext();
  
  // ✅ Вызываем хук на верхнем уровне
  const formBuilder = useFormBuilder(
    apiBase, 
    activeFormState,
    (updates) => updateOperationForm(operation.id, updates)
  );

  return (
    <FormBuilderContext.Provider value={formBuilder}>
      <div style={{ display: "flex", flexDirection: "column", flex: 1, gap: 20 }}>
        
        {/* Заголовок операции */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
           <h2 style={{ margin: 0, fontSize: 16 }}>{operation.filename}</h2>
           <span style={{ fontSize: 10, fontFamily: "monospace", color: "#888" }}>
             {operation.id.slice(0, 8)}...
           </span>
        </div>

        {/* Верхняя часть: Форма и Кнопки загрузки */}
        <div style={{ display: "flex", gap: 20, flex: 1, minHeight: 0 }}>
           <div style={{ flex: 1, minWidth: 300 }}>
              <FormPanel operationId={operation.id} />
           </div>
           
           <div style={{ width: 340, flexShrink: 0 }}>
              <UploadPanel operationId={operation.id} />
           </div>
        </div>

        {/* Нижняя часть: Протокол */}
        <div style={{ height: 300, borderTop: "1px solid var(--color-border-tertiary)", paddingTop: 20 }}>
           <ProtocolPanel
            operationId={operation.id}
          />
        </div>
      </div>
    </FormBuilderContext.Provider>
  );
}

function AppContent() {
  const { apiBase, setApiBase, activeOperation } = useAppContext();

  return (
    <div style={{
      fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
      color: "var(--color-text-primary)",
      height: "100vh", display: "flex", flexDirection: "column",
      background: "var(--color-background-tertiary)",
    }}>
      {/* Header */}
      <header style={{
        background: "var(--color-background-primary)",
        borderBottom: "1px solid var(--color-border-tertiary)",
        padding: "0 20px", height: 52, flexShrink: 0,
        display: "flex", alignItems: "center", gap: 16,
      }}>
        <span style={{ fontSize: 14, fontWeight: 700 }}>Meeting Protocol</span>
        <div style={{ flex: 1 }} />
        <input value={apiBase} onChange={e => setApiBase(e.target.value)} 
          style={inputStyle({ width: 200, fontSize: 11 })} />
      </header>

      <main style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Левая колонка: Глобальная загрузка + Список */}
        <aside style={{
          width: 280, flexShrink: 0, overflowY: "auto",
          borderRight: "1px solid var(--color-border-tertiary)",
          background: "var(--color-background-primary)",
          padding: 20, display: "flex", flexDirection: "column", gap: 20,
        }}>
          <GlobalUploadBar />
          <GlobalRecordBar />
          <OperationsList />
        </aside>

        {/* Правая колонка: Контент */}
        <section style={{ flex: 1, padding: 20, overflowY: "auto", background: "var(--color-background-primary)" }}>
          {activeOperation ? (
            <ActiveOperationView operation={activeOperation} apiBase={apiBase}/>
          ) : (
            <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#888" }}>
              Выберите операцию или загрузите файл
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}