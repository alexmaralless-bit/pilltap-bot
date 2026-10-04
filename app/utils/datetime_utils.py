"""Утилиты для работы с датами и временем."""
from datetime import datetime, timedelta
from typing import List, Optional
import pytz
from app.config import TIMEZONE


def get_timezone():
    """Получить объект timezone."""
    return pytz.timezone(TIMEZONE)


def now(tz: Optional[pytz.BaseTzInfo] = None) -> datetime:
    """Получить текущее время в указанной таймзоне."""
    if tz is None:
        tz = get_timezone()
    return datetime.now(tz)


def parse_time(time_str: str) -> Optional[str]:
    """
    Парсит строку времени и возвращает в формате HH:MM.
    Поддерживает: 12:30, 12.30, 12,30, 12 30, 12-30, 12ч30м, 12h30, 1230
    """
    import re
    
    # Убираем пробелы
    time_str = time_str.strip().replace(" ", "")
    
    # Паттерны для различных форматов
    patterns = [
        r"(\d{1,2})[:.,-](\d{2})",  # 12:30, 12.30, 12,30, 12-30
        r"(\d{1,2})[чh](\d{2})[мm]?",  # 12ч30м, 12h30
        r"^(\d{3,4})$",  # 1230 (только если 3-4 цифры)
    ]
    
    for pattern in patterns:
        match = re.match(pattern, time_str)
        if match:
            if len(match.groups()) == 2:
                hours = int(match.group(1))
                minutes = int(match.group(2))
            else:
                # Формат 1230
                time_num = int(match.group(1))
                if 100 <= time_num <= 2359:
                    hours = time_num // 100
                    minutes = time_num % 100
                else:
                    continue
            
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                return f"{hours:02d}:{minutes:02d}"
    
    return None


def format_datetime(dt: datetime, tz: Optional[pytz.BaseTzInfo] = None) -> str:
    """Форматирует datetime в читаемый формат."""
    if tz:
        dt = dt.astimezone(tz)
    return dt.strftime("%d.%m.%Y %H:%M")


def format_date(dt: datetime, tz: Optional[pytz.BaseTzInfo] = None) -> str:
    """Форматирует дату в читаемый формат."""
    if tz:
        dt = dt.astimezone(tz)
    return dt.strftime("%d.%m.%Y")


def format_time(dt: datetime, tz: Optional[pytz.BaseTzInfo] = None) -> str:
    """Форматирует время в читаемый формат."""
    if tz:
        dt = dt.astimezone(tz)
    return dt.strftime("%H:%M")


def get_next_occurrence(times: List[str], start_date: datetime, tz: Optional[pytz.BaseTzInfo] = None) -> Optional[datetime]:
    """
    Получить следующее срабатывание напоминания.
    times - список времён в формате "HH:MM"
    """
    if tz is None:
        tz = get_timezone()
    
    current = now(tz)
    if start_date.tzinfo is None:
        start_date = tz.localize(start_date)
    elif start_date.tzinfo != tz:
        start_date = start_date.astimezone(tz)
    
    # Если дата начала в будущем, возвращаем первое время в первый день
    if start_date.date() > current.date():
        first_time = times[0]
        hour, minute = map(int, first_time.split(":"))
        next_dt = start_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return next_dt
    
    # Ищем следующее время сегодня
    today = current.date()
    for time_str in times:
        hour, minute = map(int, time_str.split(":"))
        candidate = tz.localize(datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute)))
        if candidate > current:
            return candidate
    
    # Если сегодня ничего не найдено, берём первое время завтра
    tomorrow = today + timedelta(days=1)
    first_time = times[0]
    hour, minute = map(int, first_time.split(":"))
    next_dt = tz.localize(datetime.combine(tomorrow, datetime.min.time().replace(hour=hour, minute=minute)))
    return next_dt


def add_days(dt: datetime, days: int, tz: Optional[pytz.BaseTzInfo] = None) -> datetime:
    """Добавить дни к дате."""
    if tz is None:
        tz = get_timezone()
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt + timedelta(days=days)
