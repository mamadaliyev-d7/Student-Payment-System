"""ORM-модели: ученики и оплаты."""

from datetime import date
from typing import List

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("monthly_fee >= 0", name="ck_students_fee_non_negative"),
        # AUTOINCREMENT: идентификатор удалённого ученика не будет выдан повторно.
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30))
    group_name: Mapped[str] = mapped_column(String(100), index=True)
    # Суммы хранятся целыми числами в сумах (UZS): без ошибок округления float.
    monthly_fee: Mapped[int] = mapped_column(Integer)

    # При удалении ученика его оплаты удаляются вместе с ним.
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        Index("ix_payments_student_date", "student_id", "payment_date"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column(Integer)
    payment_date: Mapped[date] = mapped_column(Date, index=True)

    student: Mapped["Student"] = relationship(back_populates="payments")
