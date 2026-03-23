"""Utility to sanitize secrets from error messages and logs."""

import re

# Patterns that match common secret formats in error messages
_SECRET_PATTERNS = [
    # API keys (various formats: sk-, gsk_, xai-, Bearer tokens)
    (re.compile(r"(sk-[a-zA-Z0-9]{10,})[a-zA-Z0-9]*"), r"\1***"),
    (re.compile(r"(gsk_[a-zA-Z0-9]{10,})[a-zA-Z0-9]*"), r"\1***"),
    (re.compile(r"(xai-[a-zA-Z0-9]{10,})[a-zA-Z0-9]*"), r"\1***"),
    (re.compile(r"(key-[a-zA-Z0-9]{10,})[a-zA-Z0-9]*"), r"\1***"),
    # Bearer tokens in error messages
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9._\-]+", re.IGNORECASE), r"\1[REDACTED]"),
    # Generic API key patterns (long hex/alphanumeric strings following key= or api_key=)
    (re.compile(r"(api[_-]?key[=:]\s*)['\"]?[a-zA-Z0-9_\-]{20,}['\"]?", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(secret[=:]\s*)['\"]?[a-zA-Z0-9_\-]{10,}['\"]?", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(password[=:]\s*)['\"]?[^\s'\"]{1,}['\"]?", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(token[=:]\s*)['\"]?[a-zA-Z0-9._\-]{20,}['\"]?", re.IGNORECASE), r"\1[REDACTED]"),
    # AWS keys
    (re.compile(r"(AKIA[A-Z0-9]{12,})[A-Z0-9]*"), r"\1***"),
    # Connection strings with passwords
    (re.compile(r"(://[^:]+:)[^@]+(@)"), r"\1[REDACTED]\2"),
    # JWT tokens (3 base64 segments separated by dots)
    (re.compile(r"eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"), "[REDACTED_JWT]"),
]


def sanitize_error(error: BaseException | str) -> str:
    """
    Sanitize an error message by redacting known secret patterns.

    Accepts an exception or string. Returns a safe string suitable for logging.
    """
    msg = str(error)
    for pattern, replacement in _SECRET_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg
