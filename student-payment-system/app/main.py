"""Точка входа: FastAPI-приложение, API и веб-интерфейс."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.errors import register_exception_handlers
from app.routers import dashboard, debtors, payments, students

APP_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Учёт учеников, оплат и задолженностей",
    description=(
        "REST API учебного центра: ученики, ежемесячные оплаты и должники. "
        "Суммы — целые числа в узбекских сумах (UZS). "
        "Оплата засчитывается в календарный месяц своей даты."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.include_router(students.router)
app.include_router(payments.router)
app.include_router(debtors.router)
app.include_router(dashboard.router)

app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(APP_DIR / "templates" / "index.html")
