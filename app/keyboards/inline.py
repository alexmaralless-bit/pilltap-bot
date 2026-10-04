"""Inline-клавиатуры для бота."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional
from datetime import datetime


def confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения создания напоминания."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_reminder"),
            InlineKeyboardButton(text="✏️ Исправить", callback_data="edit_reminder"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reminder"),
        ]
    ])


def reminder_action_keyboard(occurrence_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с напоминанием (выполнено/отложить)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done_{occurrence_id}"),
            InlineKeyboardButton(text="⏰ Отложить", callback_data=f"postpone_{occurrence_id}"),
        ]
    ])


def postpone_options_keyboard(occurrence_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора времени откладывания."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="10 мин", callback_data=f"postpone_{occurrence_id}_10m"),
            InlineKeyboardButton(text="30 мин", callback_data=f"postpone_{occurrence_id}_30m"),
        ],
        [
            InlineKeyboardButton(text="1 час", callback_data=f"postpone_{occurrence_id}_1h"),
            InlineKeyboardButton(text="2 часа", callback_data=f"postpone_{occurrence_id}_2h"),
        ],
        [
            InlineKeyboardButton(text="Завтра", callback_data=f"postpone_{occurrence_id}_tomorrow"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_{occurrence_id}"),
        ]
    ])


def reminder_card_keyboard(reminder_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Клавиатура для карточки напоминания."""
    buttons = [
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_reminder_{reminder_id}"),
        ],
        [
            InlineKeyboardButton(
                text="⏸ Пауза" if is_active else "▶️ Продолжить",
                callback_data=f"toggle_{reminder_id}"
            ),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{reminder_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def reminders_list_keyboard(
    page: int,
    total_pages: int,
    reminder_ids: List[int]
) -> InlineKeyboardMarkup:
    """Клавиатура для списка напоминаний с пагинацией."""
    buttons = []
    
    # Кнопки напоминаний на текущей странице
    for i, rem_id in enumerate(reminder_ids, start=1):
        buttons.append([
            InlineKeyboardButton(
                text=f"📋 Напоминание {rem_id}",
                callback_data=f"view_reminder_{rem_id}"
            )
        ])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"page_{page + 1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_reminder_field_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора поля для редактирования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Название", callback_data=f"edit_field_{reminder_id}_title"),
        ],
        [
            InlineKeyboardButton(text="🕐 Времена", callback_data=f"edit_field_{reminder_id}_times"),
        ],
        [
            InlineKeyboardButton(text="📅 Срок", callback_data=f"edit_field_{reminder_id}_end_date"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"view_reminder_{reminder_id}"),
        ]
    ])


def cancel_edit_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отмены редактирования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit"),
        ]
    ])
