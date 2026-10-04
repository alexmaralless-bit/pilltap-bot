"""Обработчики колбэков."""
import json
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.services.reminder_service import ReminderService
from app.db.session import async_session_maker
from app.db.models import ReminderOccurrence
from app.keyboards.inline import (
    reminder_action_keyboard,
    postpone_options_keyboard
)
from app.utils.datetime_utils import get_timezone, now, add_days, format_datetime
from app.handlers.note_input import ReminderCreation, format_reminder_confirmation
from app.handlers.reminders import format_reminder_card

router = Router()


@router.callback_query(F.data == "confirm_reminder")
async def handle_confirm_reminder(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания напоминания."""
    await callback.answer()
    
    data = await state.get_data()
    
    if not data.get('title') or not data.get('times'):
        await callback.message.answer("❌ Ошибка: не все данные заполнены.")
        await state.clear()
        return
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        user = await service.get_or_create_user(callback.from_user.id)
        
        reminder = await service.create_reminder(
            user.id,
            data['title'],
            data['times'],
            start_date=None,  # Будет использовано текущее время
            end_date=data.get('end_date')
        )
        
        await callback.message.edit_text(
            f"✅ Напоминание создано!\n\n{format_reminder_card(reminder, short=False)}",
            parse_mode="Markdown"
        )
    
    await state.clear()


@router.callback_query(F.data == "edit_reminder")
async def handle_edit_reminder_from_confirmation(callback: CallbackQuery, state: FSMContext):
    """Редактирование напоминания из подтверждения."""
    await callback.answer()
    
    await callback.message.edit_text(
        "✏️ Что хотите изменить?\n\n"
        "1. Название - напишите новое название\n"
        "2. Времена - напишите новые времена\n"
        "3. Срок - напишите новый срок или 'бессрочно'"
    )
    
    # Переводим в режим ожидания ввода
    await state.set_state(ReminderCreation.waiting_confirmation.state)


@router.callback_query(F.data == "cancel_reminder")
async def handle_cancel_reminder(callback: CallbackQuery, state: FSMContext):
    """Отмена создания напоминания."""
    await callback.answer("Создание отменено")
    await callback.message.delete()
    await state.clear()


@router.callback_query(F.data.startswith("done_"))
async def handle_done_occurrence(callback: CallbackQuery):
    """Отметить событие как выполненное."""
    occurrence_id = int(callback.data.split("_")[1])
    await callback.answer("✅ Отмечено как выполненное")
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        occurrence = await service.mark_occurrence_done(occurrence_id)
        
        if occurrence:
            await callback.message.edit_text(
                f"✅ Приём {occurrence.reminder.title} отмечен как выполненный.\n\n"
                f"Следующее напоминание будет отправлено в назначенное время."
            )
        else:
            await callback.message.answer("❌ Событие не найдено.")


@router.callback_query(F.data.startswith("postpone_"))
async def handle_postpone(callback: CallbackQuery):
    """Обработка откладывания напоминания."""
    parts = callback.data.split("_")
    occurrence_id = int(parts[1])
    
    if len(parts) == 2:
        # Показать меню выбора времени
        await callback.answer()
        await callback.message.edit_reply_markup(
            reply_markup=postpone_options_keyboard(occurrence_id)
        )
        return
    
    # Обработка конкретного варианта откладывания
    option = parts[2]
    await callback.answer()
    
    tz = get_timezone()
    current = now(tz)
    
    if option == "10m":
        new_time = current + timedelta(minutes=10)
    elif option == "30m":
        new_time = current + timedelta(minutes=30)
    elif option == "1h":
        new_time = current + timedelta(hours=1)
    elif option == "2h":
        new_time = current + timedelta(hours=2)
    elif option == "tomorrow":
        tomorrow = add_days(current, 1, tz)
        # Берём первое время из напоминания
        async with async_session_maker() as session:
            result = await session.execute(
                select(ReminderOccurrence)
                .options(selectinload(ReminderOccurrence.reminder))
                .where(ReminderOccurrence.id == occurrence_id)
            )
            occurrence = result.scalar_one_or_none()
            if occurrence:
                times = json.loads(occurrence.reminder.times_json)
                first_time = times[0]
                hour, minute = map(int, first_time.split(":"))
                new_time = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                new_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        await callback.message.answer("❌ Неверный вариант откладывания.")
        return
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        occurrence = await service.postpone_occurrence(occurrence_id, new_time)
        
        if occurrence:
            await callback.message.edit_text(
                f"⏰ Напоминание отложено до {format_datetime(new_time, tz)}"
            )
        else:
            await callback.message.answer("❌ Событие не найдено.")


@router.callback_query(F.data.startswith("back_"))
async def handle_back_to_reminder(callback: CallbackQuery):
    """Вернуться к напоминанию."""
    occurrence_id = int(callback.data.split("_")[1])
    await callback.answer()
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(ReminderOccurrence)
            .options(selectinload(ReminderOccurrence.reminder))
            .where(ReminderOccurrence.id == occurrence_id)
        )
        occurrence = result.scalar_one_or_none()
        
        if occurrence:
            text = (
                f"⏰ Пора принять: **{occurrence.reminder.title}**\n\n"
                f"Время: {format_datetime(occurrence.planned_at, get_timezone())}"
            )
            await callback.message.edit_text(
                text,
                reply_markup=reminder_action_keyboard(occurrence_id),
                parse_mode="Markdown"
            )


@router.callback_query(F.data == "cancel_edit")
async def handle_cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования."""
    await callback.answer("Редактирование отменено")
    await state.clear()
    
    data = await state.get_data()
    if data.get('reminder_id'):
        from app.handlers.reminders import handle_view_reminder
        callback.data = f"view_reminder_{data['reminder_id']}"
        await handle_view_reminder(callback)
    else:
        await callback.message.delete()
