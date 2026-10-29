"""Подключение к SQLite и управление сессиями SQLAlchemy."""

import os
import sqlite3
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "students.db"


def _default_database_url() -> str:
    """Путь по умолчанию: <проект>/data/students.db (папка создаётся автоматически)."""
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


# Переменная окружения DATABASE_URL позволяет подменить базу (в том числе в тестах).
DATABASE_URL = os.getenv("DATABASE_URL") or _default_database_url()


class Base(DeclarativeBase):
    """Базовый класс всех моделей."""


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """В SQLite внешние ключи по умолчанию выключены — включаем для каждого соединения."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_engine(
    DATABASE_URL,
    # Обработчики FastAPI выполняются в пуле потоков, а соединение SQLite
    # по умолчанию привязано к потоку-создателю.
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


def init_db() -> None:
    """Создаёт таблицы, если их ещё нет. Данные при этом не затрагиваются."""
    from app import models  # noqa: F401  (регистрирует таблицы в Base.metadata)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: одна сессия на запрос, гарантированно закрывается."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
