/**
 * api/operations.js
 *
 * Весь сетевой слой приложения.
 * Компоненты не используют fetch/XHR напрямую — только через эти функции.
 */

// ─── Operations ───────────────────────────────────────────────────────────────

/**
 * Создаёт запись операции в БД.
 * @returns {{ operation_id: string, upload_url: string }}
 */
export async function createOperation(apiBase, { filename }) {
  const res = await fetch(`${apiBase}/api/operations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_name: filename,
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Ошибка создания операции: HTTP ${res.status}${text ? ` — ${text}` : ""}`);
  }

  const data = await res.json();

  return {
    operation_id: data.operation_id,
    s3Data: {
      s3_key: data.s3_key,
      s3_presigned_url: data.s3_presigned_url
    }
  };
}

/**
 * Запускает обработку загруженного файла (ASR + LLM).
 * @returns {object} ответ сервера
 */
export async function triggerProcessing(apiBase, operationId, formJson, s3_key) {
  const res = await fetch(`${apiBase}/api/operations/${operationId}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      operation_id: operationId,
      form: formJson,
      s3_key: s3_key
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Ошибка запуска обработки: HTTP ${res.status}${text ? ` — ${text}` : ""}`);
  }

  return res.json();
}

/**
 * Отправляет шаблон формы протокола на бэкенд.
 * Если передан operationId — привязывает форму к операции.
 */
export async function submitForm(apiBase, formJson, operationId = null) {
  const url = operationId
    ? `${apiBase}/api/operations/${operationId}/form`
    : `${apiBase}/api/forms`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(formJson),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}${text ? ` — ${text}` : ""}`);
  }

  return res.json();
}

// ─── S3 upload ────────────────────────────────────────────────────────────────

/**
 * Загружает файл напрямую в S3 через presigned PUT URL.
 * Использует XHR вместо fetch — только XHR поддерживает события прогресса.
 *
 * @param {string}   presignedUrl  URL из ответа createOperation
 * @param {File}     file          объект File из input/drop
 * @param {function} onProgress    колбэк (percent: number) => void
 */
export function uploadToS3(presignedUrl, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", presignedUrl);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status < 300) {
        resolve(xhr);
      } else {
        reject(new Error(`S3 вернул HTTP ${xhr.status}`));
      }
    });

    xhr.addEventListener("error",   () => reject(new Error("Ошибка сети при загрузке в S3")));
    xhr.addEventListener("timeout", () => reject(new Error("Таймаут загрузки в S3")));

    xhr.send(file);
  });
}

/**
 * Запрашивает новый presigned URL для уже существующего объекта в S3.
 */
export async function refreshPresignedUrl(apiBase, s3Key) {
  const res = await fetch(`${apiBase}/api/get/presigned_url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ s3_key: s3Key }),
  });

  if (!res.ok) {
    throw new Error(`Не удалось обновить presigned URL: HTTP ${res.status}`);
  }

  const data = await res.json();
  return {
    "freshPresignedData": data.presigned_data
  }; // ожидаем тот же формат, что и s3_presigned_url из createOperation
}

export async function uploadFileWithProgressAndRetry(
  apiBase,
  file, 
  presignedData, 
  s3Key, 
  onProgress
) {
  try {
    await uploadFileWithProgress(file, presignedData, onProgress);
  } catch (err) {
    // S3 возвращает 403 при просроченном presigned URL
    if (!err.message.includes("403")) throw err;

    onProgress?.(0); // сбрасываем прогресс перед повтором

    const { freshPresignedData } = await refreshPresignedUrl(apiBase, s3Key);
    await uploadFileWithProgress(file, freshPresignedData, onProgress);
  }
}

/**
 * Загрузка файла с прогресс-баром
 */
export function uploadFileWithProgress(
  file, 
  presignedData,
  onProgress
) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();

    // Добавляем все поля
    Object.keys(presignedData.fields).forEach(key => {
      formData.append(key, presignedData.fields[key]);
    });
    formData.append('file', file);

    // Отслеживание прогресса загрузки
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        const percentComplete = (event.loaded / event.total) * 100;
        onProgress(percentComplete.toFixed(2));
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 204 || xhr.status === 200 || xhr.status === 201) {
        resolve({
          success: true,
          status: xhr.status,
          key: presignedData.fields.key
        });
      } else {
        reject(new Error(`Ошибка загрузки: ${xhr.status} - ${xhr.responseText}`));
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('Сетевая ошибка при загрузке'));
    });

    xhr.open('POST', presignedData.url);
    xhr.send(formData);
  });
}

/**
Проверяет статус операции
@returns {{ status: string, ... }}
*/
export async function getOperationResult(apiBase, operationId) {
  const res = await fetch(`${apiBase}/api/operations/${operationId}/status`);

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Ошибка проверки статуса: HTTP ${res.status}${text ? ` — ${text}` : ""}`);
  }

  // 🔹 Проверяем, что сервер действительно вернул JSON
  const contentType = res.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    const rawText = await res.text();
    console.error(" Ожидается JSON, но получен HTML/текст:", rawText.substring(0, 300));
    throw new Error(
      `Сервер вернул не JSON. Проверьте эндпоинт GET /api/operations/${operationId}/status`
    );
  }
  
  return res.json();
}

/**
Получает протокол операции в формате Markdown
@returns {string} markdown текст протокола
*/
export async function getProtocolMarkdown(apiBase, operationId) {
  const res = await fetch(`${apiBase}/api/operations/${operationId}/protocol`);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Ошибка получения протокола: HTTP ${res.status}${text ? ` — ${text}` : ""}`);
  }
  
  // Предполагаем, что сервер возвращает text/plain или application/json с полем markdown
  const contentType = res.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    const data = await res.json();
    return data.markdown || data.protocol || "";
  } else {
    return await res.text();
  }
}

/**
Скачивает протокол в формате PDF с сервера (если сервер умеет генерировать PDF)
@returns {Blob}
*/
export async function downloadProtocolPdf(apiBase, operationId) {
  const res = await fetch(`${apiBase}/api/operations/${operationId}/protocol/pdf`);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Ошибка скачивания PDF: HTTP ${res.status}${text ? ` — ${text}` : ""}`);
  }
  return await res.blob();
}

export async function cancelOperation(apiBase, operationId) {
  const res = await fetch(`${apiBase}/api/operations/${operationId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Ошибка отмены: HTTP ${res.status}${text ? ` — ${text}` : ""}`);
  }
  return res.json(); // { status: "cancelling" }
}

/**
 * Удаляет операцию с сервера.
 * На сервере boto3 удаляет объект из S3 по s3_key.
 */
export async function deleteOperation(apiBase, operationId, s3Key) {
  const res = await fetch(`${apiBase}/api/operations/${operationId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ s3_key: s3Key }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Ошибка удаления: HTTP ${res.status}${text ? ` — ${text}` : ""}`);
  }
  return res.json();
}