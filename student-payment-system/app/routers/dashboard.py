from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, services
from app.database import get_db
from app.deps import required_month
from app.schemas import DashboardSummary
from app.utils import MonthRange

router = APIRouter(tags=["Дашборд"])


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(month_range: MonthRange = Depends(required_month), db: Session = Depends(get_db)):
    """Сводка за месяц: учеников, должников, общий долг, полученные платежи."""
    rows = crud.get_student_month_totals(db, month_range)
    return services.build_summary(month_range, rows)
