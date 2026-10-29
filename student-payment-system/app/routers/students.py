from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.models import Student
from app.schemas import MAX_ID, StudentCreate, StudentRead, StudentUpdate

router = APIRouter(tags=["Ученики"])

StudentId = Annotated[int, Path(ge=1, le=MAX_ID, description="ID ученика")]


def get_student_or_404(db: Session, student_id: int) -> Student:
    student = crud.get_student(db, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=f"Ученик с ID {student_id} не найден")
    return student


@router.post("/students", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    """Создать ученика."""
    return crud.create_student(db, data)


@router.get("/students", response_model=List[StudentRead])
def list_students(db: Session = Depends(get_db)):
    """Список всех учеников."""
    return crud.list_students(db)


@router.get("/students/{student_id}", response_model=StudentRead)
def read_student(student_id: StudentId, db: Session = Depends(get_db)):
    """Информация об одном ученике."""
    return get_student_or_404(db, student_id)


@router.patch("/students/{student_id}", response_model=StudentRead)
def update_student(student_id: StudentId, data: StudentUpdate, db: Session = Depends(get_db)):
    """Изменить данные ученика (достаточно передать только изменяемые поля)."""
    student = get_student_or_404(db, student_id)
    return crud.update_student(db, student, data)


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: StudentId, db: Session = Depends(get_db)):
    """Удалить ученика. Все его оплаты удаляются вместе с ним."""
    student = get_student_or_404(db, student_id)
    crud.delete_student(db, student)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
