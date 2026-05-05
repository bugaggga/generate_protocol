export const BLOCK_TYPES = [
  { type: "fields", label: "Поля",    icon: "▤", color: "#3B82F6" },
  { type: "list",   label: "Список",  icon: "≡", color: "#10B981" },
  { type: "table",  label: "Таблица", icon: "⊞", color: "#F59E0B" },
  { type: "text",   label: "Текст",   icon: "¶", color: "#8B5CF6" },
];

export const DEFAULT_BLOCKS = [
  {
    id: "general_info", order: 1, type: "fields", title: "Общие сведения", required: true,
    llm_instruction: "Извлеки дату, время, платформу, ФИО председателя и всех участников с должностями",
    fields: [{ key: "Дата" }, { key: "Платформа" }, { key: "Участники" }],
  },
  {
    id: "agenda", order: 2, type: "list", title: "Повестка дня", required: true,
    llm_instruction: "Перечисли все вопросы повестки дня в порядке обсуждения",
  },
  {
    id: "discussion", order: 3, type: "text", title: "Ход обсуждения", required: false,
    llm_instruction: "Кратко изложи ход обсуждения по каждому вопросу с указанием докладчиков",
  },
  {
    id: "tasks", order: 5, type: "table", title: "Поручения", required: true,
    llm_instruction: "Извлеки все поручения, назначенные участникам",
    columns: [{ key: "task" }, { key: "responsible" }, { key: "deadline" }],
  },
];

export const ACCEPTED_FORMATS = "audio/*,video/*,.mp3,.mp4,.wav,.m4a,.ogg,.webm";

export const UPLOAD_PHASES = {
  IDLE:       "idle",
  CREATING:   "creating",
  UPLOADING:  "uploading",
  PROCESSING: "processing",
  DONE:       "done",
  ERROR:      "error",
  CANCELLING:  "cancelling",
};
