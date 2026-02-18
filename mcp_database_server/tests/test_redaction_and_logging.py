from __future__ import annotations

import logging
import sys

from mcp_database_server.logging_utils import RedactingFormatter, get_logger, redact_for_audit


def test_redact_for_audit_masks_common_secret_keys_and_uris() -> None:
    value = {
        "password": "supersecret",
        "api_token": "tok_123",
        "nested": {"secret": "s3cr3t"},
        "ok": "postgresql://user:pass@host:5432/db",
        "other": ["password=hunter2", "no-secret-here"],
    }
    redacted = redact_for_audit(value)

    assert redacted["password"] == "***"
    assert redacted["api_token"] == "***"
    assert redacted["nested"]["secret"] == "***"
    assert redacted["ok"].startswith("postgresql://user:***@host")
    assert redacted["other"][0].lower().startswith("password=***")


def test_redacting_formatter_masks_postgres_password_in_message() -> None:
    fmt = RedactingFormatter(fmt="%(levelname)s %(message)s")
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="connecting to postgresql://u:p@h/db",
        args=(),
        exc_info=None,
    )
    rendered = fmt.format(record)
    assert "postgresql://u:***@h/db" in rendered
    assert "postgresql://u:p@h/db" not in rendered


def test_get_logger_writes_to_stderr_only() -> None:
    logger = get_logger("mcp_database_server.tests.stderr_only")
    assert logger.propagate is False
    assert logger.handlers, "Expected at least one handler"
    # All handlers should be StreamHandler -> stderr (or wrapper that contains stderr)
    for h in logger.handlers:
        assert isinstance(h, logging.StreamHandler)
        assert h.stream is sys.stderr
