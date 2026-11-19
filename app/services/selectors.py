"""Canonicalize recorder selectors so they behave consistently at runtime."""

from __future__ import annotations

import re

LEGACY_LABEL_RE = re.compile(r'^label\s*=\s*"?([^"]+)"?\s*$', re.IGNORECASE)
INTERNAL_LABEL_RE = re.compile(r'^internal:label="([^"]+)"i$')
ROLE_NAME_PREFIX_RE = re.compile(
    r'^(role\s*=\s*[a-zA-Z][\w-]*\s*\[\s*name\s*=\s*)(["\'])(.*)$',
    re.DOTALL,
)

GET_BY_LABEL_PREFIX = "getByLabel:"


def canonicalize_selector(selector: str | None) -> str | None:
    """Return a selector that matches the way Playwright computes accessible names.

    Recorders historically emitted ``role=link[name="PRACTICE"]`` based on rendered
    text (CSS text-transform). Playwright only matches ``name`` case-sensitively
    unless the ``i`` flag is present, so those selectors never resolve. Adding the
    flag keeps the match exact while making it case-insensitive.
    """
    if not selector:
        return selector

    legacy = LEGACY_LABEL_RE.match(selector)
    if legacy:
        return f"{GET_BY_LABEL_PREFIX}{legacy.group(1).strip()}"

    internal = INTERNAL_LABEL_RE.match(selector)
    if internal:
        return f"{GET_BY_LABEL_PREFIX}{internal.group(1).strip()}"

    role = ROLE_NAME_PREFIX_RE.match(selector)
    if not role:
        return selector

    prefix, quote, remainder = role.groups()
    remainder = remainder.strip()
    if not remainder.endswith("]"):
        return selector

    value = remainder[:-1].rstrip()
    if value and value[-1] in "iIsS":
        value = value[:-1].rstrip()

    if not value.endswith(quote):
        return selector
    if value.endswith("\\" + quote):
        return selector
    if remainder[:-1].rstrip()[-1:] in "iIsS":
        return selector

    return f"{prefix}{quote}{value}i]"
