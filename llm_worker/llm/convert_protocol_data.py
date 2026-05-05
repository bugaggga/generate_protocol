import json


def json_to_markdown(response_json: str | dict) -> str:
    """
    Преобразует JSON-ответ модели в Markdown формат.

    Args:
        response_json: JSON строка или dict с ответом модели

    Returns:
        Отформатированная Markdown строка
    """
    # Парсим JSON, если передана строка
    if isinstance(response_json, str):
        # Очищаем от markdown-обёрток, если они есть
        response_json = response_json.strip()
        if response_json.startswith("```json"):
            response_json = response_json[7:]
        if response_json.startswith("```"):
            response_json = response_json[3:]
        if response_json.endswith("```"):
            response_json = response_json[:-3]

        data = json.loads(response_json.strip())
    else:
        data = response_json

    markdown_parts = []

    # Заголовок документа
    markdown_parts.append("# Протокол встречи\n")

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






'''def save_markdown_to_file(markdown_text: str, path: str) -> None:
    """Сохраняет Markdown текст в файл."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown_text)


# Пример использования
if __name__ == "__main__":
    # Пример ответа модели
    example_response = {
        "blocks": [
            {
                "id": "participants",
                "title": "Участники встречи",
                "content": {
                    "Модератор": "Иванов Иван",
                    "Участники": ["Петров Петр", "Сидорова Анна"]
                }
            },
            {
                "id": "agenda",
                "title": "Повестка дня",
                "content": [
                    "Открытие встречи",
                    "Обсуждение бюджета",
                    "Планирование следующего квартала"
                ]
            },
            {
                "id": "decisions",
                "title": "Принятые решения",
                "content": [
                    {"Решение": "Утвердить бюджет", "Ответственный": "Иванов", "Крайний срок": "2024-05-01"},
                    {"Решение": "Подготовить отчёт", "Ответственный": "Петров", "Крайний срок": "2024-04-25"}
                ]
            },
            {
                "id": "summary",
                "title": "Итоги встречи",
                "content": "Встреча прошла продуктивно, все вопросы обсуждены."
            }
        ]
    }

    # Преобразуем в Markdown
    markdown = json_to_markdown(example_response)
    print(markdown)

    # Сохраняем в файл
    save_markdown_to_file(markdown, "C:/Generate_protocol/tmp_data/test_protocol.md")'''