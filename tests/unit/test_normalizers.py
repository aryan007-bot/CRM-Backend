from datetime import date
from decimal import Decimal

from app.import_engine.normalizer import (
    normalize_date,
    normalize_money,
    normalize_phone,
)


def test_normalize_phone_valid_cases():
    cases = [
        ("9876543210", "+919876543210"),
        ("+91 98765 43210", "+919876543210"),
        ("+91-98765-43210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("(+91) 8765432109", "+918765432109"),
        ("7123456789", "+917123456789"),
        ("6987654321", "+916987654321"),
    ]
    for raw, expected in cases:
        norm, err = normalize_phone(raw)
        assert err is None, f"Failed for '{raw}': {err}"
        assert norm == expected


def test_normalize_phone_invalid_cases():
    invalid_cases = [
        "",
        None,
        "12345",              # Too short
        "9876543210123",      # Too long
        "abc1234567",         # Non numeric
        "1876543210",         # Starts with 1 (not standard Indian mobile)
        "5876543210",         # Starts with 5
    ]
    for raw in invalid_cases:
        norm, err = normalize_phone(raw)
        assert norm is None
        assert err is not None


def test_normalize_money_valid_cases():
    cases = [
        ("₹25,000", Decimal("25000.00")),
        ("25000.50", Decimal("25000.50")),
        ("Rs. 1,50,000.75", Decimal("150000.75")),
        ("INR 5000", Decimal("5000.00")),
        ("25k", Decimal("25000.00")),
        ("10.5k", Decimal("10500.00")),
        (45000, Decimal("45000.00")),
    ]
    for raw, expected in cases:
        val, err = normalize_money(raw)
        assert err is None, f"Failed for '{raw}': {err}"
        assert val == expected


def test_normalize_money_invalid_cases():
    invalid_cases = [
        "",
        None,
        "not_money",
        "-5000",              # Negative amount rejected
        "₹ -250",
    ]
    for raw in invalid_cases:
        val, err = normalize_money(raw)
        assert val is None
        assert err is not None


def test_normalize_date_valid_cases():
    cases = [
        ("2026-10-15", date(2026, 10, 15)),
        ("15/10/2026", date(2026, 10, 15)),
        ("15-10-2026", date(2026, 10, 15)),
        ("2026/10/15", date(2026, 10, 15)),
        (date(2026, 10, 15), date(2026, 10, 15)),
    ]
    for raw, expected in cases:
        val, err = normalize_date(raw)
        assert err is None, f"Failed for '{raw}': {err}"
        assert val == expected


def test_normalize_date_optional_and_invalid():
    # Empty is allowed (optional field)
    val, err = normalize_date(None)
    assert val is None and err is None

    val, err = normalize_date("")
    assert val is None and err is None

    # Invalid date string
    val, err = normalize_date("invalid_date_str")
    assert val is None
    assert err is not None
