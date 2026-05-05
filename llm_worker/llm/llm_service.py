import requests
import logging

from common.core.db_service import is_cancelled, is_version_active
from llm_worker.llm.convert_protocol_data import json_to_markdown
from llm_worker.llm.prepare_text import chunk_text, hierarchical_merge

OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
MODEL = "qwen2.5:3b"
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

def call_llm(prompt: str):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=1200
    )

    data = response.json()
    return data["response"]

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
    6. Поле "content" должно строго соответствовать указанному типу. Не добавляй лишние ключи, в том числе вложенные внутрь content. Например: Блок, содержащий обычный текст, должен располагаться прямо по ключу content, не выделяй его в отдельный ключ.
    7. Если информация для блока отсутствует в транскрипции, используй пустые значения: "" (строка), [] (массив) или {{}} (объект). Не выдумывай данные.
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
            block_structure = f'Обычная строка.\n'

        blocks_prompt += f"Структура: {block_structure}\n"

    return blocks_prompt

class VersionOutdatedError(Exception):
    """Версия операции устарела — штатная остановка."""

def build_protocol(transcript, form: dict, operation_id: str = None, version=None, loop=None):
    import asyncio
    chunks = chunk_text(transcript)
    summaries = []

    for i, chunk in enumerate(chunks):
        # Чекпоинт между каждым чанком
        if operation_id and version is not None and loop is not None:
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
                    f"v{version} outdated at chunk {i}/{len(chunks)}"
                )

        logging.info(f"{SERVICE_NAME} Processing chunk {i + 1}/{len(chunks)}")
        prompt = build_prompt(form, chunk)
        summary = build_with_retries(call_llm, prompt)
        summaries.append(summary)

    logging.info(f"{SERVICE_NAME} Start merging parts")
    merging_protocol = hierarchical_merge(summaries=summaries, merge_fn=merge_fn)
    md_protocol = json_to_markdown(merging_protocol)
    return merging_protocol, md_protocol

def build_with_retries(callback, prompt: str):
    for attempt in range(1, 4):
        try:
            logging.info(f"{SERVICE_NAME} Attempt {attempt}/{3}")

            summary = callback(prompt)
            return  summary # успех

        except Exception:
            logging.exception(f"{SERVICE_NAME} Attempt {attempt} failed")

            if attempt == 3:
                raise