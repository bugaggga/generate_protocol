FROM python:3.11-slim

WORKDIR /worker

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY recognize_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt  \
    --timeout 100

COPY recognize_worker ./recognize_worker
COPY common ./common

CMD ["python", "-m", "recognize_worker.worker"]