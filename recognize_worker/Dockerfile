FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ffmpeg \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/* \

WORKDIR /worker

COPY recognize_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt  \
    --timeout 100

COPY recognize_worker ./recognize_worker
COPY common ./common

CMD ["python", "-m", "recognize_worker.worker"]