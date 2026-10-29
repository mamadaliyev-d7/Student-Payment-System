from datetime import date

import pytest


def test_add_payment_with_date(client, create_student):
    student = create_student()
    response = client.post(
        "/payments", json={"student_id": student["id"], "amount": 300000, "payment_date": "2026-10-05"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert body["student_id"] == student["id"]
    assert body["amount"] == 300000
    assert body["payment_date"] == "2026-10-05"


def test_payment_without_date_uses_today(client, create_student):
    student = create_student()
    before = date.today()
    response = client.post("/payments", json={"student_id": student["id"], "amount": 1000})
    after = date.today()
    assert response.status_code == 201
    assert response.json()["payment_date"] in {before.isoformat(), after.isoformat()}


def test_payment_for_missing_student_returns_404(client):
    response = client.post("/payments", json={"student_id": 999, "amount": 1000})
    assert response.status_code == 404
    assert client.get("/payments").json() == []


@pytest.mark.parametrize("amount", [0, -1, -500000, 1.5, "abc", 10**13])
def test_invalid_amount_returns_422(client, create_student, amount):
    student = create_student()
    response = client.post("/payments", json={"student_id": student["id"], "amount": amount})
    assert response.status_code == 422
    assert client.get("/payments").json() == []


@pytest.mark.parametrize(
    "bad_date",
    ["2026-13-01", "2026-02-30", "01.10.2026", "2026/10/05", "2026-10-5", "abc", "", "1999-12-31", "2101-01-01"],
)
def test_invalid_date_returns_422(client, create_student, bad_date):
    student = create_student()
    response = client.post(
        "/payments", json={"student_id": student["id"], "amount": 1000, "payment_date": bad_date}
    )
    assert response.status_code == 422
    assert client.get("/payments").json() == []


@pytest.mark.parametrize("bad_id", [0, -5, "abc"])
def test_invalid_student_id_in_payment_returns_422(client, bad_id):
    assert client.post("/payments", json={"student_id": bad_id, "amount": 1000}).status_code == 422


def test_payment_requires_student_and_amount(client, create_student):
    student = create_student()
    assert client.post("/payments", json={"amount": 1000}).status_code == 422
    assert client.post("/payments", json={"student_id": student["id"]}).status_code == 422


def test_list_payments_newest_first(client, create_student, add_payment):
    student = create_student()
    old = add_payment(student["id"], 100000, "2026-09-10")
    new = add_payment(student["id"], 200000, "2026-10-10")
    same_day_later = add_payment(student["id"], 300000, "2026-10-10")

    payments = client.get("/payments").json()
    assert [p["id"] for p in payments] == [same_day_later["id"], new["id"], old["id"]]


def test_list_payments_filter_by_month(client, create_student, add_payment):
    student = create_student()
    add_payment(student["id"], 100000, "2026-09-30")
    october_a = add_payment(student["id"], 200000, "2026-10-01")
    october_b = add_payment(student["id"], 300000, "2026-10-31")
    add_payment(student["id"], 400000, "2026-11-01")

    response = client.get("/payments", params={"month": "2026-10"})
    assert response.status_code == 200
    assert {p["id"] for p in response.json()} == {october_a["id"], october_b["id"]}


def test_list_payments_filter_by_student(client, create_student, add_payment):
    ali = create_student(name="Ali")
    madina = create_student(name="Madina")
    mine = add_payment(ali["id"], 100000, "2026-10-01")
    add_payment(madina["id"], 200000, "2026-10-01")

    response = client.get("/payments", params={"student_id": ali["id"]})
    assert [p["id"] for p in response.json()] == [mine["id"]]


@pytest.mark.parametrize("bad_month", ["2026-13", "2026-1", "abc", "", "2026/10"])
def test_list_payments_invalid_month_returns_422(client, bad_month):
    assert client.get("/payments", params={"month": bad_month}).status_code == 422


def test_student_payment_history(client, create_student, add_payment):
    ali = create_student(name="Ali")
    madina = create_student(name="Madina")
    first = add_payment(ali["id"], 100000, "2026-09-05")
    second = add_payment(ali["id"], 150000, "2026-10-05")
    add_payment(madina["id"], 999, "2026-10-05")

    response = client.get(f"/students/{ali['id']}/payments")
    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [second["id"], first["id"]]
    assert all(p["student_id"] == ali["id"] for p in response.json())


def test_student_payment_history_filter_by_month(client, create_student, add_payment):
    student = create_student()
    add_payment(student["id"], 100000, "2026-09-05")
    october = add_payment(student["id"], 150000, "2026-10-05")

    response = client.get(f"/students/{student['id']}/payments", params={"month": "2026-10"})
    assert [p["id"] for p in response.json()] == [october["id"]]


def test_student_payment_history_empty(client, create_student):
    student = create_student()
    response = client.get(f"/students/{student['id']}/payments")
    assert response.status_code == 200
    assert response.json() == []


def test_student_payment_history_for_missing_student_returns_404(client):
    assert client.get("/students/999/payments").status_code == 404


def test_student_payment_history_invalid_id_returns_422(client):
    assert client.get("/students/0/payments").status_code == 422
    assert client.get("/students/abc/payments").status_code == 422


def test_payments_survive_application_restart(client_factory):
    """Платежи лежат в файле БД, а не в памяти процесса."""
    with client_factory() as first_run:
        student = first_run.post(
            "/students",
            json={"name": "Ali", "phone": "+998901234567", "group_name": "Python", "monthly_fee": 500000},
        ).json()
        created = first_run.post(
            "/payments", json={"student_id": student["id"], "amount": 250000, "payment_date": "2026-10-05"}
        ).json()

    with client_factory() as second_run:
        payments = second_run.get("/payments").json()
        assert payments == [created]
        assert second_run.get(f"/students/{student['id']}/payments").json() == [created]
        debtors = second_run.get("/debtors", params={"month": "2026-10"}).json()
        assert debtors["debtors"][0]["debt_amount"] == 250000
