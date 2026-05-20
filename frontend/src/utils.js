let _idCounter = 100;
export const genBlockId = () => `block_${++_idCounter}`;

export const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
};

export const now = () =>
  new Date().toLocaleTimeString("ru-RU", { hour12: false });

/**
 * Конвертирует Markdown в HTML без внешних зависимостей.
 * Покрывает: заголовки, жирный/курсив, код, списки, таблицы,
 * блок-цитаты, горизонтальные линии, ссылки, переносы строк.
 */
export function markdownToHtml(markdown) {
  if (!markdown || typeof markdown !== "string") return "";

  let html = markdown;

  // ── Экранирование HTML-спецсимволов в блоках кода ────────────────────────
  // Сначала вытаскиваем блоки кода во временные плейсхолдеры,
  // чтобы их содержимое не обрабатывалось остальными правилами
  const codeBlocks = [];
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const escaped = code
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    const langAttr = lang ? ` class="language-${lang}"` : "";
    codeBlocks.push(`<pre><code${langAttr}>${escaped.trimEnd()}</code></pre>`);
    return `%%CODE_BLOCK_${codeBlocks.length - 1}%%`;
  });

  // Инлайн-код
  const inlineCodes = [];
  html = html.replace(/`([^`]+)`/g, (_, code) => {
    const escaped = code
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    inlineCodes.push(`<code>${escaped}</code>`);
    return `%%INLINE_CODE_${inlineCodes.length - 1}%%`;
  });

  // ── Заголовки ─────────────────────────────────────────────────────────────
  html = html.replace(/^######\s+(.+)$/gm, "<h6>$1</h6>");
  html = html.replace(/^#####\s+(.+)$/gm,  "<h5>$1</h5>");
  html = html.replace(/^####\s+(.+)$/gm,   "<h4>$1</h4>");
  html = html.replace(/^###\s+(.+)$/gm,    "<h3>$1</h3>");
  html = html.replace(/^##\s+(.+)$/gm,     "<h2>$1</h2>");
  html = html.replace(/^#\s+(.+)$/gm,      "<h1>$1</h1>");

  // ── Горизонтальная линия ──────────────────────────────────────────────────
  html = html.replace(/^(?:---|\*\*\*|___)\s*$/gm, "<hr>");

  // ── Блок-цитаты ───────────────────────────────────────────────────────────
  html = html.replace(/((?:^>.*\n?)+)/gm, (block) => {
    const inner = block.replace(/^>\s?/gm, "").trim();
    return `<blockquote>${inner}</blockquote>\n`;
  });

  // ── Таблицы ───────────────────────────────────────────────────────────────
  html = html.replace(/((?:^\|.+\|\n)+)/gm, (tableBlock) => {
    const rows = tableBlock.trim().split("\n");
    if (rows.length < 2) return tableBlock;

    const isSeparator = (row) => /^\|[-:| ]+\|$/.test(row.trim());
    const parseRow = (row) =>
      row.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());

    let result = "<table>\n";
    let inBody = false;

    rows.forEach((row, i) => {
      if (isSeparator(row)) { inBody = true; return; }

      const cells = parseRow(row);
      if (i === 0) {
        result += "<thead><tr>" + cells.map((c) => `<th>${c}</th>`).join("") + "</tr></thead>\n";
      } else {
        if (!inBody) { result += "<tbody>\n"; inBody = true; }
        result += "<tr>" + cells.map((c) => `<td>${c}</td>`).join("") + "</tr>\n";
      }
    });

    if (inBody) result += "</tbody>\n";
    result += "</table>";
    return result;
  });

  // ── Списки ────────────────────────────────────────────────────────────────
  // Нумерованный
  html = html.replace(/((?:^\d+\.\s+.+\n?)+)/gm, (block) => {
    const items = block.trim().split("\n")
      .map((line) => `<li>${line.replace(/^\d+\.\s+/, "")}</li>`)
      .join("\n");
    return `<ol>\n${items}\n</ol>\n`;
  });

  // Маркированный (-, *, +)
  html = html.replace(/((?:^[-*+]\s+.+\n?)+)/gm, (block) => {
    const items = block.trim().split("\n")
      .map((line) => `<li>${line.replace(/^[-*+]\s+/, "")}</li>`)
      .join("\n");
    return `<ul>\n${items}\n</ul>\n`;
  });

  // ── Инлайн-форматирование ─────────────────────────────────────────────────
  // Жирный + курсив
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/___(.+?)___/g,        "<strong><em>$1</em></strong>");
  // Жирный
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__(.+?)__/g,      "<strong>$1</strong>");
  // Курсив
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/_(.+?)_/g,   "<em>$1</em>");
  // Зачёркнутый
  html = html.replace(/~~(.+?)~~/g, "<del>$1</del>");

  // ── Ссылки и изображения ─────────────────────────────────────────────────
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2">');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,  '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // ── Параграфы и переносы строк ────────────────────────────────────────────
  // Двойной перенос → новый параграф
  html = html
    .split(/\n{2,}/)
    .map((block) => {
      block = block.trim();
      if (!block) return "";
      // Не оборачиваем в <p> то, что уже является блочным элементом
      const isBlock = /^<(h[1-6]|ul|ol|li|table|blockquote|pre|hr|thead|tbody|tr)/.test(block);
      if (isBlock) return block;
      // Одиночный перенос внутри параграфа → <br>
      return `<p>${block.replace(/\n/g, "<br>")}</p>`;
    })
    .join("\n");

  // ── Восстанавливаем плейсхолдеры ─────────────────────────────────────────
  html = html.replace(/%%CODE_BLOCK_(\d+)%%/g,  (_, i) => codeBlocks[+i]);
  html = html.replace(/%%INLINE_CODE_(\d+)%%/g, (_, i) => inlineCodes[+i]);

  return html;
}
