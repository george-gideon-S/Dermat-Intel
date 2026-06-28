"""Tiny shared formatting helpers so every tab renders None/NaN consistently."""
from __future__ import annotations


def is_missing(v) -> bool:
    return v is None or (isinstance(v, float) and v != v)


def rating(v) -> str:
    return f"{float(v):.1f}" if not is_missing(v) else "—"


def reviews(v) -> str:
    return str(int(v)) if not is_missing(v) else "0"


def text(v, default: str = "—") -> str:
    if is_missing(v):
        return default
    s = str(v).strip()
    return s or default
