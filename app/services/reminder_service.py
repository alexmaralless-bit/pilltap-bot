"""Сервис для работы с напоминаниями."""
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.db.models import User, Reminder, ReminderOccurrence
from app.utils.datetime_utils import get_timezone, now, get_next_occurrence, add_days
from app.config import TIMEZONE


class ReminderService:
    """Сервис для управления напоминаниями."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.timezone = get_timezone()
    
    async def get_or_create_user(self, tg_id: int) -> User:
        """Получить или создать пользователя."""
        result = await self.session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(tg_id=tg_id, tz=TIMEZONE)
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        
        return user
    
    async def create_reminder(
        self,
        user_id: int,
        title: str,
        times: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Reminder:
        """Создать напоминание."""
        if start_date is None:
            start_date = now(self.timezone)
        elif start_date.tzinfo is None:
            start_date = self.timezone.localize(start_date)
        
        if end_date and end_date.tzinfo is None:
            end_date = self.timezone.localize(end_date)
        
        reminder = Reminder(
            user_id=user_id,
            title=title,
            times_json=json.dumps(times, ensure_ascii=False),
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )
        
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)
        
        # Создаём первое событие
        await self._schedule_next_occurrence(reminder)
        
        return reminder
    
    async def _schedule_next_occurrence(self, reminder: Reminder):
        """Запланировать следующее срабатывание напоминания."""
        if not reminder.is_active:
            return
        
        # Проверяем, не истёк ли срок
        if reminder.end_date:
            current = now(self.timezone)
            if reminder.end_date < current:
                reminder.is_active = False
                await self.session.commit()
                return
        
        times = json.loads(reminder.times_json)
        next_time = get_next_occurrence(times, reminder.start_date, self.timezone)
        
        if not next_time:
            return
        
        # Проверяем, не истёк ли срок для следующего срабатывания
        if reminder.end_date and next_time > reminder.end_date:
            reminder.is_active = False
            await self.session.commit()
            return
        
        # Проверяем, нет ли уже запланированного события на это время
        existing = await self.session.execute(
            select(ReminderOccurrence).where(
                and_(
                    ReminderOccurrence.reminder_id == reminder.id,
                    ReminderOccurrence.planned_at == next_time,
                    ReminderOccurrence.status == "pending"
                )
            )
        )
        if existing.scalar_one_or_none():
            return
        
        occurrence = ReminderOccurrence(
            reminder_id=reminder.id,
            planned_at=next_time,
            status="pending"
        )
        
        self.session.add(occurrence)
        await self.session.commit()
    
    async def get_user_reminders(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
        active_only: bool = False
    ) -> List[Reminder]:
        """Получить напоминания пользователя."""
        query = select(Reminder).where(Reminder.user_id == user_id)
        
        if active_only:
            query = query.where(Reminder.is_active == True)
        
        query = query.order_by(Reminder.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def count_user_reminders(
        self,
        user_id: int,
        active_only: bool = False
    ) -> int:
        """Подсчитать количество напоминаний пользователя."""
        from sqlalchemy import func
        
        query = select(func.count(Reminder.id)).where(Reminder.user_id == user_id)
        
        if active_only:
            query = query.where(Reminder.is_active == True)
        
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_reminder(self, reminder_id: int, user_id: int) -> Optional[Reminder]:
        """Получить напоминание по ID."""
        result = await self.session.execute(
            select(Reminder).where(
                and_(
                    Reminder.id == reminder_id,
                    Reminder.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def update_reminder(
        self,
        reminder_id: int,
        user_id: int,
        title: Optional[str] = None,
        times: Optional[List[str]] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[Reminder]:
        """Обновить напоминание."""
        reminder = await self.get_reminder(reminder_id, user_id)
        if not reminder:
            return None
        
        if title:
            reminder.title = title
        if times:
            reminder.times_json = json.dumps(times, ensure_ascii=False)
        if end_date is not None:
            if end_date.tzinfo is None:
                end_date = self.timezone.localize(end_date)
            reminder.end_date = end_date
        
        await self.session.commit()
        await self.session.refresh(reminder)
        
        # Пересоздаём следующие события
        await self._reschedule_reminder(reminder)
        
        return reminder
    
    async def _reschedule_reminder(self, reminder: Reminder):
        """Пересоздать события для напоминания."""
        # Удаляем все pending события
        result = await self.session.execute(
            select(ReminderOccurrence).where(
                and_(
                    ReminderOccurrence.reminder_id == reminder.id,
                    ReminderOccurrence.status == "pending"
                )
            )
        )
        pending_occurrences = result.scalars().all()
        for occ in pending_occurrences:
            await self.session.delete(occ)
        
        await self.session.commit()
        
        # Создаём новое следующее событие
        await self._schedule_next_occurrence(reminder)
    
    async def toggle_reminder_active(self, reminder_id: int, user_id: int) -> Optional[Reminder]:
        """Переключить активность напоминания."""
        reminder = await self.get_reminder(reminder_id, user_id)
        if not reminder:
            return None
        
        reminder.is_active = not reminder.is_active
        await self.session.commit()
        await self.session.refresh(reminder)
        
        if reminder.is_active:
            await self._schedule_next_occurrence(reminder)
        
        return reminder
    
    async def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        """Удалить напоминание."""
        reminder = await self.get_reminder(reminder_id, user_id)
        if not reminder:
            return False
        
        await self.session.delete(reminder)
        await self.session.commit()
        return True
    
    async def get_pending_occurrences(self, limit: int = 100) -> List[ReminderOccurrence]:
        """Получить запланированные события для отправки."""
        current = now(self.timezone)
        
        result = await self.session.execute(
            select(ReminderOccurrence)
            .options(selectinload(ReminderOccurrence.reminder))
            .where(
                and_(
                    ReminderOccurrence.status == "pending",
                    ReminderOccurrence.planned_at <= current,
                    ReminderOccurrence.reminder.has(Reminder.is_active == True)
                )
            )
            .limit(limit)
        )
        
        return list(result.scalars().all())
    
    async def mark_occurrence_done(self, occurrence_id: int) -> Optional[ReminderOccurrence]:
        """Отметить событие как выполненное."""
        result = await self.session.execute(
            select(ReminderOccurrence)
            .options(selectinload(ReminderOccurrence.reminder))
            .where(ReminderOccurrence.id == occurrence_id)
        )
        occurrence = result.scalar_one_or_none()
        
        if not occurrence:
            return None
        
        occurrence.status = "done"
        occurrence.done_at = now(self.timezone)
        
        await self.session.commit()
        await self.session.refresh(occurrence)
        
        # Планируем следующее срабатывание
        await self._schedule_next_occurrence(occurrence.reminder)
        
        return occurrence
    
    async def postpone_occurrence(
        self,
        occurrence_id: int,
        new_time: datetime
    ) -> Optional[ReminderOccurrence]:
        """Отложить событие."""
        result = await self.session.execute(
            select(ReminderOccurrence)
            .options(selectinload(ReminderOccurrence.reminder))
            .where(ReminderOccurrence.id == occurrence_id)
        )
        occurrence = result.scalar_one_or_none()
        
        if not occurrence:
            return None
        
        if new_time.tzinfo is None:
            new_time = self.timezone.localize(new_time)
        
        occurrence.postponed_from = occurrence.planned_at
        occurrence.planned_at = new_time
        occurrence.status = "postponed"
        
        await self.session.commit()
        await self.session.refresh(occurrence)
        
        return occurrence
