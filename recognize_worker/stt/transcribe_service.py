def transcribe_chunks(model, chunks, params):
    results = []

    for chunk_file, start_time in chunks:
        result = model.transcribe(chunk_file, **params)

        for segment in result["segments"]:
            segment["start"] += start_time
            segment["end"] += start_time

        results.extend(result["segments"])

    return results

def find_overlap(a, b, min_overlap=10):
    """
    Ищет максимальное пересечение конца строки a
    и начала строки b
    """
    max_len = min(len(a), len(b))

    for i in range(max_len, min_overlap, -1):
        if a[-i:] == b[:i]:
            return i
    return 0


def merge_two(a, b):
    overlap_len = find_overlap(a, b)
    return a + b[overlap_len:]


def merge_texts(texts):
    result = texts[0]["text"]

    for t in texts[1:]:
        result = merge_two(result, t["text"])

    return result

def merge_segments(segments):
    segments = sorted(segments, key=lambda x: x["start"])
    #remove_duplicates(segments, threshold=1.0)
    #text = " ".join([s["text"].strip() for s in segments])
    text = merge_texts(segments)
    return text