"""Точка входа в приложение."""
import asyncio
import logging
from app.db.session import init_db
from app.bot import main

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def startup_and_run():
    """Инициализация и запуск."""
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных инициализирована")
    
    await main()


if __name__ == "__main__":
    try:
        asyncio.run(startup_and_run())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
