"""Utilities to bound tool outputs (rows and bytes)."""

from __future__ import annotations

import json
from typing import Any


def truncate_text(text: str, max_bytes: int) -> tuple[str, bool]:
    """Truncate UTF-8 text to fit within max_bytes."""
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text, False
    truncated = data[:max_bytes]
    # Ensure valid utf-8 by dropping invalid tail
    out = truncated.decode("utf-8", errors="ignore")
    return out, True


def json_bytes(obj: Any) -> bytes:
    """Stable JSON encoding for size estimation."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def bound_rows(rows: list[dict[str, Any]], max_rows: int) -> tuple[list[dict[str, Any]], bool]:
    """Cap row list length."""
    if len(rows) <= max_rows:
        return rows, False
    return rows[:max_rows], True
