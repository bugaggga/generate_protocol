from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.routes import router

# Базовая настройка логирования
logging.basicConfig(
    level=logging.INFO
)

app = FastAPI(
    title="STT Protocol Service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # разрешить все origin
    allow_credentials=True,
    allow_methods=["*"],        # все методы (GET, POST и т.д.)
    allow_headers=["*"],        # все заголовки
)

app.include_router(router)