"""Logging utilities for STDIO MCP servers.

MCP STDIO servers must keep stdout clean because it is used for JSON-RPC messages.
All logs must go to stderr.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any


_REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # postgresql://user:pass@host/db  -> postgresql://user:***@host/db
    (re.compile(r"(postgres(?:ql)?://[^:\s/]+:)([^@\s]+)(@)"), r"\1***\3"),
    # user=... password=... style fragments
    (re.compile(r"(\bpassword\s*=\s*)(\S+)", re.IGNORECASE), r"\1***"),
]


def _redact_text(text: str) -> str:
    """Redact secrets from free-form text."""
    redacted = text
    for pattern, repl in _REDACTION_PATTERNS:
        redacted = pattern.sub(repl, redacted)
    return redacted


class RedactingFormatter(logging.Formatter):
    """Logging formatter that redacts common secret patterns."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return _redact_text(msg)


def get_logger(name: str) -> logging.Logger:
    """Create or return a stderr-only logger configured for MCP STDIO safety."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(
        RedactingFormatter(fmt="%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    logger.addHandler(handler)
    logger.propagate = False
    return logger


def redact_for_audit(value: Any) -> Any:
    """Redact secrets from values being logged/audited.

    - Strings are pattern-redacted.
    - Dict/list are shallow-redacted recursively for common key names.
    """
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            lk = str(k).lower()
            if "password" in lk or "secret" in lk or "token" in lk or "key" in lk:
                out[k] = "***"
            else:
                out[k] = redact_for_audit(v)
        return out
    if isinstance(value, list):
        return [redact_for_audit(v) for v in value]
    return value
