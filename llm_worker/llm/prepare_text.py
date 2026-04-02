import logging

SERVICE_NAME="[Merge]"

def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 800) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size

        if end < text_length:
            # ищем ближайший пробел назад
            end = text.rfind(" ", start, end)
            if end == -1:
                end = start + chunk_size  # fallback

        chunk = text[start:end]
        chunks.append(chunk)

        start = end - overlap
        if start < 0:
            start = 0

    return chunks

def group_items(items: list[str], group_size: int) -> list[list[str]]:
    """Разбивает список на группы фиксированного размера"""
    return [items[i:i + group_size] for i in range(0, len(items), group_size)]


def hierarchical_merge(
    summaries: list[str],
    merge_fn,
    group_size: int = 3,
    max_iterations: int = 5,
) -> str:
    """
    Многоуровневое объединение summaries

    :param summaries: список частичных суммаризаций
    :param merge_fn: функция вызова LLM (принимает список текстов → возвращает текст)
    :param group_size: сколько summaries объединять за раз
    :param max_iterations: защита от бесконечного цикла
    :return: финальный протокол
    """

    current_level = summaries
    iteration = 0

    while len(current_level) > 1:
        iteration += 1

        if iteration > max_iterations:
            raise RuntimeError("Too many merge iterations")

        logging.info(f"{SERVICE_NAME} Level {iteration}, items: {len(current_level)}")

        grouped = group_items(current_level, group_size)

        next_level = []

        for group in grouped:
            merged = merge_fn(group)  # ← вызов LLM
            next_level.append(merged)

        current_level = next_level

    return current_level[0]