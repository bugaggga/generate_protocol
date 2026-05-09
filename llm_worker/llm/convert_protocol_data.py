import json

import re

def _extract_json(text: str) -> str:
    """
    Извлекает JSON из ответа модели, обрабатывая типичные случаи:
    - markdown-обёртки ```json ... ```
    - JSON зарытый в середине текста
    - лишние пробелы и переносы строк
    """
    if not text or not text.strip():
        raise ValueError("Model returned empty response")

    text = text.strip()

    # Убираем markdown-обёртки
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    # Пробуем распарсить напрямую
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Ищем первый JSON-объект в тексте
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        candidate = match.group(0)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in model response: {text[:200]!r}")


def json_to_markdown(response_json: str | dict) -> str:
    """
    Преобразует JSON-ответ модели в Markdown формат.

    Args:
        response_json: JSON строка или dict с ответом модели

    Returns:
        Отформатированная Markdown строка
    """
    data = {}
    # Парсим JSON, если передана строка
    if isinstance(response_json, str):
        data = json.loads(response_json)

    markdown_parts = ["# Протокол встречи\n"]

    # Заголовок документа

    # Обрабатываем каждый блок
    for block in data.get("blocks", []):
        block_id = block.get("id", "")
        title = block.get("title", "")
        content = block.get("content")

        # Добавляем заголовок блока
        markdown_parts.append(f"## {title}\n")

        # Форматируем контент в зависимости от типа
        if isinstance(content, str):
            # Простой текст
            if content.strip():
                markdown_parts.append(f"{content.strip()}\n")
            else:
                markdown_parts.append("_Информация отсутствует_\n")

        elif isinstance(content, list):
            if len(content) == 0:
                markdown_parts.append("_Информация отсутствует_\n")
            elif isinstance(content[0], dict):
                # Таблица (массив объектов)
                markdown_parts.append(_format_table(content))
            else:
                # Список строк
                markdown_parts.append(_format_list(content))

        elif isinstance(content, dict):
            # Поля (объект)
            formatted_fields = _format_fields(content)
            if formatted_fields.strip():
                markdown_parts.append(formatted_fields)
            else:
                markdown_parts.append("_Информация отсутствует_\n")
        else:
            markdown_parts.append("_Информация отсутствует_\n")

        markdown_parts.append("\n")

    return "\n".join(markdown_parts)


def _format_table(rows: list[dict]) -> str:
    """Форматирует массив объектов как Markdown таблицу."""
    if not rows:
        return "_Информация отсутствует_\n"

    # Получаем заголовки из первого объекта
    headers = list(rows[0].keys())

    # Формируем заголовок таблицы
    table_parts = []
    header_row = "| " + " | ".join(_escape_pipe(h) for h in headers) + " |"
    table_parts.append(header_row)

    # Разделитель
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    table_parts.append(separator)

    # Строки таблицы
    for row in rows:
        row_values = []
        for header in headers:
            value = row.get(header, "")
            # Преобразуем в строку и экранируем специальные символы
            value_str = str(value) if value is not None else ""
            row_values.append(_escape_pipe(value_str))

        table_parts.append("| " + " | ".join(row_values) + " |")

    return "\n".join(table_parts) + "\n"


def _format_list(items: list) -> str:
    """Форматирует список строк как Markdown маркированный список."""
    if not items:
        return "_Информация отсутствует_\n"

    list_parts = []
    for item in items:
        if item:  # Пропускаем пустые значения
            # Экранируем специальные символы Markdown
            item_str = str(item).strip()
            list_parts.append(f"- {item_str}")

    if not list_parts:
        return "_Информация отсутствует_\n"

    return "\n".join(list_parts) + "\n"


def _format_fields(fields: dict) -> str:
    """Форматирует объект с полями как список ключ-значение."""
    if not fields:
        return ""

    field_parts = []
    for key, value in fields.items():
        if value is not None and value != "" and value != [] and value != {}:
            # Форматируем ключ (заменяем underscore на пробелы и делаем первую букву заглавной)
            formatted_key = key.replace("_", " ").title()

            if isinstance(value, list):
                # Если значение - список, форматируем как вложенный список
                field_parts.append(f"**{formatted_key}**:")
                for item in value:
                    field_parts.append(f"  - {item}")
            elif isinstance(value, dict):
                # Если значение - объект, рекурсивно форматируем
                field_parts.append(f"**{formatted_key}**:")
                for sub_key, sub_value in value.items():
                    sub_formatted = sub_key.replace("_", " ").title()
                    field_parts.append(f"  - **{sub_formatted}**: {sub_value}")
            else:
                # Простое значение
                field_parts.append(f"**{formatted_key}**: {value}")

    return "\n".join(field_parts) + "\n" if field_parts else ""


def _escape_pipe(text: str) -> str:
    """Экранирует символ | в тексте для таблиц."""
    if not text:
        return ""
    return str(text).replace("|", "\\|")

