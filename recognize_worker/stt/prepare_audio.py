import subprocess
import os

def split_audio(input_file, output_dir, chunk_duration=30, overlap=5):
    os.makedirs(output_dir, exist_ok=True)

    # получаем длительность
    result = subprocess.run(
        ["ffprobe", "-i", input_file, "-show_entries", "format=duration",
         "-v", "quiet", "-of", "csv=p=0"],
        capture_output=True, text=True
    )
    total_duration = float(result.stdout.strip())

    chunks = []
    start = 0
    i = 0

    while start < total_duration:
        output_file = os.path.join(output_dir, f"chunk_{i}.wav")

        subprocess.run([
            "ffmpeg",
            "-y",
            "-i", input_file,
            "-ss", str(start),
            "-t", str(chunk_duration),
            output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        chunks.append((output_file, start))
        start += chunk_duration - overlap
        i += 1

    return chunks
