"""Чистые функции без доступа к БД и FastAPI: разбор месяца и расчёт долга."""

import re
from dataclasses import dataclass
from datetime import date

# [0-9] вместо \d: \d в Python принимает и «чужие» цифры (например, арабо-индийские).
_MONTH_RE = re.compile(r"([0-9]{4})-([0-9]{2})")

MIN_YEAR = 2000
MAX_YEAR = 2100

MONTH_FORMAT_ERROR = "Некорректный формат месяца. Ожидается ГГГГ-ММ, например 2026-10"


@dataclass(frozen=True)
class MonthRange:
    """Календарный месяц как полуинтервал дат [start, end)."""

    label: str  # "2026-10"
    start: date  # первый день месяца (включительно)
    end: date  # первый день следующего месяца (не включительно)


def parse_month(value: str) -> MonthRange:
    """Разбирает строку ГГГГ-ММ. При ошибке бросает ValueError с понятным текстом."""
    match = _MONTH_RE.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(MONTH_FORMAT_ERROR)

    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        raise ValueError("Некорректный месяц: номер месяца должен быть от 01 до 12")
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"Некорректный год: допустимы значения от {MIN_YEAR} до {MAX_YEAR}")

    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return MonthRange(label=f"{year:04d}-{month:02d}", start=start, end=end)


def calculate_debt(monthly_fee: int, paid_amount: int) -> int:
    """Задолженность = max(месячная стоимость − оплачено за месяц, 0)."""
    return max(monthly_fee - paid_amount, 0)
