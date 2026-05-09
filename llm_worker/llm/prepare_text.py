import logging
import re

SERVICE_NAME="[Merge]"

# ---------------------------------------------------------------------------
# Временно́й чанкинг (для видео — основной путь)
# ---------------------------------------------------------------------------

_TS_RE = re.compile(r'^\[(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\]\s*(.*)', re.MULTILINE)


def _parse_timestamp(mm: str, ss: str) -> float:
    """'01', '30' → 90.0"""
    return int(mm) * 60 + int(ss)


def parse_timed_transcript(transcript: str) -> list[tuple[float, float, str]]:
    """
    Парсит транскрипт с метками вида '[MM:SS-MM:SS] текст'.
    Возвращает список (start_sec, end_sec, text).
    """
    segments = []
    for m in _TS_RE.finditer(transcript):
        start = _parse_timestamp(m.group(1), m.group(2))
        end = _parse_timestamp(m.group(3), m.group(4))
        text = m.group(5).strip()
        if text:
            segments.append((start, end, text))
    return segments

def _split_segments_by_chars(
        segments: list[tuple[float, float, str]],
        chunk_size: int,
        overlap: int,
) -> list[list[tuple[float, float, str]]]:
    """
    Разбивает список сегментов на группы по числу символов текста,
    не разрывая сегменты на границах чанков.

    Overlap формируется из хвостовых сегментов предыдущей группы:
    первый сегмент добавляется всегда (гарантия хотя бы одного перекрытия),
    следующие — пока суммарный размер не превысит overlap.
    """
    segment_chunks: list[list[tuple[float, float, str]]] = []
    current: list[tuple[float, float, str]] = []
    current_chars = 0

    for seg in segments:
        _, _, text = seg
        seg_chars = len(text)

        if current and current_chars + seg_chars > chunk_size:
            segment_chunks.append(current)

            overlap_segs: list[tuple[float, float, str]] = []
            overlap_chars = 0
            for prev in reversed(current):
                prev_chars = len(prev[2])
                if not overlap_segs or overlap_chars < overlap:
                    overlap_segs.insert(0, prev)
                    overlap_chars += prev_chars
                else:
                    break

            current = overlap_segs
            current_chars = overlap_chars

        current.append(seg)
        current_chars += seg_chars

    if current:
        segment_chunks.append(current)

    return segment_chunks

def chunk_by_chars(
        transcript: str,
        frames_meta: list[dict],
        chunk_size: int = 3000,
        overlap: int = 500,
        max_frames_per_chunk: int = 5,
) -> list[tuple[str, list[dict]]]:
    """
    Разбивает транскрипт на чанки по числу символов, не разрывая сегменты.

    Граница чанка всегда совпадает с границей сегмента: если добавление
    очередного сегмента превысит chunk_size, он уходит в следующий чанк.
    Overlap формируется из хвостовых сегментов предыдущего чанка —
    берём сегменты с конца пока сумма их символов не превысит overlap.

    Фреймы привязываются по времени: временна́я метка фрейма должна
    попасть в диапазон [start первого сегмента чанка, end последнего].
    """
    segments = parse_timed_transcript(transcript)

    if not segments:
        logging.warning(f"{SERVICE_NAME} No timestamps found, single chunk fallback")
        return [(transcript, frames_meta[:max_frames_per_chunk])]

    segment_chunks = _split_segments_by_chars(segments, chunk_size, overlap)

    # --- 2. Строим результат: текст чанка + фреймы по времени ---
    result: list[tuple[str, list[dict]]] = []
    for seg_chunk in segment_chunks:
        t_start = seg_chunk[0][0]  # start первого сегмента
        t_end = seg_chunk[-1][1]  # end последнего сегмента

        lines = [
            #f"[{_fmt_ts(s)}-{_fmt_ts(e)}] {t}"
            f"{t}"
            for _, _, t in seg_chunk
        ]
        text_chunk = "\n".join(lines)

        chunk_frames = [
                           f for f in frames_meta
                           if t_start <= f["timestamp_sec"] <= t_end
                       ][:max_frames_per_chunk]

        logging.info(f"chunk_frames count: len{chunk_frames}; {SERVICE_NAME} Chunk text: {text_chunk}")
        result.append((text_chunk, chunk_frames))

    total_chars = sum(len(s[2]) for s in segments)
    logging.info(
        f"{SERVICE_NAME} char-based split: {len(result)} chunks "
        f"(chunk_size={chunk_size}, overlap={overlap}, "
        f"total_chars={total_chars})"
    )
    return result

def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Символьный чанкинг (fallback для аудио без кадров)
# ---------------------------------------------------------------------------

def chunk_text(transcript: str, chunk_size: int = 3000, overlap: int = 500) -> list[str]:
    """
        Разбивает транскрипт на чанки по числу символов, не разрывая сегменты.
        Используется для аудио (без фреймов) — возвращает список строк.
        """
    segments = parse_timed_transcript(transcript)

    if not segments:
        logging.warning(f"{SERVICE_NAME} No timestamps found, single chunk fallback")
        return [transcript]

    segment_chunks = _split_segments_by_chars(segments, chunk_size, overlap)

    result = []
    for seg_chunk in segment_chunks:
        result.append("\n".join(
            f"{t}" for _, _, t in seg_chunk
        ))

    total_chars = sum(len(s[2]) for s in segments)
    logging.info(
        f"{SERVICE_NAME} chunk_text: {len(result)} chunks "
        f"(chunk_size={chunk_size}, overlap={overlap}, total_chars={total_chars})"
    )
    return result



#-------------------------------
# Объединение Результатов
#-------------------------------

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
            if len(group) < 2:
                next_level.extend(group)
                continue
            merged = merge_fn(group)  # ← вызов LLM
            next_level.append(merged)

        current_level = next_level

    return current_level[0]