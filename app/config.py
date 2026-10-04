"""Конфигурация приложения."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///pilltap.db")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Времена по умолчанию для периодов дня
DEFAULT_MORNING_TIME = "07:00"
DEFAULT_LUNCH_TIME = "13:00"
DEFAULT_EVENING_TIME = "19:00"
DEFAULT_TWICE_DAY_TIMES = ["09:00", "21:00"]
