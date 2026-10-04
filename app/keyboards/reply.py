"""Reply-клавиатуры для бота."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Мои напоминания")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напишите напоминание..."
    )
