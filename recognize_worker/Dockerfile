FROM python:3.11-slim

WORKDIR /worker

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY recognize_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple  \
    --timeout 100

COPY recognize_worker ./recognize_worker
COPY common ./common
COPY models ./models

CMD ["python", "-m", "recognize_worker.worker"]