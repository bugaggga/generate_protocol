from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_ASYNC_URL",
    "postgresql+asyncpg://user:password@postgres:5432/stt_db"
)

engine = create_async_engine(DATABASE_URL,
                             echo=False,
                             pool_pre_ping=True,  # проверка живости соединения перед выдачей из пула
                             pool_recycle=300)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
