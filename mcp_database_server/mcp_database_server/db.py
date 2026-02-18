"""PostgreSQL connectivity for MCP-database-server."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

from mcp_database_server.config import Settings
from mcp_database_server.logging_utils import get_logger

logger = get_logger(__name__)


def _parse_connection_file(text: str) -> str | None:
    """Extract a PostgreSQL URI from a connection file line.

    Supported:
    - 'psql postgresql://...'
    - 'postgresql://...'
    """
    line = text.strip()
    if not line:
        return None
    if line.startswith("psql "):
        line = line[len("psql ") :].strip()
    if line.startswith("postgresql://") or line.startswith("postgres://"):
        return line
    return None


def _load_local_connection_url() -> str | None:
    """Load optional local dev connection url from config/db_connection.txt."""
    path = Path(__file__).resolve().parent / "config" / "db_connection.txt"
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        return _parse_connection_file(content)
    except Exception:
        # Don't log file contents; just note failure.
        logger.warning("Failed reading local db connection file: %s", str(path))
        return None


def build_postgres_dsn(settings: Settings) -> str:
    """Build a PostgreSQL DSN from Settings.

    Priority:
    1) POSTGRES_URL
    2) local config/db_connection.txt (optional convenience)
    3) individual POSTGRES_* parts
    """
    if settings.postgres_url:
        return settings.postgres_url

    local = _load_local_connection_url()
    if local:
        return local

    # Individual parts: require user, password, db
    if not settings.postgres_user or not settings.postgres_password or not settings.postgres_db:
        raise ValueError(
            "Database configuration missing. Provide POSTGRES_URL or POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB."
        )

    return (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


async def with_connection(settings: Settings, fn):
    """Run a coroutine with a short-lived connection.

    Using per-call connection keeps scaffold simple; later steps can introduce pooling.
    """
    dsn = build_postgres_dsn(settings)
    timeout = settings.query_timeout_seconds
    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(dsn, timeout=timeout)
        return await fn(conn)
    finally:
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                logger.warning("Failed closing DB connection cleanly.")


async def run_with_timeout(coro, timeout_seconds: int):
    """Run a coroutine with timeout, raising asyncio.TimeoutError on expiry."""
    return await asyncio.wait_for(coro, timeout=timeout_seconds)
