"""Общие фикстуры. Тесты работают с ОТДЕЛЬНОЙ временной базой и не трогают data/students.db."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

# Важно: подменяем DATABASE_URL ДО импорта приложения, чтобы даже запуск lifespan
# (создание таблиц при старте) использовал временную базу, а не рабочую.
_BOOTSTRAP_DIR = tempfile.mkdtemp(prefix="student_payments_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_BOOTSTRAP_DIR) / 'bootstrap.db').as_posix()}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@contextmanager
def _client_for(db_url: str):
    """Клиент, работающий с БД по адресу db_url. Новая сессия на каждый запрос."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture()
def db_url(tmp_path):
    """Своя пустая база на каждый тест."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture()
def client(db_url):
    with _client_for(db_url) as test_client:
        yield test_client


@pytest.fixture()
def client_factory(db_url):
    """Позволяет «перезапустить приложение» поверх того же файла базы."""
    return lambda: _client_for(db_url)


@pytest.fixture()
def create_student(client):
    def _create(name="Ali", phone="+998901234567", group_name="Python Beginner", monthly_fee=500000):
        response = client.post(
            "/students",
            json={"name": name, "phone": phone, "group_name": group_name, "monthly_fee": monthly_fee},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture()
def add_payment(client):
    def _add(student_id, amount, payment_date=None):
        body = {"student_id": student_id, "amount": amount}
        if payment_date is not None:
            body["payment_date"] = payment_date
        response = client.post("/payments", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _add
