import requests
import logging

from llm_worker.llm.prepare_text import chunk_text, hierarchical_merge

OLLAMA_URL = "http://ollama:11434/api/generate"
MODEL = "qwen2.5:7b"
SERVICE_NAME="[Build]"

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
Сформируй единый протокол на основе следующих частей.

Требования:
- убрать дубли
- объединить темы
- структурировать

Текст:
{separator.join(summaries_group)}
"""
    return call_llm(prompt)

def generate_summary(transcript: str) -> str:
    prompt = f"""
Ты — система составления протоколов встреч.

Сформируй структурированный протокол по тексту:

Требования:
- Краткое содержание
- Основные темы
- Принятые решения
- Вопросы и ответы на них (если есть)
- Участники (если можно определить)

Текст:
{transcript}
"""

    return call_llm(prompt)

def build_protocol(transcript):
    chunks = chunk_text(transcript)

    summaries = []

    for chunk in chunks:
        logging.info(f"{SERVICE_NAME} Start summary for next chunk")
        summary = generate_summary(chunk)
        summaries.append(summary)

    final_protocol = hierarchical_merge(
        summaries=summaries,
        merge_fn=merge_fn
    )

    return final_protocol