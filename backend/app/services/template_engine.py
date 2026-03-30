"""
Template rendering engine with variable interpolation.

Supports dynamic variables like {{first_name}}, {{company}}, {{title}},
{{unsubscribe_url}}, {{sender_name}}, etc.
"""

import re
from typing import Any


# Variables available for interpolation
STANDARD_VARIABLES = {
    # Lead fields
    "first_name",
    "last_name",
    "full_name",
    "email",
    "phone",
    "company",
    "title",
    # Sender fields
    "sender_name",
    "sender_title",
    "sender_company",
    "sender_email",
    "sender_phone",
    # Compliance
    "unsubscribe_url",
    # Custom
    "custom_1",
    "custom_2",
    "custom_3",
}

VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def render_template(template_text: str, context: dict[str, Any]) -> str:
    """
    Replace all {{variable}} placeholders with values from context.

    Missing variables are replaced with empty string to avoid broken output.
    """

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        value = context.get(key, "")
        return str(value) if value is not None else ""

    return VARIABLE_PATTERN.sub(replacer, template_text)


def extract_variables(template_text: str) -> list[str]:
    """Extract all variable names used in a template."""
    return list(set(VARIABLE_PATTERN.findall(template_text)))


def build_lead_context(
    lead: Any,
    sender: dict[str, str] | None = None,
    unsubscribe_url: str | None = None,
    extras: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Build a template context dict from a Lead model instance.
    """
    ctx: dict[str, str] = {
        "first_name": getattr(lead, "first_name", ""),
        "last_name": getattr(lead, "last_name", ""),
        "full_name": f"{getattr(lead, 'first_name', '')} {getattr(lead, 'last_name', '')}".strip(),
        "email": getattr(lead, "email", ""),
        "phone": getattr(lead, "phone", "") or "",
        "company": getattr(lead, "company", ""),
        "title": getattr(lead, "title", ""),
    }

    if sender:
        ctx.update(
            {
                "sender_name": sender.get("name", ""),
                "sender_title": sender.get("title", ""),
                "sender_company": sender.get("company", "Gengyve USA"),
                "sender_email": sender.get("email", ""),
                "sender_phone": sender.get("phone", ""),
            }
        )

    if unsubscribe_url:
        ctx["unsubscribe_url"] = unsubscribe_url

    if extras:
        ctx.update(extras)

    return ctx


def validate_template(template_text: str) -> list[str]:
    """
    Return list of warnings/issues with a template.
    """
    warnings = []
    variables = extract_variables(template_text)

    unknown = [v for v in variables if v not in STANDARD_VARIABLES]
    if unknown:
        warnings.append(f"Unknown variables: {', '.join(unknown)}")

    if len(template_text) > 10000:
        warnings.append("Template exceeds 10,000 characters")

    return warnings
