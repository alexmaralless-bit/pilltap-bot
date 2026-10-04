import os

os.environ.setdefault("BOT_TOKEN", "test-token")

import pytest

from app.services.parser import ReminderParser

CASES = [
    ("Напомни принимать Аспирин в 12:30", "Аспирин"),
    ("Називин 3 раза в день в течение 3 дней", "Називин"),
    ("Парацетамол утром и вечером до пятницы", "Парацетамол"),
    ("Витамин D в 08:00 и 20:00 на неделю", "Витамин D"),
    ("Антибиотик 2 раза в день до 25 января", "Антибиотик"),
]


@pytest.fixture(scope="module")
def parser():
    return ReminderParser()


@pytest.mark.parametrize("text,title", CASES)
def test_title(parser, text, title):
    result = parser.parse(text)
    assert result["title"] is not None
    assert result["title"].lower() == title.lower()


def test_times(parser):
    assert parser.parse("Напомни принимать Аспирин в 12:30")["times"] == ["12:30"]
    assert parser.parse("Витамин D в 08:00 и 20:00 на неделю")["times"] == ["08:00", "20:00"]
    assert parser.parse("Парацетамол утром и вечером до пятницы")["times"] == ["07:00", "19:00"]
    assert parser.parse("Називин 3 раза в день в течение 3 дней")["times"] == ["07:00", "13:00", "19:00"]
    assert parser.parse("Антибиотик 2 раза в день до 25 января")["times"] == ["09:00", "21:00"]
