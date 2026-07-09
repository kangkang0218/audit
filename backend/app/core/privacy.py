from __future__ import annotations

import re
from typing import Any

ID_CARD = re.compile(r"(?<![0-9A-Za-z])(\d{6})\d{8}([0-9Xx]{4})(?![0-9A-Za-z])")
LONG_ACCOUNT = re.compile(r"(?<!\d)(\d{4})\d{8,15}(\d{4})(?!\d)")
MOBILE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
FLEX_ID_CARD = re.compile(
    r"(?<!\d)((?:\d\s*){6})(?:\d\s*){8}((?:[0-9Xx]\s*){4})(?!\d)"
)
FLEX_LONG_ACCOUNT = re.compile(
    r"(?<!\d)((?:\d\s*){4})(?:\d\s*){8,15}((?:\d\s*){4})(?!\d)"
)
FLEX_MOBILE = re.compile(
    r"(?<!\d)((?:1\s*[3-9]\s*\d\s*))(?:\d\s*){4}((?:\d\s*){4})(?!\d)"
)


def _compact_group(match: re.Match[str], stars: str) -> str:
    left = re.sub(r"\s+", "", match.group(1))
    right = re.sub(r"\s+", "", match.group(2))
    return f"{left}{stars}{right}"


def mask_sensitive_text(value: str) -> str:
    value = FLEX_ID_CARD.sub(lambda match: _compact_group(match, "********"), value)
    value = ID_CARD.sub(r"\1********\2", value)
    value = FLEX_LONG_ACCOUNT.sub(lambda match: _compact_group(match, "********"), value)
    value = LONG_ACCOUNT.sub(r"\1********\2", value)
    value = FLEX_MOBILE.sub(lambda match: _compact_group(match, "****"), value)
    return MOBILE.sub(r"\1****\2", value)


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return mask_sensitive_text(value)
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def mask_identifier(value: str | None) -> str | None:
    if not value:
        return value
    compact = re.sub(r"\s+", "", value)
    if len(compact) <= 8:
        return "*" * len(compact)
    return f"{compact[:4]}{'*' * max(4, len(compact) - 8)}{compact[-4:]}"
