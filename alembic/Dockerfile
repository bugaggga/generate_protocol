FROM python:3.11-slim

WORKDIR /alembic

COPY alembic ./alembic
COPY alembic.ini .

RUN pip install --upgrade pip setuptools wheel

RUN pip install --default-timeout=120 --no-cache-dir -r alembic/requirements.txt

COPY common ./common