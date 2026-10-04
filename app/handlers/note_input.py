"""Обработчик ввода заметок пользователем."""
import json
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.services.parser import ReminderParser
from app.services.reminder_service import ReminderService
from app.db.session import async_session_maker
from app.keyboards.inline import confirmation_keyboard
from app.keyboards.reply import main_menu_keyboard
from app.utils.datetime_utils import format_datetime, get_timezone, now

router = Router()
parser = ReminderParser()


class ReminderCreation(StatesGroup):
    """Состояния для создания напоминания."""
    waiting_confirmation = State()
    editing_title = State()
    editing_times = State()
    editing_end_date = State()


@router.message(F.text == "📋 Мои напоминания")
async def show_reminders(message: Message):
    """Показать список напоминаний."""
    from app.handlers.reminders import show_reminders_list
    await show_reminders_list(message)


@router.message(F.text == "/reminders")
async def cmd_reminders(message: Message):
    """Команда /reminders."""
    from app.handlers.reminders import show_reminders_list
    await show_reminders_list(message)


@router.message(F.text)
async def process_note_input(message: Message, state: FSMContext):
    """Обработка ввода текста пользователем."""
    # Проверяем, не находимся ли мы в режиме редактирования
    current_state = await state.get_state()
    if current_state == ReminderCreation.editing_title.state:
        await process_title_edit(message, state)
        return
    elif current_state == ReminderCreation.editing_times.state:
        await process_times_edit(message, state)
        return
    elif current_state == ReminderCreation.editing_end_date.state:
        await process_end_date_edit(message, state)
        return
    
    # Парсим текст
    text = message.text.strip()
    parsed = parser.parse(text)
    
    # Если уверенность низкая или не распознано название
    if parsed['confidence'] < 0.5 or not parsed['title']:
        await message.answer(
            "❌ Не удалось распознать напоминание. Попробуйте написать ещё раз.\n\n"
            "**Примеры:**\n"
            "• `Аспирин в 12:30`\n"
            "• `Називин 3 раза в день на 3 дня`\n"
            "• `Парацетамол утром и вечером`",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Если не распознаны времена, используем утро по умолчанию
    if not parsed['times']:
        parsed['times'] = ["07:00"]
    
    # Сохраняем данные в состояние
    await state.update_data(
        title=parsed['title'],
        times=parsed['times'],
        end_date=parsed['end_date'],
        original_text=text
    )
    
    # Формируем сообщение подтверждения
    confirmation_text = format_reminder_confirmation(parsed)
    
    await message.answer(
        confirmation_text,
        reply_markup=confirmation_keyboard(),
        parse_mode="Markdown"
    )
    
    await state.set_state(ReminderCreation.waiting_confirmation.state)


def format_reminder_confirmation(parsed: dict) -> str:
    """Форматирует текст подтверждения напоминания."""
    tz = get_timezone()
    current = now(tz)
    
    text = "📋 **Подтвердите напоминание:**\n\n"
    text += f"💊 **Препарат:** {parsed['title']}\n"
    text += f"🕐 **Времена:** {', '.join(parsed['times'])}\n"
    text += f"📅 **Дата начала:** {current.strftime('%d.%m.%Y')}\n"
    
    if parsed['end_date']:
        text += f"📆 **Дата окончания:** {format_datetime(parsed['end_date'], tz)}\n"
    else:
        text += "📆 **Срок:** Бессрочно\n"
    
    # Вычисляем следующее срабатывание
    from app.utils.datetime_utils import get_next_occurrence
    next_occ = get_next_occurrence(parsed['times'], current, tz)
    if next_occ:
        text += f"⏰ **Следующее срабатывание:** {format_datetime(next_occ, tz)}\n"
    
    return text


async def process_title_edit(message: Message, state: FSMContext):
    """Обработка редактирования названия."""
    new_title = message.text.strip()
    if len(new_title) < 2:
        await message.answer("❌ Название слишком короткое. Введите ещё раз:")
        return
    
    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    
    if reminder_id:
        # Редактирование существующего напоминания
        async with async_session_maker() as session:
            service = ReminderService(session)
            user = await service.get_or_create_user(message.from_user.id)
            reminder = await service.update_reminder(
                reminder_id,
                user.id,
                title=new_title
            )
            if reminder:
                from app.handlers.reminders import format_reminder_card, reminder_card_keyboard
                await message.answer(
                    f"✅ Название обновлено!\n\n{format_reminder_card(reminder, short=False)}",
                    reply_markup=reminder_card_keyboard(reminder.id, reminder.is_active),
                    parse_mode="Markdown"
                )
                await state.clear()
            else:
                await message.answer("❌ Напоминание не найдено.")
    else:
        # Создание нового напоминания
        data['title'] = new_title
        await state.update_data(**data)
        
        parsed = {
            'title': data['title'],
            'times': data.get('times', []),
            'end_date': data.get('end_date')
        }
        
        confirmation_text = format_reminder_confirmation(parsed)
        await message.answer(
            confirmation_text,
            reply_markup=confirmation_keyboard(),
            parse_mode="Markdown"
        )
        
        await state.set_state(ReminderCreation.waiting_confirmation.state)


async def process_times_edit(message: Message, state: FSMContext):
    """Обработка редактирования времён."""
    text = message.text.strip()
    parsed = parser.parse(text)
    
    if not parsed['times']:
        await message.answer(
            "❌ Не удалось распознать времена. Попробуйте ещё раз:\n"
            "• `12:30`\n"
            "• `утро, обед, вечер`\n"
            "• `08:00 и 20:00`"
        )
        return
    
    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    
    if reminder_id:
        # Редактирование существующего напоминания
        async with async_session_maker() as session:
            service = ReminderService(session)
            user = await service.get_or_create_user(message.from_user.id)
            reminder = await service.update_reminder(
                reminder_id,
                user.id,
                times=parsed['times']
            )
            if reminder:
                from app.handlers.reminders import format_reminder_card, reminder_card_keyboard
                await message.answer(
                    f"✅ Времена обновлены!\n\n{format_reminder_card(reminder, short=False)}",
                    reply_markup=reminder_card_keyboard(reminder.id, reminder.is_active),
                    parse_mode="Markdown"
                )
                await state.clear()
            else:
                await message.answer("❌ Напоминание не найдено.")
    else:
        # Создание нового напоминания
        data['times'] = parsed['times']
        await state.update_data(**data)
        
        parsed_full = {
            'title': data['title'],
            'times': data['times'],
            'end_date': data.get('end_date')
        }
        
        confirmation_text = format_reminder_confirmation(parsed_full)
        await message.answer(
            confirmation_text,
            reply_markup=confirmation_keyboard(),
            parse_mode="Markdown"
        )
        
        await state.set_state(ReminderCreation.waiting_confirmation.state)


async def process_end_date_edit(message: Message, state: FSMContext):
    """Обработка редактирования срока."""
    text = message.text.strip()
    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    
    end_date = None
    
    # Если "бессрочно" или пусто
    if text.lower() in ["бессрочно", "нет", ""]:
        end_date = None
    else:
        parsed = parser.parse(text)
        if not parsed['end_date']:
            # Пробуем dateparser напрямую
            import dateparser
            from app.config import TIMEZONE
            from app.utils.datetime_utils import now, get_timezone
            
            tz = get_timezone()
            current = now(tz)
            parsed_date = dateparser.parse(
                text,
                languages=['ru'],
                settings={'TIMEZONE': TIMEZONE, 'RELATIVE_BASE': current}
            )
            
            if parsed_date:
                if parsed_date.tzinfo is None:
                    parsed_date = tz.localize(parsed_date)
                elif parsed_date.tzinfo != tz:
                    parsed_date = parsed_date.astimezone(tz)
                parsed_date = parsed_date.replace(hour=23, minute=59, second=59)
                end_date = parsed_date
            else:
                await message.answer(
                    "❌ Не удалось распознать дату. Попробуйте ещё раз:\n"
                    "• `на 3 дня`\n"
                    "• `до пятницы`\n"
                    "• `до 25 января`\n"
                    "• `бессрочно`"
                )
                return
        else:
            end_date = parsed['end_date']
    
    if reminder_id:
        # Редактирование существующего напоминания
        async with async_session_maker() as session:
            service = ReminderService(session)
            user = await service.get_or_create_user(message.from_user.id)
            reminder = await service.update_reminder(
                reminder_id,
                user.id,
                end_date=end_date
            )
            if reminder:
                from app.handlers.reminders import format_reminder_card, reminder_card_keyboard
                await message.answer(
                    f"✅ Срок обновлён!\n\n{format_reminder_card(reminder, short=False)}",
                    reply_markup=reminder_card_keyboard(reminder.id, reminder.is_active),
                    parse_mode="Markdown"
                )
                await state.clear()
            else:
                await message.answer("❌ Напоминание не найдено.")
    else:
        # Создание нового напоминания
        data['end_date'] = end_date
        await state.update_data(**data)
        
        parsed_full = {
            'title': data['title'],
            'times': data.get('times', []),
            'end_date': data.get('end_date')
        }
        
        confirmation_text = format_reminder_confirmation(parsed_full)
        await message.answer(
            confirmation_text,
            reply_markup=confirmation_keyboard(),
            parse_mode="Markdown"
        )
        
        await state.set_state(ReminderCreation.waiting_confirmation.state)
