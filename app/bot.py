"""Инициализация бота и диспетчера."""
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import BOT_TOKEN
from app.handlers import start, note_input, reminders, callbacks
from app.scheduler.apscheduler_setup import scheduler, start_scheduler
from app.scheduler.jobs import send_reminders_job, restore_reminders

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def register_handlers():
    """Регистрация обработчиков."""
    dp.include_router(start.router)
    dp.include_router(note_input.router)
    dp.include_router(reminders.router)
    dp.include_router(callbacks.router)


async def setup_scheduler():
    """Настройка планировщика."""
    await start_scheduler()
    
    # Восстанавливаем напоминания
    await restore_reminders(bot)
    
    # Добавляем периодическую задачу проверки напоминаний (каждую минуту)
    scheduler.add_job(
        send_reminders_job,
        'interval',
        minutes=1,
        args=[bot],
        id='send_reminders',
        replace_existing=True
    )
    
    logger.info("Планировщик настроен")


async def on_startup():
    """Действия при запуске бота."""
    logger.info("Бот запускается...")
    await setup_scheduler()


async def on_shutdown():
    """Действия при остановке бота."""
    logger.info("Бот останавливается...")
    from app.scheduler.apscheduler_setup import shutdown_scheduler
    await shutdown_scheduler()


async def main():
    """Главная функция для запуска бота."""
    register_handlers()
    
    try:
        await on_startup()
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown()
        await bot.session.close()
