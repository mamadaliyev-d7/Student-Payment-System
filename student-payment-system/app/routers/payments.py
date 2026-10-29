from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.deps import optional_month
from app.routers.students import get_student_or_404
from app.schemas import MAX_ID, PaymentCreate, PaymentRead
from app.utils import MonthRange

router = APIRouter(tags=["Оплаты"])


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(data: PaymentCreate, db: Session = Depends(get_db)):
    """Добавить оплату. Если дата не передана, используется сегодняшняя."""
    if crud.get_student(db, data.student_id) is None:
        raise HTTPException(status_code=404, detail=f"Ученик с ID {data.student_id} не найден")
    return crud.create_payment(db, data)


@router.get("/payments", response_model=List[PaymentRead])
def list_payments(
    month_range: Optional[MonthRange] = Depends(optional_month),
    student_id: Optional[int] = Query(None, ge=1, le=MAX_ID, description="Фильтр по ученику"),
    db: Session = Depends(get_db),
):
    """Список оплат (новые сверху). Можно отфильтровать по месяцу ГГГГ-ММ и по ученику."""
    return crud.list_payments(db, month_range=month_range, student_id=student_id)


@router.get("/students/{student_id}/payments", response_model=List[PaymentRead])
def list_student_payments(
    student_id: int = Path(..., ge=1, le=MAX_ID, description="ID ученика"),
    month_range: Optional[MonthRange] = Depends(optional_month),
    db: Session = Depends(get_db),
):
    """История оплат конкретного ученика (новые сверху), можно с фильтром по месяцу."""
    get_student_or_404(db, student_id)
    return crud.list_payments(db, month_range=month_range, student_id=student_id)
