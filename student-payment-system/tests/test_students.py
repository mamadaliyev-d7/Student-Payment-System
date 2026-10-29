import pytest

VALID = {"name": "Ali", "phone": "+998901234567", "group_name": "Python Beginner", "monthly_fee": 500000}


def test_create_student(client):
    response = client.post("/students", json=VALID)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert {k: body[k] for k in VALID} == VALID


def test_list_students_empty_database(client):
    response = client.get("/students")
    assert response.status_code == 200
    assert response.json() == []


def test_list_and_get_student(client, create_student):
    first = create_student(name="Ali")
    second = create_student(name="Madina", phone="+998931234567", group_name="Frontend", monthly_fee=400000)

    listed = client.get("/students").json()
    assert [s["id"] for s in listed] == [first["id"], second["id"]]

    single = client.get(f"/students/{second['id']}")
    assert single.status_code == 200
    assert single.json() == second


def test_get_missing_student_returns_404(client):
    response = client.get("/students/999")
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


@pytest.mark.parametrize("bad_id", ["0", "-1", "abc", "1.5"])
def test_invalid_student_id_returns_422(client, bad_id):
    assert client.get(f"/students/{bad_id}").status_code == 422


def test_patch_student_changes_only_given_fields(client, create_student):
    student = create_student()
    response = client.patch(f"/students/{student['id']}", json={"monthly_fee": 600000, "group_name": "Advanced"})
    assert response.status_code == 200
    body = response.json()
    assert body["monthly_fee"] == 600000
    assert body["group_name"] == "Advanced"
    assert body["name"] == student["name"]
    assert body["phone"] == student["phone"]
    assert client.get(f"/students/{student['id']}").json() == body


def test_patch_missing_student_returns_404(client):
    assert client.patch("/students/999", json={"name": "X"}).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{}, {"name": None}, {"name": "   "}, {"monthly_fee": -1}, {"monthly_fee": None}, {"phone": "abc"}],
)
def test_patch_rejects_invalid_data(client, create_student, payload):
    student = create_student()
    assert client.patch(f"/students/{student['id']}", json=payload).status_code == 422
    assert client.get(f"/students/{student['id']}").json() == student  # данные не изменились


def test_delete_student(client, create_student):
    student = create_student()
    response = client.delete(f"/students/{student['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/students/{student['id']}").status_code == 404
    assert client.get("/students").json() == []


def test_delete_missing_student_returns_404(client):
    assert client.delete("/students/999").status_code == 404


def test_delete_student_removes_their_payments_only(client, create_student, add_payment):
    ali = create_student(name="Ali")
    madina = create_student(name="Madina")
    add_payment(ali["id"], 100000, "2026-10-01")
    add_payment(ali["id"], 50000, "2026-10-02")
    keep = add_payment(madina["id"], 200000, "2026-10-03")

    assert client.delete(f"/students/{ali['id']}").status_code == 204

    assert client.get(f"/students/{ali['id']}/payments").status_code == 404
    remaining = client.get("/payments").json()
    assert [p["id"] for p in remaining] == [keep["id"]]


def test_deleted_student_id_is_not_reused(client, create_student):
    first = create_student()
    client.delete(f"/students/{first['id']}")
    second = create_student()
    assert second["id"] != first["id"]


@pytest.mark.parametrize(
    "override",
    [
        {"monthly_fee": -1},
        {"monthly_fee": 500.5},
        {"monthly_fee": "abc"},
        {"monthly_fee": 10**13},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 101},
        {"phone": ""},
        {"phone": "abc"},
        {"phone": "12"},
        {"phone": "+998 90 abc"},
        {"group_name": ""},
        {"group_name": "  "},
    ],
)
def test_create_student_validation(client, override):
    response = client.post("/students", json={**VALID, **override})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert client.get("/students").json() == []


@pytest.mark.parametrize("missing", ["name", "phone", "group_name", "monthly_fee"])
def test_create_student_requires_all_fields(client, missing):
    payload = {k: v for k, v in VALID.items() if k != missing}
    assert client.post("/students", json=payload).status_code == 422


def test_create_student_without_body_returns_422(client):
    assert client.post("/students").status_code == 422


def test_zero_fee_is_allowed(client):
    response = client.post("/students", json={**VALID, "monthly_fee": 0})
    assert response.status_code == 201
    assert response.json()["monthly_fee"] == 0


def test_text_fields_are_trimmed(client):
    response = client.post("/students", json={**VALID, "name": "  Ali  ", "group_name": " Python "})
    assert response.status_code == 201
    assert response.json()["name"] == "Ali"
    assert response.json()["group_name"] == "Python"


def test_sql_injection_string_is_stored_literally(client):
    evil = "Robert'); DROP TABLE students;--"
    response = client.post("/students", json={**VALID, "name": evil})
    assert response.status_code == 201
    listed = client.get("/students").json()
    assert [s["name"] for s in listed] == [evil]
