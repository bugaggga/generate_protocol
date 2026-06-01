import React, { useRef } from "react";
import { useProtocol } from "../hooks/useProtocol";
import { protocol-content } from "./ui/styles.css";

/**
 * ProtocolPanel
 *
 * Принимает только operationId.
 * Все данные (status, protocolHtml, error) получает через useProtocol,
 * который читает из контекста — поэтому протокол сохраняется при
 * переключении между операциями.
 */
export function ProtocolPanel({ operationId }) {
  const { status, protocolHtml, error } = useProtocol(operationId);
  const contentRef = useRef(null);

  const handleDownloadPDF = async () => {
    const element = contentRef.current;
    if (!element) return;
    const html2pdf = (await import("html2pdf.js")).default;
    await html2pdf().set({
      margin: 10,
      filename: `protocol-${operationId.slice(0, 8)}.pdf`,
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2 },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
    }).from(element).save();
  };

  // ── Состояния ─────────────────────────────────────────────────────────────

  if (status === "idle") {
    return (
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", padding: "32px 20px", gap: 10,
        color: "var(--color-text-tertiary)", textAlign: "center",
      }}>
        <span style={{ fontSize: 28, opacity: 0.3 }}>📋</span>
        <span style={{ fontSize: 13 }}>Запустите обработку, чтобы получить протокол</span>
      </div>
    );
  }

  if (status === "polling") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "20px 0",
        color: "var(--color-text-secondary)", fontSize: 13 }}>
        <span style={{
          display: "inline-block", width: 14, height: 14, flexShrink: 0,
          border: "2px solid var(--color-border-secondary)", borderTopColor: "#3B82F6",
          borderRadius: "50%", animation: "spin 0.8s linear infinite",
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
        Сервер обрабатывает запись... Проверяем каждые 3 сек.
      </div>
    );
  }

  if (status === "loading") {
    return (
      <div style={{ padding: "20px 0", color: "var(--color-text-secondary)", fontSize: 13 }}>
        📄 Загружаем текст протокола...
      </div>
    );
  }

  if (status === "error") {
    return (
      <div style={{
        padding: "14px 16px", borderRadius: 8,
        background: "#FEF2F2", border: "1px solid #FCA5A5",
        color: "#B91C1C", fontSize: 13,
      }}>
        ❌ {error}
      </div>
    );
  }

  if (!protocolHtml) {
    return (
      <div style={{ padding: "20px 0", color: "var(--color-text-tertiary)", fontSize: 13 }}>
        Протокол не получен
      </div>
    );
  }

  // ── Готовый протокол ──────────────────────────────────────────────────────
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 14, fontWeight: 600 }}>📋 Протокол операции</span>
        <button
          onClick={handleDownloadPDF}
          style={{
            padding: "7px 14px", borderRadius: 7,
            border: "1px solid var(--color-border-secondary)",
            background: "var(--color-background-secondary)",
            cursor: "pointer", fontSize: 12, fontWeight: 500,
            display: "flex", alignItems: "center", gap: 6,
          }}
          onMouseEnter={e => e.currentTarget.style.background = "var(--color-border-tertiary)"}
          onMouseLeave={e => e.currentTarget.style.background = "var(--color-background-secondary)"}
        >
          📄 Скачать PDF
        </button>
      </div>

      <style>{`
        .protocol-content table { border-collapse: collapse; width: 100%; margin: 12px 0; }
        .protocol-content th,
        .protocol-content td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
        .protocol-content thead th { background: #f5f5f5; font-weight: 600; }
      `}</style>
      <div
        ref={contentRef}
        className="protocol-content"
        style={{
          background: "#fff", color: "#000",
          padding: 24, borderRadius: 8,
          border: "1px solid var(--color-border-secondary)",
          minHeight: 200, fontSize: 14, lineHeight: 1.7,
        }}
      >
        <div dangerouslySetInnerHTML={{ __html: protocolHtml }} />
      </div>
    </div>
  );
}