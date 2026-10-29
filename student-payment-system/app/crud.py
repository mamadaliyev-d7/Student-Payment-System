"""Работа с базой данных: все запросы параметризованы через SQLAlchemy (без SQL-инъекций)."""

from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Payment, Student
from app.schemas import PaymentCreate, StudentCreate, StudentUpdate
from app.utils import MonthRange


# --------------------------------------------------------------------------- ученики
def create_student(db: Session, data: StudentCreate) -> Student:
    student = Student(**data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def list_students(db: Session) -> List[Student]:
    return list(db.scalars(select(Student).order_by(Student.id)))


def get_student(db: Session, student_id: int) -> Optional[Student]:
    return db.get(Student, student_id)


def update_student(db: Session, student: Student, data: StudentUpdate) -> Student:
    for field_name, value in data.model_dump(exclude_unset=True).items():
        setattr(student, field_name, value)
    db.commit()
    db.refresh(student)
    return student


def delete_student(db: Session, student: Student) -> None:
    """Удаляет ученика вместе с его оплатами (cascade на уровне ORM и внешнего ключа)."""
    db.delete(student)
    db.commit()


# ---------------------------------------------------------------------------- оплаты
def create_payment(db: Session, data: PaymentCreate) -> Payment:
    payment = Payment(
        student_id=data.student_id,
        amount=data.amount,
        payment_date=data.payment_date or date.today(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def list_payments(
    db: Session,
    month_range: Optional[MonthRange] = None,
    student_id: Optional[int] = None,
) -> List[Payment]:
    """Оплаты, новые сверху. Месяц — полуинтервал [start, end), поэтому границы точные."""
    stmt = select(Payment)
    if student_id is not None:
        stmt = stmt.where(Payment.student_id == student_id)
    if month_range is not None:
        stmt = stmt.where(
            Payment.payment_date >= month_range.start,
            Payment.payment_date < month_range.end,
        )
    stmt = stmt.order_by(Payment.payment_date.desc(), Payment.id.desc())
    return list(db.scalars(stmt))


# -------------------------------------------------------------------- отчёт за месяц
def get_student_month_totals(db: Session, month_range: MonthRange) -> List[Tuple[Student, int]]:
    """Для каждого ученика — сумма его оплат за месяц (0, если оплат не было).

    Один запрос: подзапрос суммирует оплаты месяца по ученикам, затем LEFT JOIN
    к таблице учеников. Используется ТЕКУЩАЯ месячная стоимость ученика.
    """
    paid_subquery = (
        select(
            Payment.student_id.label("student_id"),
            func.sum(Payment.amount).label("paid"),
        )
        .where(
            Payment.payment_date >= month_range.start,
            Payment.payment_date < month_range.end,
        )
        .group_by(Payment.student_id)
        .subquery()
    )
    stmt = (
        select(Student, func.coalesce(paid_subquery.c.paid, 0))
        .select_from(Student)
        .outerjoin(paid_subquery, paid_subquery.c.student_id == Student.id)
        .order_by(Student.id)
    )
    return [(student, int(paid)) for student, paid in db.execute(stmt).all()]
