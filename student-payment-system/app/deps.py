"""Зависимости FastAPI: разбор параметра month."""

from typing import Optional

from fastapi import HTTPException, Query

from app.utils import MonthRange, parse_month

_MONTH_DESCRIPTION = "Месяц в формате ГГГГ-ММ"


def _parse_or_422(value: str) -> MonthRange:
    try:
        return parse_month(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def required_month(
    month: str = Query(..., description=_MONTH_DESCRIPTION, examples=["2026-10"]),
) -> MonthRange:
    return _parse_or_422(month)


def optional_month(
    month: Optional[str] = Query(None, description=_MONTH_DESCRIPTION, examples=["2026-10"]),
) -> Optional[MonthRange]:
    return None if month is None else _parse_or_422(month)
