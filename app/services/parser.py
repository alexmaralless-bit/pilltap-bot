"""Парсер текста для извлечения информации о напоминаниях."""
import re
import json
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import dateparser
from app.config import (
    DEFAULT_MORNING_TIME,
    DEFAULT_LUNCH_TIME,
    DEFAULT_EVENING_TIME,
    DEFAULT_TWICE_DAY_TIMES,
    TIMEZONE
)
from app.utils.datetime_utils import parse_time, get_timezone, now


class ReminderParser:
    """Парсер для извлечения данных о напоминании из текста."""
    
    def __init__(self):
        self.timezone = get_timezone()
        # Паттерны для распознавания
        self.period_keywords = {
            "утро": DEFAULT_MORNING_TIME,
            "утром": DEFAULT_MORNING_TIME,
            "утренний": DEFAULT_MORNING_TIME,
            "обед": DEFAULT_LUNCH_TIME,
            "обедом": DEFAULT_LUNCH_TIME,
            "днём": DEFAULT_LUNCH_TIME,
            "днем": DEFAULT_LUNCH_TIME,
            "вечер": DEFAULT_EVENING_TIME,
            "вечером": DEFAULT_EVENING_TIME,
            "вечерний": DEFAULT_EVENING_TIME,
        }
        
        self.frequency_patterns = [
            (r"(\d+)\s*раза?\s*в\s*день", "times_per_day"),
            (r"(\d+)\s*раз\s*в\s*день", "times_per_day"),
        ]
        
        self.duration_patterns = [
            (r"на\s+(\d+)\s*дн[еяй]", "days"),
            (r"в\s+течение\s+(\d+)\s*дн[еяй]", "days"),
            (r"в\s+течение\s+(\d+)\s*х?\s*дн[еяй]", "days"),
            (r"в\s+течение\s+(\d+)\s*дн[еяй]", "days"),
            (r"на\s+неделю", "week"),
            (r"на\s+(\d+)\s*недел[иь]", "weeks"),
        ]
        
        self.until_patterns = [
            (r"до\s+послезавтра", "after_tomorrow"),
            (r"до\s+(понедельника|вторника|среды|четверга|пятницы|субботы|воскресенья)", "weekday"),
            (r"до\s+(пн|вт|ср|чт|пт|сб|вс)\b", "weekday_short"),
        ]
    
    def parse(self, text: str) -> Dict:
        """
        Парсит текст и возвращает словарь с распознанными данными.
        Возвращает: {
            'title': str или None,
            'times': List[str] или None,
            'end_date': datetime или None,
            'confidence': float (0-1)
        }
        """
        text = text.lower().strip()
        result = {
            'title': None,
            'times': None,
            'end_date': None,
            'confidence': 0.0
        }
        
        # Извлекаем времена
        times = self._extract_times(text)
        
        # Извлекаем периодичность
        frequency = self._extract_frequency(text)
        
        # Объединяем времена
        if times:
            result['times'] = times
        elif frequency:
            result['times'] = frequency
        
        # Извлекаем срок
        end_date = self._extract_end_date(text)
        if end_date:
            result['end_date'] = end_date
        
        # Извлекаем название лекарства
        title = self._extract_title(text)
        if title:
            result['title'] = title
        
        # Вычисляем уверенность
        confidence = self._calculate_confidence(result)
        result['confidence'] = confidence
        
        return result
    
    def _extract_times(self, text: str) -> Optional[List[str]]:
        """Извлекает времена из текста."""
        times = []
        
        # Ищем конкретные времена (12:30, 12.30 и т.д.)
        time_pattern = r"(\d{1,2}[:.,\s-]\d{2}|\d{1,2}[чh]\d{2}[мm]?|\b\d{3,4}\b)"
        matches = re.finditer(time_pattern, text)
        
        for match in matches:
            time_str = match.group(1)
            parsed = parse_time(time_str)
            if parsed and parsed not in times:
                times.append(parsed)
        
        # Ищем ключевые слова периодов дня
        found_periods = []
        for keyword, default_time in self.period_keywords.items():
            # Используем word boundary для точного совпадения
            if re.search(rf"\b{keyword}\b", text, re.IGNORECASE) and default_time not in found_periods:
                found_periods.append(default_time)
        
        if found_periods:
            # Если нашли периоды, добавляем их к временам или заменяем
            if not times:
                times = found_periods
            else:
                # Объединяем, убирая дубликаты
                times = sorted(list(set(times + found_periods)))
        
        # Убираем дубликаты и сортируем
        times = sorted(list(set(times))) if times else None
        
        return times
    
    def _extract_frequency(self, text: str) -> Optional[List[str]]:
        """Извлекает периодичность (N раз в день)."""
        for pattern, pattern_type in self.frequency_patterns:
            match = re.search(pattern, text)
            if match:
                count = int(match.group(1))
                if count == 3:
                    return [DEFAULT_MORNING_TIME, DEFAULT_LUNCH_TIME, DEFAULT_EVENING_TIME]
                elif count == 2:
                    return DEFAULT_TWICE_DAY_TIMES
                elif count == 1:
                    # Если 1 раз в день, нужно найти время или использовать утро по умолчанию
                    return [DEFAULT_MORNING_TIME]
        
        return None
    
    def _extract_end_date(self, text: str) -> Optional[datetime]:
        """Извлекает дату окончания."""
        current = now(self.timezone)
        
        # Сначала проверяем паттерны "до ..." (они более специфичны)
        for pattern, pattern_type in self.until_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if pattern_type == "after_tomorrow":
                    end_date = current + timedelta(days=2)
                    return end_date.replace(hour=23, minute=59, second=59)
                elif pattern_type == "weekday" or pattern_type == "weekday_short":
                    weekday_name = match.group(1)
                    end_date = self._parse_weekday(weekday_name, current)
                    if end_date:
                        return end_date.replace(hour=23, minute=59, second=59)
        
        # Проверяем паттерны "на N дней"
        for pattern, pattern_type in self.duration_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if pattern_type == "days":
                    days = int(match.group(1))
                    end_date = current + timedelta(days=days)
                    return end_date.replace(hour=23, minute=59, second=59)
                elif pattern_type == "week":
                    end_date = current + timedelta(weeks=1)
                    return end_date.replace(hour=23, minute=59, second=59)
                elif pattern_type == "weeks":
                    weeks = int(match.group(1))
                    end_date = current + timedelta(weeks=weeks)
                    return end_date.replace(hour=23, minute=59, second=59)
        
        # Пробуем dateparser для остальных случаев
        # Ищем "до <дата>" (только если не нашли выше)
        until_match = re.search(r"до\s+(.+)", text, re.IGNORECASE)
        if until_match:
            date_str = until_match.group(1).strip()
            # Убираем лишние слова
            date_str = re.sub(r"\s+(года?|месяца?|дня?)\s*$", "", date_str)
            parsed_date = dateparser.parse(
                date_str,
                languages=['ru'],
                settings={'TIMEZONE': TIMEZONE, 'RELATIVE_BASE': current, 'PREFER_DATES_FROM': 'future'}
            )
            if parsed_date:
                if parsed_date.tzinfo is None:
                    parsed_date = self.timezone.localize(parsed_date)
                elif parsed_date.tzinfo != self.timezone:
                    parsed_date = parsed_date.astimezone(self.timezone)
                return parsed_date.replace(hour=23, minute=59, second=59)
        
        return None
    
    def _parse_weekday(self, weekday_name: str, current: datetime) -> Optional[datetime]:
        """Парсит день недели и возвращает дату."""
        weekday_map = {
            # Именительный падеж
            "понедельник": 0, "пн": 0,
            "вторник": 1, "вт": 1,
            "среда": 2, "ср": 2,
            "четверг": 3, "чт": 3,
            "пятница": 4, "пт": 4,
            "суббота": 5, "сб": 5,
            "воскресенье": 6, "вс": 6,
            # Родительный падеж
            "понедельника": 0,
            "вторника": 1,
            "среды": 2,
            "четверга": 3,
            "пятницы": 4,
            "субботы": 5,
            "воскресенья": 6,
        }
        
        weekday_name = weekday_name.lower().strip()
        target_weekday = weekday_map.get(weekday_name)
        
        if target_weekday is None:
            return None
        
        current_weekday = current.weekday()
        days_ahead = target_weekday - current_weekday
        
        if days_ahead <= 0:
            days_ahead += 7
        
        return current + timedelta(days=days_ahead)
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Извлекает название лекарства."""
        # Убираем служебные слова и паттерны
        cleaned = text
        
        # Убираем времена
        time_pattern = r"(\d{1,2}[:.,\s-]\d{2}|\d{1,2}[чh]\d{2}[мm]?|\b\d{3,4}\b)"
        cleaned = re.sub(time_pattern, "", cleaned)
        
        # Убираем ключевые слова периодов
        for keyword in self.period_keywords.keys():
            cleaned = re.sub(rf"\b{keyword}\b", "", cleaned, flags=re.IGNORECASE)
        
        # Убираем паттерны периодичности
        for pattern, _ in self.frequency_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Убираем паттерны срока
        for pattern, _ in self.duration_patterns + self.until_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Убираем служебные слова
        # «до <дата>» и всё после него — это срок, а не название
        cleaned = re.sub(r"\bдо\s+.+$", "", cleaned, flags=re.IGNORECASE)

        # Служебные слова — только целиком, иначе выпадают буквы внутри названий
        # («Витамин» → «итамин», «Називин» → «зиин»)
        service_words = [
            r"\bв\s+течение\b\s*",
            r"\bнапомни\b\s*",
            r"\bпринимать\b\s*",
            r"\bпринять\b\s*",
            r"\bпить\b\s*",
            r"\bвыпить\b\s*",
            r"\bтаблетк[иуа]?\b\s*",
            r"\bлекарство\b\s*",
            r"\bпрепарат\b\s*",
            r"\bв\b\s*",
            r"\bдо\b\s*",
            r"\bна\b\s*",
            r"\b(каждое|каждый|каждую|каждые|ежедневно)\b\s*",
            r"\b\d+\s*(дн[а-я]*|недел[а-я]*|месяц[а-я]*)\b\s*",
        ]
        
        for word in service_words:
            cleaned = re.sub(word, "", cleaned, flags=re.IGNORECASE)
        
        # Очищаем от лишних пробелов
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        # Убираем союзы и предлоги в конце
        # Союзы и предлоги, которые могут остаться
        stop_words = ["и", "или", "а", "но", "с", "со", "для", "от", "к", "по", "из", "за", "на", "в", "о", "об", "про"]
        # остатки от вырезанных шаблонов: одиночные кириллические буквы («й» от «дней»);
        # латиницу не трогаем — «Витамин D», «Омега B»
        words = [w for w in cleaned.split() if not re.fullmatch(r"[а-яё]", w)]
        
        # Убираем стоп-слова с конца
        while words and words[-1].lower() in stop_words:
            words.pop()
        
        # Если осталось что-то осмысленное (больше 2 символов)
        if words and len(" ".join(words)) > 2:
            # Берём первые 1-3 слова как название
            title = " ".join(words[:3])
            return title.title()
        
        return None
    
    def _calculate_confidence(self, result: Dict) -> float:
        """Вычисляет уверенность в распознавании (0-1)."""
        score = 0.0
        
        if result['title']:
            score += 0.4
        if result['times']:
            score += 0.4
        if result['end_date']:
            score += 0.2
        else:
            # Если срок не указан, это нормально (бессрочно)
            score += 0.1
        
        return min(score, 1.0)
