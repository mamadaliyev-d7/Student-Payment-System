from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, services
from app.database import get_db
from app.deps import required_month
from app.schemas import DebtorsResponse
from app.utils import MonthRange

router = APIRouter(tags=["Должники"])


@router.get("/debtors", response_model=DebtorsResponse)
def get_debtors(month_range: MonthRange = Depends(required_month), db: Session = Depends(get_db)):
    """Должники за месяц ГГГГ-ММ.

    Задолженность = max(месячная стоимость − сумма оплат за месяц, 0).
    Учитывается текущая месячная стоимость ученика.
    """
    rows = crud.get_student_month_totals(db, month_range)
    return services.build_debtors_response(month_range, rows)
