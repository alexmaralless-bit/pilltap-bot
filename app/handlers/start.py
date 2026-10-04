"""Обработчик команды /start."""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.keyboards.reply import main_menu_keyboard
from app.services.reminder_service import ReminderService
from app.db.session import async_session_maker

router = Router()


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()
    
    async with async_session_maker() as session:
        service = ReminderService(session)
        await service.get_or_create_user(message.from_user.id)
    
    instructions = (
        "👋 Привет! Я бот для напоминаний о приёме таблеток.\n\n"
        "📝 **Как использовать:**\n"
        "Просто напишите напоминание свободным текстом, например:\n\n"
        "• `Напомни принимать Аспирин в 12:30`\n"
        "• `Називин 3 раза в день в течение 3 дней`\n"
        "• `Парацетамол утром и вечером до пятницы`\n"
        "• `Витамин D в 08:00 и 20:00 на неделю`\n\n"
        "🤖 Бот распознаёт:\n"
        "• Название лекарства\n"
        "• Время приёма (12:30, 12.30, утро, обед, вечер)\n"
        "• Периодичность (2 раза в день, 3 раза в день)\n"
        "• Срок действия (на 3 дня, до пятницы, до 25 января)\n\n"
        "📋 Используйте команду /reminders для просмотра всех напоминаний."
    )
    
    await message.answer(
        instructions,
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
