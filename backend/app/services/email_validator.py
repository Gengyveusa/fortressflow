"""Email and phone validation helpers."""

import re

import phonenumbers
from email_validator import EmailNotValidError, validate_email


# Common disposable email domains
DISPOSABLE_DOMAINS: frozenset[str] = frozenset({
    "10minutemail.com", "guerrillamail.com", "guerrillamail.info",
    "guerrillamailblock.com", "grr.la", "guerrillamail.net",
    "guerrillamail.org", "guerrillamail.de", "sharklasers.com",
    "guerrillamailblock.com", "tempmail.com", "temp-mail.org",
    "throwaway.email", "mailinator.com", "maildrop.cc",
    "dispostable.com", "yopmail.com", "yopmail.fr", "yopmail.net",
    "trashmail.com", "trashmail.net", "trashmail.me", "trashmail.org",
    "mailnesia.com", "mailnull.com", "mailexpire.com",
    "tempail.com", "tempr.email", "temp-mail.io",
    "fakeinbox.com", "sharklasers.com", "guerrillamail.info",
    "getnada.com", "mailsac.com", "harakirimail.com",
    "discard.email", "discardmail.com", "discardmail.de",
    "33mail.com", "maildrop.cc", "mailcatch.com",
    "mailforspam.com", "safetymail.info", "trashymail.com",
    "trashymail.net", "wegwerfmail.de", "wegwerfmail.net",
    "jetable.org", "spamgourmet.com", "mytrashmail.com",
    "kasmail.com", "inboxalias.com", "spamfree24.org",
    "mailzilla.com", "meltmail.com", "spaml.com",
    "bugmenot.com", "deadaddress.com", "despam.it",
    "devnullmail.com", "dodgit.com", "emailgo.de",
    "emailtemporario.com.br", "ephemail.net", "filzmail.com",
    "getairmail.com", "gishpuppy.com", "grandmamail.com",
    "haltospam.com", "hatespam.org", "hidemail.de",
    "imails.info", "incognitomail.org", "jetable.com",
    "klassmaster.com", "kurzepost.de", "lhsdv.com",
    "link2mail.net", "litedrop.com", "lookugly.com",
    "lortemail.dk", "lr78.com", "mailbidon.com",
    "mailblocks.com", "mailcatch.com", "maileater.com",
    "mailexpire.com", "mailin8r.com", "mailinator.net",
    "mailme.ir", "mailme.lv", "mailmoat.com",
    "mailnator.com", "mailshell.com", "mailsiphon.com",
    "mailslite.com", "mailtemp.info", "mailzilla.org",
    "mintemail.com", "mmmmail.com", "mobi.web.id",
    "mt2015.com", "mytempemail.com", "nepwk.com",
    "nobulk.com", "noclickemail.com", "nogmailspam.info",
    "nomail.xl.cx", "nomail2me.com", "nospam.ze.tc",
    "nospamfor.us", "nowmymail.com", "objectmail.com",
    "obobbo.com", "odaymail.com", "oneoffemail.com",
    "owlpic.com", "pjjkp.com", "proxymail.eu",
    "punkass.com", "putthisinyouremail.com", "reallymymail.com",
    "recode.me", "regbypass.com", "rmqkr.net",
})

# Role-based email prefixes — these are generic addresses, not individual contacts
ROLE_PREFIXES: frozenset[str] = frozenset({
    "info", "admin", "support", "noreply", "no-reply", "no_reply",
    "webmaster", "postmaster", "hostmaster", "abuse",
    "sales", "marketing", "contact", "help", "helpdesk",
    "billing", "finance", "hr", "jobs", "careers",
    "press", "media", "team", "office", "hello",
    "feedback", "enquiries", "inquiries", "reception",
    "security", "privacy", "legal", "compliance",
})


def is_valid_email(email: str) -> bool:
    """Return True if the email address passes RFC-5322 validation."""
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def is_disposable_email(email: str) -> bool:
    """Return True if the email uses a known disposable domain."""
    try:
        domain = email.rsplit("@", 1)[1].lower()
        return domain in DISPOSABLE_DOMAINS
    except (IndexError, AttributeError):
        return False


def is_role_based_email(email: str) -> bool:
    """Return True if the email is a role-based address (info@, support@, etc.)."""
    try:
        local_part = email.rsplit("@", 1)[0].lower()
        return local_part in ROLE_PREFIXES
    except (IndexError, AttributeError):
        return False


def check_mx_record(domain: str) -> bool:
    """Stub for MX record check — always returns True.

    In production, integrate with dns.resolver to verify the domain
    has valid MX records before sending.
    """
    return bool(domain)


def validate_email_full(email: str) -> tuple[bool, str]:
    """Full email validation: RFC check + disposable + role-based.

    Returns (is_valid, reason) tuple.
    """
    if not is_valid_email(email):
        return False, "invalid_email_format"
    if is_disposable_email(email):
        return False, "disposable_email_domain"
    if is_role_based_email(email):
        return False, "role_based_email"
    return True, "valid"


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
