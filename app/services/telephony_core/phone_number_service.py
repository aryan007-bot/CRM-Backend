import re
from typing import Optional, Tuple


class PhoneNumberService:
    """Centralized phone number validation and normalization service."""

    # E.164 standard regex: + followed by 1 to 15 digits
    E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")

    @classmethod
    def normalize_phone(cls, raw_phone: str, default_country_code: str = "+91") -> Tuple[bool, str, Optional[str]]:
        """Normalizes any phone string into E.164 format.
        
        Returns:
            Tuple of (is_valid: bool, normalized_phone: str, error_message: Optional[str])
        """
        if not raw_phone:
            return False, "", "Phone number cannot be empty"

        cleaned = re.sub(r"[\s\-\(\)\.]", "", raw_phone.strip())

        # If already starts with +, validate length
        if cleaned.startswith("+"):
            if not cls.E164_REGEX.match(cleaned):
                return False, cleaned, "Invalid E.164 phone format"
            return True, cleaned, None

        # Strip leading trunk zeros (e.g., 09213960958 -> 9213960958)
        if cleaned.startswith("0") and len(cleaned) == 11:
            cleaned = cleaned[1:]

        # Indian 10-digit mobile number handling
        if len(cleaned) == 10 and cleaned.isdigit():
            normalized = f"{default_country_code}{cleaned}"
            return True, normalized, None

        # If 12 digits starting with 91
        if len(cleaned) == 12 and cleaned.startswith("91") and cleaned.isdigit():
            normalized = f"+{cleaned}"
            return True, normalized, None

        # Generic digit string
        if cleaned.isdigit() and 7 <= len(cleaned) <= 15:
            normalized = f"+{cleaned}"
            return True, normalized, None

        return False, cleaned, f"Invalid phone number format: {raw_phone}"

    @classmethod
    def mask_phone(cls, phone: str) -> str:
        """Masks phone number for safe logging (e.g., +919213960958 -> +919213***958)."""
        if not phone or len(phone) < 8:
            return "***"
        prefix = phone[:6]
        suffix = phone[-3:]
        return f"{prefix}***{suffix}"
