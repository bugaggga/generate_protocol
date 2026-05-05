FROM python:3.11-slim

WORKDIR /worker

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY stt_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple  \
    --timeout 100

COPY stt_worker ./stt_worker
COPY common ./common
COPY models ./models

CMD ["python", "-m", "stt_worker.worker"]