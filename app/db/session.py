"""Управление сессиями базы данных."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import DATABASE_URL
from app.db.models import Base

# Создаём асинхронный движок
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# Создаём фабрику сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Инициализация базы данных (создание таблиц)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Получить сессию БД."""
    async with async_session_maker() as session:
        yield session
