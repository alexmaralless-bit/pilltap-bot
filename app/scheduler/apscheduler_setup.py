"""Настройка APScheduler."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

logger = logging.getLogger(__name__)

# Настройка планировщика
jobstores = {
    'default': MemoryJobStore()
}

executors = {
    'default': AsyncIOExecutor()
}

job_defaults = {
    'coalesce': True,  # Объединять пропущенные задачи
    'max_instances': 1,  # Только один экземпляр задачи
    'misfire_grace_time': 300  # 5 минут на выполнение пропущенных задач
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults,
    timezone='Europe/Moscow'
)


async def start_scheduler():
    """Запустить планировщик."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Планировщик запущен")


async def shutdown_scheduler():
    """Остановить планировщик."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Планировщик остановлен")
