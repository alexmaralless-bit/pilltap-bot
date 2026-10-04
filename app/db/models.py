"""Модели базы данных."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """Модель пользователя."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(Integer, unique=True, nullable=False, index=True)
    tz = Column(String(50), default="Europe/Moscow")
    created_at = Column(DateTime, default=datetime.utcnow)

    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")


class Reminder(Base):
    """Модель напоминания."""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    times_json = Column(String(500), nullable=False)  # JSON массив времён, например ["07:00", "13:00", "19:00"]
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)  # None для бессрочных
    rule_type = Column(String(50), default="daily")  # daily, custom
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reminders")
    occurrences = relationship("ReminderOccurrence", back_populates="reminder", cascade="all, delete-orphan")


class ReminderOccurrence(Base):
    """Модель события напоминания."""
    __tablename__ = "reminder_occurrences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id"), nullable=False, index=True)
    planned_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), default="pending")  # pending, done, postponed, skipped
    done_at = Column(DateTime, nullable=True)
    postponed_from = Column(DateTime, nullable=True)  # Оригинальное время, если было отложено

    reminder = relationship("Reminder", back_populates="occurrences")
