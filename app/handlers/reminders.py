"""Обработчики для управления напоминаниями."""
import json
from typing import List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.services.reminder_service import ReminderService
from app.db.session import async_session_maker
from app.keyboards.inline import (
    reminders_list_keyboard,
    reminder_card_keyboard,
    edit_reminder_field_keyboard,
    cancel_edit_keyboard
)
from app.keyboards.reply import main_menu_keyboard
from app.utils.datetime_utils import format_datetime, format_date, get_timezone
from app.handlers.note_input import ReminderCreation

router = Router()

ITEMS_PER_PAGE = 5


async def show_reminders_list(message: Message, page: int = 0):
    """Показать список напоминаний с пагинацией."""
    if page < 0:
        page = 0
    async with async_session_maker() as session:
        service = ReminderService(session)
        user = await service.get_or_create_user(message.from_user.id)
        
        reminders = await service.get_user_reminders(
            user.id,
            limit=ITEMS_PER_PAGE,
            offset=page * ITEMS_PER_PAGE,
            active_only=False
        )
        
        total_count = await service.count_user_reminders(user.id, active_only=False)
        total_pages = (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_count > 0 else 1
        
        if not reminders:
            await message.answer(
                "📋 У вас пока нет напоминаний.\n\n"
                "Напишите напоминание, например:\n"
                "`Аспирин в 12:30`",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
            return
        
        text = f"📋 **Ваши напоминания** (страница {page + 1}/{total_pages}):\n\n"
        
        reminder_ids = []
        for reminder in reminders:
            reminder_ids.append(reminder.id)
            text += format_reminder_card(reminder, short=True) + "\n\n"
        
        await message.answer(
            text,
            reply_markup=reminders_list_keyboard(page, total_pages, reminder_ids),
            parse_mode="Markdown"
        )


def format_reminder_card(reminder, short: bool = False) -> str:
    """Форматирует карточку напоминания."""
    tz = get_timezone()
    times = json.loads(reminder.times_json)
    
    status_emoji = "✅" if reminder.is_active else "⏸"
    text = f"{status_emoji} **{reminder.title}**\n"
    
    if not short:
        text += f"🕐 Времена: {', '.join(times)}\n"
        text += f"📅 Начало: {format_date(reminder.start_date, tz)}\n"
        
        if reminder.end_date:
            text += f"📆 Окончание: {format_date(reminder.end_date, tz)}\n"
        else:
            text += "📆 Срок: Бессрочно\n"
        
        # Находим следующее срабатывание
        from app.utils.datetime_utils import get_next_occurrence
        next_occ = get_next_occurrence(times, reminder.start_date, tz)
        if next_occ:
            text += f"⏰ Следующее: {format_datetime(next_occ, tz)}\n"
    else:
        text += f"🕐 {', '.join(times)}"
        if reminder.end_date:
            text += f" | До {format_date(reminder.end_date, tz)}"
    
    return text


@router.callback_query(F.data.startswith("page_"))
async def handle_page_navigation(callback: CallbackQuery):
    """Обработка навигации по страницам."""
    page = int(callback.data.split("_")[1])
    await callback.answer()
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        user = await service.get_or_create_user(callback.from_user.id)
        
        reminders = await service.get_user_reminders(
            user.id,
            limit=ITEMS_PER_PAGE,
            offset=page * ITEMS_PER_PAGE,
            active_only=False
        )
        
        total_count = await service.count_user_reminders(user.id, active_only=False)
        total_pages = (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_count > 0 else 1
        
        if not reminders:
            await callback.message.edit_text(
                "📋 На этой странице нет напоминаний.",
                reply_markup=reminders_list_keyboard(page, total_pages, [])
            )
            return
        
        text = f"📋 **Ваши напоминания** (страница {page + 1}/{total_pages}):\n\n"
        
        reminder_ids = []
        for reminder in reminders:
            reminder_ids.append(reminder.id)
            text += format_reminder_card(reminder, short=True) + "\n\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=reminders_list_keyboard(page, total_pages, reminder_ids),
            parse_mode="Markdown"
        )


@router.callback_query(F.data.startswith("view_reminder_"))
async def handle_view_reminder(callback: CallbackQuery):
    """Просмотр деталей напоминания."""
    reminder_id = int(callback.data.split("_")[2])
    await callback.answer()
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        user = await service.get_or_create_user(callback.from_user.id)
        reminder = await service.get_reminder(reminder_id, user.id)
        
        if not reminder:
            await callback.message.answer("❌ Напоминание не найдено.")
            return
        
        text = format_reminder_card(reminder, short=False)
        
        await callback.message.edit_text(
            text,
            reply_markup=reminder_card_keyboard(reminder.id, reminder.is_active),
            parse_mode="Markdown"
        )


@router.callback_query(F.data.startswith("edit_reminder_"))
async def handle_edit_reminder(callback: CallbackQuery):
    """Начать редактирование напоминания."""
    reminder_id = int(callback.data.split("_")[2])
    await callback.answer()
    
    await callback.message.edit_text(
        "✏️ Выберите поле для редактирования:",
        reply_markup=edit_reminder_field_keyboard(reminder_id)
    )


@router.callback_query(F.data.startswith("edit_field_"))
async def handle_edit_field(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора поля для редактирования."""
    parts = callback.data.split("_")
    reminder_id = int(parts[2])
    field = parts[3]
    
    await callback.answer()
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        user = await service.get_or_create_user(callback.from_user.id)
        reminder = await service.get_reminder(reminder_id, user.id)
        
        if not reminder:
            await callback.message.answer("❌ Напоминание не найдено.")
            return
        
        if field == "title":
            await callback.message.edit_text(
                "✏️ Введите новое название лекарства:",
                reply_markup=cancel_edit_keyboard()
            )
            await state.set_state(ReminderCreation.editing_title.state)
            await state.update_data(reminder_id=reminder_id, editing_field="title")
        elif field == "times":
            await callback.message.edit_text(
                "✏️ Введите новые времена приёма:\n"
                "Например: `12:30, 20:00` или `утро, вечер`",
                reply_markup=cancel_edit_keyboard(),
                parse_mode="Markdown"
            )
            await state.set_state(ReminderCreation.editing_times.state)
            await state.update_data(reminder_id=reminder_id, editing_field="times")
        elif field == "end_date":
            await callback.message.edit_text(
                "✏️ Введите новый срок:\n"
                "Например: `на 3 дня`, `до пятницы`, `бессрочно`",
                reply_markup=cancel_edit_keyboard(),
                parse_mode="Markdown"
            )
            await state.set_state(ReminderCreation.editing_end_date.state)
            await state.update_data(reminder_id=reminder_id, editing_field="end_date")


@router.callback_query(F.data.startswith("toggle_"))
async def handle_toggle_reminder(callback: CallbackQuery):
    """Переключить активность напоминания."""
    reminder_id = int(callback.data.split("_")[1])
    await callback.answer()
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        user = await service.get_or_create_user(callback.from_user.id)
        reminder = await service.toggle_reminder_active(reminder_id, user.id)
        
        if not reminder:
            await callback.message.answer("❌ Напоминание не найдено.")
            return
        
        status = "активировано" if reminder.is_active else "приостановлено"
        await callback.message.answer(f"✅ Напоминание {status}.")
        
        # Обновляем карточку
        text = format_reminder_card(reminder, short=False)
        await callback.message.edit_text(
            text,
            reply_markup=reminder_card_keyboard(reminder.id, reminder.is_active),
            parse_mode="Markdown"
        )


@router.callback_query(F.data.startswith("delete_"))
async def handle_delete_reminder(callback: CallbackQuery):
    """Удалить напоминание."""
    reminder_id = int(callback.data.split("_")[1])
    await callback.answer()
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        user = await service.get_or_create_user(callback.from_user.id)
        deleted = await service.delete_reminder(reminder_id, user.id)
        
        if deleted:
            await callback.message.answer("✅ Напоминание удалено.")
            await callback.message.delete()
        else:
            await callback.message.answer("❌ Напоминание не найдено.")
