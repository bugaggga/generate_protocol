import time
import psycopg2
import os

DB_URL = os.getenv("DATABASE_URL_SYNC", "postgresql://user:password@postgres:5432/stt_db")

while True:
    try:
        conn = psycopg2.connect(DB_URL)
        conn.close()
        print("Postgres is ready")
        break
    except Exception:
        print("Waiting for Postgres...")
        time.sleep(2)