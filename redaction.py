"""Masks sensitive details (emails, phone numbers, amounts, long numbers, secrets) for roles
that are not allowed to see Restricted material. Plain code, no AI."""
import re

from config import ROLES

PATTERNS = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email hidden]"),
    ("amount", re.compile(r"(?:\bRs\.?|\bINR|\u20b9)\s?\d[\d,]*(?:\.\d+)?", re.IGNORECASE), "[amount hidden]"),
    ("phone", re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[phone hidden]"),
    ("phone", re.compile(r"\+\d[\d\s-]{8,}\d"), "[phone hidden]"),
    ("number", re.compile(r"(?<!\d)\d{12,}(?!\d)"), "[number hidden]"),
    ("secret", re.compile(r"\b(?:sk|pk|AIza)[-_A-Za-z0-9]{20,}\b"), "[secret hidden]"),
]

FIELDS = ("statement", "subject", "value", "quote")


def applies_to(role):
    """Redaction applies to every role that cannot see Restricted material."""
    return "Restricted" not in ROLES.get(role, [])


def redact(text):
    """Return (masked_text, number_of_replacements)."""
    text = "" if text is None else str(text)
    total = 0
    for _name, pattern, mask in PATTERNS:
        text, n = pattern.subn(mask, text)
        total += n
    return text, total


def redact_claim(claim):
    """Return (copy_of_claim_with_masked_text, number_of_replacements)."""
    masked = dict(claim)
    total = 0
    for field in FIELDS:
        if masked.get(field):
            masked[field], n = redact(masked[field])
            total += n
    return masked, total