import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Tuple


def normalize_phone(raw_phone: Any) -> Tuple[Optional[str], Optional[str]]:
    """Normalizes an Indian phone number to +91XXXXXXXXXX format.
    Returns (normalized_phone, error_message).
    """
    if raw_phone is None:
        return None, "Phone number is missing"

    # Convert to string and strip whitespace
    s = str(raw_phone).strip()
    if not s or s.lower() == "nan":
        return None, "Phone number is empty"

    # Remove formatting characters: spaces, hyphens, parentheses, dots
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", s)

    # Handle leading + or 00
    if cleaned.startswith("+91"):
        digits = cleaned[3:]
    elif cleaned.startswith("0091"):
        digits = cleaned[4:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        digits = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        digits = cleaned[1:]
    else:
        digits = cleaned

    # A valid Indian mobile number consists of 10 digits, typically starting with 6, 7, 8, or 9
    if not digits.isdigit():
        return None, f"Phone contains invalid characters: '{s}'"

    if len(digits) != 10:
        return None, f"Invalid phone number length ({len(digits)} digits): '{s}'"

    if digits[0] not in "6789":
        return None, f"Invalid Indian phone starting digit '{digits[0]}' in '{s}'"

    return f"+91{digits}", None


def normalize_money(raw_amount: Any) -> Tuple[Optional[Decimal], Optional[str]]:
    """Normalizes a currency/amount string to Decimal(2).
    Returns (Decimal, error_message).
    """
    if raw_amount is None:
        return None, "Amount is missing"

    s = str(raw_amount).strip()
    if not s or s.lower() == "nan":
        return None, "Amount is empty"

    # Strip currency symbols (₹, Rs, Rs., INR, $) and commas
    cleaned = re.sub(r"[₹\$,]|(rs\.?)|(inr)", "", s, flags=re.IGNORECASE).strip()

    # Handle 'K' / 'k' suffix if present (e.g. 25k -> 25000)
    multiplier = Decimal("1")
    if cleaned.lower().endswith("k"):
        multiplier = Decimal("1000")
        cleaned = cleaned[:-1].strip()

    try:
        val = Decimal(cleaned) * multiplier
        val = val.quantize(Decimal("0.01"))
        if val < 0:
            return None, f"Amount cannot be negative: '{s}'"
        return val, None
    except (InvalidOperation, ValueError):
        return None, f"Invalid financial amount: '{s}'"


def normalize_date(raw_date: Any) -> Tuple[Optional[date], Optional[str]]:
    """Normalizes various date formats into an ISO date object.
    Supports: DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY, YYYY/MM/DD, datetime/date objects, Excel serial dates.
    Returns (date, error_message).
    """
    if raw_date is None:
        return None, None  # Optional field

    if isinstance(raw_date, date) and not isinstance(raw_date, datetime):
        return raw_date, None

    if isinstance(raw_date, datetime):
        return raw_date.date(), None

    s = str(raw_date).strip()
    if not s or s.lower() == "nan" or s.lower() == "nat":
        return None, None

    # Supported string date formats
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date(), None
        except ValueError:
            continue

    # Attempt Excel float serial date (days since 1899-12-30)
    try:
        serial = float(s)
        if 20000 <= serial <= 70000:  # Roughly year 1954 to 2091
            from datetime import timedelta
            dt = datetime(1899, 12, 30) + timedelta(days=serial)
            return dt.date(), None
    except ValueError:
        pass

    return None, f"Unrecognized date format: '{s}'"
