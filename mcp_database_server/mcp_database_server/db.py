"""PostgreSQL connectivity for MCP-database-server.

Security/safety requirements (per MCP-development-standards):
- Never print connection strings or credentials.
- Default DB connection comes from the repo database/db_connection.txt, with env override.
- Enforce query/statement timeouts in two layers:
  1) application timeout via asyncio.wait_for
  2) PostgreSQL statement_timeout via SET LOCAL inside a transaction
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

import asyncpg

from mcp_database_server.config import Settings
from mcp_database_server.logging_utils import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def _parse_connection_file(text: str) -> str | None:
    """Extract a PostgreSQL URI from a connection file line.

    Supported:
    - 'psql postgresql://...'
    - 'postgresql://...'
    - 'postgres://...'
    """
    line = text.strip()
    if not line:
        return None
    if line.startswith("psql "):
        line = line[len("psql ") :].strip()
    if line.startswith("postgresql://") or line.startswith("postgres://"):
        return line
    return None


def _load_repo_connection_url() -> str | None:
    """Load the canonical repo DB connection URL from `../database/db_connection.txt`.

    Repository layout (per work item):
      - MCP server container: mcp-deployment-management-system-53514/mcp_database_server/...
      - Database container:   mcp-deployment-management-system-53515/database/db_connection.txt

    We resolve this path relative to this file to avoid relying on process CWD.
    """
    # This file is at: .../mcp-deployment-management-system-53514/mcp_database_server/mcp_database_server/db.py
    # Go up 3 levels -> mcp-deployment-management-system-53514, then sibling workspace -> mcp-deployment-management-system-53515/database/db_connection.txt
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root.parent / "mcp-deployment-management-system-53515" / "database" / "db_connection.txt"
    if not candidate.exists():
        return None
    try:
        content = candidate.read_text(encoding="utf-8")
        return _parse_connection_file(content)
    except Exception:
        # Don't log file contents or connection strings.
        logger.warning("Failed reading repo db connection file: %s", str(candidate))
        return None


def build_postgres_dsn(settings: Settings) -> str:
    """Build a PostgreSQL DSN from Settings.

    Priority:
    1) POSTGRES_URL (env override; recommended in production)
    2) repo database/db_connection.txt (default)
    3) individual POSTGRES_* parts
    """
    if settings.postgres_url:
        return settings.postgres_url

    repo = _load_repo_connection_url()
    if repo:
        return repo

    # Individual parts: require user, password, db
    if not settings.postgres_user or not settings.postgres_password or not settings.postgres_db:
        raise ValueError(
            "Database configuration missing. Provide POSTGRES_URL or POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB."
        )

    return (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


async def run_with_timeout(coro: Awaitable[T], timeout_seconds: int) -> T:
    """Run a coroutine with timeout, raising asyncio.TimeoutError on expiry."""
    return await asyncio.wait_for(coro, timeout=timeout_seconds)


async def with_connection(settings: Settings, fn: Callable[[asyncpg.Connection], Awaitable[T]]) -> T:
    """Run a coroutine with a short-lived connection.

    Using per-call connection keeps implementation simple and safe.
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


async def with_statement_timeout(
    conn: asyncpg.Connection, timeout_seconds: int, fn: Callable[[asyncpg.Connection], Awaitable[T]]
) -> T:
    """Run an operation within a transaction with a PostgreSQL statement_timeout set.

    This defends against long-running queries even if the client-side timeout is not reached
    due to driver/network conditions.
    """
    timeout_ms = max(1, int(timeout_seconds * 1000))
    async with conn.transaction():
        # SET LOCAL only affects the current transaction.
        await conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
        # Also cap idle-in-transaction to avoid holding locks indefinitely.
        await conn.execute(f"SET LOCAL idle_in_transaction_session_timeout = {timeout_ms}")
        return await fn(conn)
