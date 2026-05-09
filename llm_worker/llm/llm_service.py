import requests
import logging
import os

from common.core.db_service import is_version_active
from llm_worker.llm.convert_protocol_data import json_to_markdown, _extract_json
from llm_worker.llm.prepare_text import chunk_text, hierarchical_merge, chunk_by_chars

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_ENDPOINT = f"{OLLAMA_HOST}/api/generate"
MODEL = "qwen2.5vl:3b"
SERVICE_NAME="[Build]"
RESPONSE_STRUCT = """
{
    "blocks": [
      {
        "id": "идентификатор_блока",
        "title": "название_блока",
        "content": <данные_согласно_описанной_структуре>
      },
      ...
    ]
}
"""

def call_llm(prompt: str, images: list[str] | None = None):
    """
        Вызывает Ollama.
        images — список base64-строк (jpg). При None модель работает
        как обычная текстовая LLM, без изменения API.
        """
    payload: dict = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 4096
        }
    }
    if images:
        payload["images"] = images

    response = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=1200)

    data = response.json()

    if "error" in data:
        logging.error(f"{SERVICE_NAME} error: {data['error']}")
        raise RuntimeError(f"Ollama error: {data['error']}")

    if "response" not in data:
        logging.error(f"{SERVICE_NAME} Unexpected Ollama response: {data}")
        raise RuntimeError(f"Ollama returned no 'response' field: {data}")

    return data["response"]


# ---------------------------------------------------------------------------
# Промпты
# ---------------------------------------------------------------------------
def merge_fn(summaries_group: list[str]) -> str:
    separator = "\n\n---\n\n"
    prompt = f"""
Ты — автоматизированная система генерации протоколов совещаний.
    Твоя задача: проанализировать уже подготовленные блоки протокола и объединить их.
    Убери дубли. Не добавляй новых блоков, обновляй уже существующие.
    Верни результат СТРОГО в формате JSON. Запрещено использовать markdown-обёртки (```json), пояснения или любой текст вне JSON.

ТРЕБУЕМАЯ СТРУКТУРА ОТВЕТА:
{RESPONSE_STRUCT}

Правила составления ответа:
    1. Итоговый Массив "blocks" должен содержать все блоки. которые есть в исходных блоках.
    1. Массив "blocks" НЕ должен содержать блоки, идентификаторов которых нет в исходных блоках.
    2. Поле "content" должно строго соответствовать указанному типу. Не добавляй лишние ключи.
    3. Если информация для блока отсутствует в исходных блоках, используй пустые значения: "" (строка), [] (массив) или {{}} (объект). Не выдумывай данные.
    4. Сохраняй исходную нумерацию и формулировки title из формы.

На выходе должен получиться протокол в виде JSON с такой же структурой, как исходные блоки

Блоки:
{separator.join(summaries_group)}

JSON-Ответ:
"""
    return call_llm(prompt)

def build_prompt(form: dict, transcript: str) -> str:
    blocks_prompt = create_form_for_prompt(form)

    return f"""
Ты — автоматизированная система генерации протоколов совещаний.
Твоя задача: проанализировать транскрипцию встречи и заполнить поля заданной формы.
Верни результат СТРОГО в формате JSON. Запрещено использовать markdown-обёртки (```json), пояснения или любой текст вне JSON.

ТРЕБУЕМАЯ СТРУКТУРА ОТВЕТА:
{RESPONSE_STRUCT}

ПРАВИЛА ЗАПОЛНЕНИЯ:
    1. Имена ВСЕХ ключей в JSON (включая вложенные поля внутри "content") должны В ТОЧНОСТИ совпадать с теми, что указаны в форме.
    2. СТРОГО ЗАПРЕЩЕНО: переводить ключи на английский, менять регистр, сокращать или дополнять их.
    3. Пример: если в форме ключ "ответственный", в ответе должно быть "ответственный": "...", а НЕ "responsible".
    4. Перед выводом сверь каждый ключ с исходной формой.
    
    5. Массив "blocks" должен содержать все блоки из формы в порядке их следования.
    6. Поле "content" должно строго соответствовать указанному для блока виду. Не добавляй лишние ключи, в том числе вложенные внутрь content. Например: Блок, содержащий обычный текст, должен располагаться прямо по ключу content, не выделяй его в отдельный ключ.
    7. Если информация для блока отсутствует в транскрипции, используй пустые значения: "" (строка), [] (массив) или {{}} (объект). Не выдумывай данные.
    8. Если к транскрипции приложены изображения — дополняй из них визуальную информацию (слайды, таблицы, схемы, текст), если есть данные для протокола.
    8. Сохраняй исходную нумерацию и формулировки title из формы.

ФОРМА ПРОТОКОЛА:
    {blocks_prompt}

ТРАНСКРИПЦИЯ:
    {transcript}

JSON-ОТВЕТ:"""

def create_form_for_prompt(form: dict):
    blocks_prompt = "Блоки:\n"
    for block in sorted(form["blocks"], key=lambda b: b["order"]):
        blocks_prompt += f'\n### id : {block["id"]} | title: {block["title"]}\n'
        if len(block["llm_instruction"]) > 0: blocks_prompt += f'Инструкция: {block["llm_instruction"]}\n'
        if block["type"] == "table":
            cols = ", ".join(c["key"] for c in block["columns"])
            block_structure = f'Массив объектов с ключами: {cols}\n'
        elif block["type"] == "list":
            block_structure = 'Массив строк.\n'
        elif block["type"] == "fields":
            fields = ", ".join(f["key"] for f in block["fields"])
            block_structure = f'Объект с ключами: {fields}\n'
        else:
            block_structure = f'Строка.\n'

        blocks_prompt += f"Вид: {block_structure}\n"

    return blocks_prompt

class VersionOutdatedError(Exception):
    """Версия операции устарела — штатная остановка."""

def build_protocol(
        transcript,
        form: dict,
        frames_meta: list[dict] | None = None,
        operation_id: str = None,
        version=None,
        loop=None):
    """
        Строит протокол встречи.

        frames_meta — список {"path": str, "timestamp_sec": float}.
        При наличии кадров использует временно́й чанкинг и передаёт
        изображения в модель вместе с текстом.
        При отсутствии — обычный символьный чанкинг (аудио-режим).
        """
    # Выбираем стратегию чанкинга
    if frames_meta:
        raw_chunks = chunk_by_chars(transcript, frames_meta)
        # raw_chunks: list[(text, [frame_path, ...])]
    else:
        raw_chunks = [(chunk, []) for chunk in chunk_text(transcript)]

    summaries = []
    for i, (text_chunk, frame_dicts) in enumerate(raw_chunks):
        # Чекпоинт между каждым чанком
        if operation_id and version is not None and loop is not None:
            import asyncio
            future = asyncio.run_coroutine_threadsafe(
                is_version_active(operation_id, version),
                loop
            )
            try:
                still_active = future.result(timeout=10)
            except TimeoutError:
                logging.warning(f"{SERVICE_NAME} Version check timed out, continuing")
                still_active = True  # при таймауте не прерываем

            if not still_active:
                raise VersionOutdatedError(
                    f"v{version} outdated at chunk {i}/{len(raw_chunks)}"
                )

        images_b64 = [frame_dict["b64"] for frame_dict in frame_dicts] if frame_dicts else None
        frame_info = f" + {len(images_b64)} frames" if images_b64 else ""
        logging.info(f"{SERVICE_NAME} Chunk {i + 1}/{len(raw_chunks)}{frame_info}")

        prompt = build_prompt(form, text_chunk)
        summary = build_with_retries(call_llm, prompt, images_b64)
        logging.info(f"{SERVICE_NAME} Chunk {i + 1} Result:  {summary}")
        summaries.append(summary)

    logging.info(f"{SERVICE_NAME} Start merging parts")
    raw_protocol = hierarchical_merge(summaries=summaries, merge_fn=merge_fn)
    clean_protocol = _extract_json(raw_protocol)  # единственная точка очистки
    md_protocol = json_to_markdown(clean_protocol)
    return clean_protocol, md_protocol

def build_with_retries(
        callback,
        prompt: str,
        images: list[str] | None = None,
        max_attempts: int = 3,):
    for attempt in range(1, max_attempts + 1):
        try:
            logging.info(f"{SERVICE_NAME} LLM attempt {attempt}/{max_attempts}")
            return callback(prompt, images)
        except Exception:
            logging.exception(f"{SERVICE_NAME} Attempt {attempt} failed")
            if attempt == max_attempts:
                raise