FROM python:3.11-slim

WORKDIR /worker

COPY llm_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple  \
    --timeout 100

COPY llm_worker ./llm_worker
COPY common ./common

CMD ["python", "-m", "llm_worker.worker"]