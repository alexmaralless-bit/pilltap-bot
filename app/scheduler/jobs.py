"""Задачи планировщика."""
import logging
from datetime import datetime
from aiogram import Bot

from app.db.session import async_session_maker
from app.services.reminder_service import ReminderService
from app.keyboards.inline import reminder_action_keyboard
from app.utils.datetime_utils import format_datetime, get_timezone

logger = logging.getLogger(__name__)


async def send_reminders_job(bot: Bot):
    """Задача для отправки напоминаний."""
    try:
        async with async_session_maker() as session:
            service = ReminderService(session)
            occurrences = await service.get_pending_occurrences(limit=100)
            
            for occurrence in occurrences:
                try:
                    reminder = occurrence.reminder
                    user = reminder.user
                    
                    text = (
                        f"⏰ **Пора принять:** {reminder.title}\n\n"
                        f"Время: {format_datetime(occurrence.planned_at, get_timezone())}"
                    )
                    
                    await bot.send_message(
                        chat_id=user.tg_id,
                        text=text,
                        reply_markup=reminder_action_keyboard(occurrence.id),
                        parse_mode="Markdown"
                    )
                    
                    logger.info(f"Отправлено напоминание {occurrence.id} пользователю {user.tg_id}")
                    
                except Exception as e:
                    logger.error(f"Ошибка при отправке напоминания {occurrence.id}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Ошибка в задаче отправки напоминаний: {e}")


async def restore_reminders(bot: Bot):
    """Восстановить активные напоминания после перезапуска."""
    try:
        from app.utils.datetime_utils import get_next_occurrence, now, get_timezone
        from sqlalchemy import select, and_
        from app.db.models import User, Reminder, ReminderOccurrence
        import json
        
        async with async_session_maker() as session:
            service = ReminderService(session)
            
            # Получаем всех пользователей
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            for user in users:
                reminders = await service.get_user_reminders(
                    user.id,
                    limit=1000,
                    active_only=True
                )
                
                for reminder in reminders:
                    if not reminder.is_active:
                        continue
                    
                    # Проверяем срок
                    if reminder.end_date:
                        tz = get_timezone()
                        current = now(tz)
                        if reminder.end_date < current:
                            reminder.is_active = False
                            await session.commit()
                            continue
                    
                    # Создаём следующее событие, если его нет
                    times = json.loads(reminder.times_json)
                    next_time = get_next_occurrence(times, reminder.start_date, get_timezone())
                    
                    if next_time:
                        # Проверяем, есть ли уже pending событие
                        existing_result = await session.execute(
                            select(ReminderOccurrence).where(
                                and_(
                                    ReminderOccurrence.reminder_id == reminder.id,
                                    ReminderOccurrence.status == "pending"
                                )
                            )
                        )
                        
                        if not existing_result.scalar_one_or_none():
                            # Создаём событие
                            occurrence = ReminderOccurrence(
                                reminder_id=reminder.id,
                                planned_at=next_time,
                                status="pending"
                            )
                            session.add(occurrence)
            
            await session.commit()
            logger.info("Напоминания восстановлены после перезапуска")
            
    except Exception as e:
        logger.error(f"Ошибка при восстановлении напоминаний: {e}")
