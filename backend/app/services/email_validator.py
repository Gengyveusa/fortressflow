"""Email and phone validation helpers."""

import re

import phonenumbers
from email_validator import EmailNotValidError, validate_email


def is_valid_email(email: str) -> bool:
    """Return True if the email address passes RFC-5322 validation."""
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def is_valid_phone(phone: str) -> bool:
    """Return True if phone is a parseable and valid E.164 number."""
    if not phone:
        return False
    try:
        parsed = phonenumbers.parse(phone, None)
        return phonenumbers.is_valid_number(parsed)
    except phonenumbers.NumberParseException:
        return False


def normalize_email(email: str) -> str:
    """Return lowercase-stripped email, or raise ValueError if invalid."""
    try:
        result = validate_email(email, check_deliverability=False)
        return result.normalized
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc


def normalize_phone(phone: str) -> str:
    """Return E.164 formatted phone number, or raise ValueError if invalid."""
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException as exc:
        raise ValueError(f"Cannot parse phone: {exc}") from exc
