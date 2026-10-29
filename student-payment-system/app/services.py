"""Бизнес-логика отчётов: из строк «(ученик, оплачено за месяц)» строим должников и сводку."""

from typing import Iterable, List, Tuple

from app.models import Student
from app.schemas import DashboardSummary, DebtorItem, DebtorsResponse
from app.utils import MonthRange, calculate_debt

MonthRows = Iterable[Tuple[Student, int]]


def build_debtors(rows: MonthRows) -> List[DebtorItem]:
    """Должник — тот, у кого оплаты за месяц меньше месячной стоимости (долг > 0)."""
    debtors: List[DebtorItem] = []
    for student, paid in rows:
        debt = calculate_debt(student.monthly_fee, paid)
        if debt > 0:
            debtors.append(
                DebtorItem(
                    student_id=student.id,
                    name=student.name,
                    phone=student.phone,
                    group_name=student.group_name,
                    monthly_fee=student.monthly_fee,
                    paid_amount=paid,
                    debt_amount=debt,
                )
            )
    return debtors


def build_debtors_response(month_range: MonthRange, rows: MonthRows) -> DebtorsResponse:
    debtors = build_debtors(rows)
    return DebtorsResponse(
        month=month_range.label,
        total_debtors=len(debtors),
        total_debt=sum(item.debt_amount for item in debtors),
        debtors=debtors,
    )


def build_summary(month_range: MonthRange, rows: MonthRows) -> DashboardSummary:
    rows = list(rows)
    debtors = build_debtors(rows)
    return DashboardSummary(
        month=month_range.label,
        total_students=len(rows),
        total_debtors=len(debtors),
        total_debt=sum(item.debt_amount for item in debtors),
        total_received=sum(paid for _, paid in rows),
    )
