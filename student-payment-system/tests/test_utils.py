"""Чистая логика без БД: разбор месяца и расчёт долга."""

from datetime import date

import pytest

from app.utils import calculate_debt, parse_month


def test_parse_month_regular():
    rng = parse_month("2026-10")
    assert rng.label == "2026-10"
    assert rng.start == date(2026, 10, 1)
    assert rng.end == date(2026, 11, 1)


def test_parse_month_december_rolls_to_next_year():
    rng = parse_month("2026-12")
    assert rng.start == date(2026, 12, 1)
    assert rng.end == date(2027, 1, 1)


def test_parse_month_february_leap_year():
    assert parse_month("2028-02").end == date(2028, 3, 1)


@pytest.mark.parametrize(
    "value",
    ["2026-13", "2026-00", "2026-1", "26-10", "2026/10", "2026-10-01", "abcd", "", " 2026-10",
     "2026-10 ", "1999-12", "2101-01", "٢٠٢٦-١٠"],
)
def test_parse_month_rejects_bad_values(value):
    with pytest.raises(ValueError):
        parse_month(value)


@pytest.mark.parametrize(
    ("fee", "paid", "expected"),
    [(500000, 0, 500000), (500000, 300000, 200000), (500000, 500000, 0), (500000, 700000, 0), (0, 0, 0)],
)
def test_calculate_debt(fee, paid, expected):
    assert calculate_debt(fee, paid) == expected
