"""Pydantic-схемы: проверка входных данных и формат ответов."""

import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils import MAX_YEAR, MIN_YEAR

MAX_ID = 2_147_483_647
MAX_AMOUNT = 1_000_000_000_000  # 1 трлн сум — защита от опечаток и переполнения

_PHONE_RE = re.compile(r"\+?[0-9\s\-()]+")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _validate_phone(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", value)
    if not _PHONE_RE.fullmatch(value) or not 7 <= len(digits) <= 15:
        raise ValueError(
            "Некорректный номер телефона. Допустимы цифры, пробелы, «+», «-» и скобки, "
            "например +998901234567"
        )
    return value


# --------------------------------------------------------------------------- ученики
class StudentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=30)
    group_name: str = Field(min_length=1, max_length=100)
    monthly_fee: int = Field(ge=0, le=MAX_AMOUNT)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: str) -> str:
        return _validate_phone(value)


class StudentUpdate(BaseModel):
    """PATCH: передаются только изменяемые поля."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, min_length=1, max_length=30)
    group_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    monthly_fee: Optional[int] = Field(default=None, ge=0, le=MAX_AMOUNT)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, value: Optional[str]) -> Optional[str]:
        return value if value is None else _validate_phone(value)

    @model_validator(mode="after")
    def check_not_empty(self) -> "StudentUpdate":
        if not self.model_fields_set:
            raise ValueError("Передайте хотя бы одно поле для изменения")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"Поле «{field_name}» не может быть пустым")
        return self


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    group_name: str
    monthly_fee: int


# ---------------------------------------------------------------------------- оплаты
class PaymentCreate(BaseModel):
    student_id: int = Field(ge=1, le=MAX_ID)
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    payment_date: Optional[date] = None  # не передана — берётся сегодняшняя дата

    @field_validator("payment_date", mode="before")
    @classmethod
    def require_iso_format(cls, value):
        """Принимаем только строго ГГГГ-ММ-ДД (а не любой формат, который знает pydantic)."""
        if value is None:
            return value
        if isinstance(value, str) and _DATE_RE.fullmatch(value):
            return value
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        raise ValueError("Некорректная дата. Используйте формат ГГГГ-ММ-ДД, например 2026-10-05")

    @field_validator("payment_date")
    @classmethod
    def check_year_range(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and not MIN_YEAR <= value.year <= MAX_YEAR:
            raise ValueError(f"Год даты должен быть от {MIN_YEAR} до {MAX_YEAR}")
        return value


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    amount: int
    payment_date: date


# -------------------------------------------------------------------------- должники
class DebtorItem(BaseModel):
    student_id: int
    name: str
    phone: str
    group_name: str
    monthly_fee: int
    paid_amount: int
    debt_amount: int


class DebtorsResponse(BaseModel):
    month: str
    total_debtors: int
    total_debt: int  # сумма задолженности по всем должникам
    debtors: List[DebtorItem]


class DashboardSummary(BaseModel):
    month: str
    total_students: int
    total_debtors: int
    total_debt: int
    total_received: int  # все платежи за месяц, включая переплаты
