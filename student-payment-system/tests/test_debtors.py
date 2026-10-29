import pytest

MONTH = "2026-10"


def get_debtors(client, month=MONTH):
    response = client.get("/debtors", params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_database(client):
    assert get_debtors(client) == {"month": MONTH, "total_debtors": 0, "total_debt": 0, "debtors": []}


def test_no_payments_whole_fee_is_debt(client, create_student):
    student = create_student(monthly_fee=500000)
    data = get_debtors(client)
    assert data["total_debtors"] == 1
    assert data["debtors"][0] == {
        "student_id": student["id"],
        "name": "Ali",
        "phone": "+998901234567",
        "group_name": "Python Beginner",
        "monthly_fee": 500000,
        "paid_amount": 0,
        "debt_amount": 500000,
    }


def test_partial_payment_leaves_remainder(client, create_student, add_payment):
    student = create_student(monthly_fee=500000)
    add_payment(student["id"], 300000, "2026-10-05")
    debtor = get_debtors(client)["debtors"][0]
    assert debtor["paid_amount"] == 300000
    assert debtor["debt_amount"] == 200000


def test_full_payment_removes_from_debtors(client, create_student, add_payment):
    student = create_student(monthly_fee=500000)
    add_payment(student["id"], 500000, "2026-10-05")
    data = get_debtors(client)
    assert data["total_debtors"] == 0
    assert data["debtors"] == []


def test_overpayment_means_zero_debt_and_not_listed(client, create_student, add_payment):
    student = create_student(monthly_fee=500000)
    add_payment(student["id"], 700000, "2026-10-05")
    data = get_debtors(client)
    assert data["total_debtors"] == 0
    assert data["total_debt"] == 0


def test_multiple_payments_in_one_month_are_summed(client, create_student, add_payment):
    student = create_student(monthly_fee=500000)
    add_payment(student["id"], 100000, "2026-10-02")
    add_payment(student["id"], 150000, "2026-10-15")
    add_payment(student["id"], 50000, "2026-10-30")
    debtor = get_debtors(client)["debtors"][0]
    assert debtor["paid_amount"] == 300000
    assert debtor["debt_amount"] == 200000


def test_multiple_payments_can_cover_full_fee(client, create_student, add_payment):
    student = create_student(monthly_fee=500000)
    add_payment(student["id"], 200000, "2026-10-02")
    add_payment(student["id"], 300000, "2026-10-20")
    assert get_debtors(client)["total_debtors"] == 0


def test_only_selected_month_is_counted(client, create_student, add_payment):
    student = create_student(monthly_fee=500000)
    add_payment(student["id"], 500000, "2026-09-15")  # прошлый месяц
    add_payment(student["id"], 500000, "2026-11-15")  # следующий месяц
    add_payment(student["id"], 100000, "2026-10-15")

    october = get_debtors(client, "2026-10")["debtors"][0]
    assert october["paid_amount"] == 100000
    assert october["debt_amount"] == 400000

    assert get_debtors(client, "2026-09")["total_debtors"] == 0
    assert get_debtors(client, "2026-11")["total_debtors"] == 0
    assert get_debtors(client, "2026-08")["debtors"][0]["debt_amount"] == 500000


def test_month_boundaries(client, create_student, add_payment):
    student = create_student(monthly_fee=1000)
    add_payment(student["id"], 100, "2026-09-30")  # не октябрь
    add_payment(student["id"], 200, "2026-10-01")  # октябрь: первый день
    add_payment(student["id"], 300, "2026-10-31")  # октябрь: последний день
    add_payment(student["id"], 400, "2026-11-01")  # не октябрь
    debtor = get_debtors(client)["debtors"][0]
    assert debtor["paid_amount"] == 500


def test_december_does_not_leak_into_january(client, create_student, add_payment):
    student = create_student(monthly_fee=1000)
    add_payment(student["id"], 100, "2026-12-31")
    add_payment(student["id"], 200, "2027-01-01")
    assert get_debtors(client, "2026-12")["debtors"][0]["paid_amount"] == 100
    assert get_debtors(client, "2027-01")["debtors"][0]["paid_amount"] == 200


def test_leap_year_february(client, create_student, add_payment):
    student = create_student(monthly_fee=1000)
    add_payment(student["id"], 100, "2028-02-29")
    add_payment(student["id"], 200, "2028-03-01")
    assert get_debtors(client, "2028-02")["debtors"][0]["paid_amount"] == 100
    assert get_debtors(client, "2028-03")["debtors"][0]["paid_amount"] == 200


def test_example_from_specification(client, create_student, add_payment):
    ali = create_student(name="Ali", phone="+998901234567", group_name="Python Beginner", monthly_fee=500000)
    madina = create_student(name="Madina", phone="+998931234567", group_name="Frontend", monthly_fee=400000)
    dilnoza = create_student(name="Dilnoza", phone="+998971234567", group_name="Design", monthly_fee=300000)
    add_payment(ali["id"], 300000, "2026-10-05")
    add_payment(dilnoza["id"], 300000, "2026-10-06")

    assert get_debtors(client) == {
        "month": "2026-10",
        "total_debtors": 2,
        "total_debt": 600000,
        "debtors": [
            {
                "student_id": ali["id"], "name": "Ali", "phone": "+998901234567",
                "group_name": "Python Beginner", "monthly_fee": 500000,
                "paid_amount": 300000, "debt_amount": 200000,
            },
            {
                "student_id": madina["id"], "name": "Madina", "phone": "+998931234567",
                "group_name": "Frontend", "monthly_fee": 400000,
                "paid_amount": 0, "debt_amount": 400000,
            },
        ],
    }


def test_current_fee_is_used_when_fee_changes(client, create_student, add_payment):
    """Правило проекта: берётся действующая (текущая) месячная стоимость."""
    student = create_student(monthly_fee=500000)
    add_payment(student["id"], 300000, "2026-10-05")
    assert get_debtors(client)["debtors"][0]["debt_amount"] == 200000

    client.patch(f"/students/{student['id']}", json={"monthly_fee": 350000})
    debtor = get_debtors(client)["debtors"][0]
    assert debtor["monthly_fee"] == 350000
    assert debtor["debt_amount"] == 50000

    client.patch(f"/students/{student['id']}", json={"monthly_fee": 300000})
    assert get_debtors(client)["total_debtors"] == 0


def test_student_with_zero_fee_is_never_a_debtor(client, create_student):
    create_student(monthly_fee=0)
    assert get_debtors(client)["total_debtors"] == 0


def test_payments_of_other_students_do_not_mix(client, create_student, add_payment):
    ali = create_student(name="Ali", monthly_fee=500000)
    madina = create_student(name="Madina", monthly_fee=500000)
    add_payment(madina["id"], 500000, "2026-10-05")
    data = get_debtors(client)
    assert [d["student_id"] for d in data["debtors"]] == [ali["id"]]
    assert data["debtors"][0]["paid_amount"] == 0


def test_deleted_student_disappears_from_debtors(client, create_student):
    student = create_student()
    client.delete(f"/students/{student['id']}")
    assert get_debtors(client)["total_debtors"] == 0


@pytest.mark.parametrize(
    "bad_month",
    ["2026-13", "2026-00", "2026-1", "26-10", "2026/10", "2026-10-01", "abcd", "", "2026-10 ", "1999-12", "٢٠٢٦-١٠"],
)
def test_invalid_month_format_returns_422(client, bad_month):
    response = client.get("/debtors", params={"month": bad_month})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_missing_month_returns_422(client):
    assert client.get("/debtors").status_code == 422


# ----------------------------------------------------------------- дашборд
def test_dashboard_empty_database(client):
    response = client.get("/dashboard", params={"month": MONTH})
    assert response.status_code == 200
    assert response.json() == {
        "month": MONTH, "total_students": 0, "total_debtors": 0, "total_debt": 0, "total_received": 0,
    }


def test_dashboard_totals(client, create_student, add_payment):
    ali = create_student(name="Ali", monthly_fee=500000)
    madina = create_student(name="Madina", monthly_fee=400000)
    dilnoza = create_student(name="Dilnoza", monthly_fee=300000)
    add_payment(ali["id"], 300000, "2026-10-05")        # долг 200 000
    add_payment(dilnoza["id"], 350000, "2026-10-06")    # переплата, долга нет
    add_payment(madina["id"], 999999, "2026-09-30")     # другой месяц — не учитывается

    response = client.get("/dashboard", params={"month": MONTH})
    assert response.json() == {
        "month": MONTH,
        "total_students": 3,
        "total_debtors": 2,                 # Ali и Madina
        "total_debt": 200000 + 400000,
        "total_received": 300000 + 350000,  # переплата входит в полученные платежи
    }


def test_dashboard_invalid_month_returns_422(client):
    assert client.get("/dashboard", params={"month": "2026-13"}).status_code == 422
    assert client.get("/dashboard").status_code == 422
