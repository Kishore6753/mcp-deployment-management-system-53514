"""Tool implementations for MCP-database-server."""

from __future__ import annotations

import json
import re
from typing import Any

import asyncpg

from mcp_database_server.bounding import bound_rows, json_bytes, truncate_text
from mcp_database_server.config import Settings
from mcp_database_server.db import run_with_timeout, with_connection
from mcp_database_server.logging_utils import get_logger, redact_for_audit

logger = get_logger(__name__)

_SELECT_ONLY_RE = re.compile(r"^\s*select\b", re.IGNORECASE)


def _tool_text_result(text: str, max_bytes: int) -> dict:
    """Build a standard MCP tool result with bounded text content."""
    bounded, truncated = truncate_text(text, max_bytes=max_bytes)
    if truncated:
        bounded += "\n\n[Truncated due to output size limits.]"
    return {"content": [{"type": "text", "text": bounded}]}


def _tool_error(text: str, max_bytes: int) -> dict:
    """Build an MCP tool error result (isError=true) with bounded text."""
    res = _tool_text_result(text, max_bytes=max_bytes)
    res["isError"] = True
    return res


def _ensure_select_only(sql: str) -> None:
    """Reject any non-SELECT statement (defense-in-depth)."""
    if not _SELECT_ONLY_RE.match(sql):
        raise ValueError("Only SELECT queries are allowed for db_query in this server.")


async def _fetch_rows(conn: asyncpg.Connection, sql: str) -> list[dict[str, Any]]:
    """Fetch rows as JSON-serializable dicts."""
    records = await conn.fetch(sql)
    return [dict(r) for r in records]


async def tool_db_health_check(settings: Settings) -> dict:
    """Check DB connectivity and return minimal non-secret metadata."""
    async def _op(conn: asyncpg.Connection):
        row = await conn.fetchrow("SELECT version() AS version")
        version = str(row["version"]) if row and "version" in row else "unknown"
        return version

    try:
        version = await run_with_timeout(
            with_connection(settings, _op),
            timeout_seconds=settings.query_timeout_seconds,
        )
        payload = {"ok": True, "server_version": version}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        return _tool_text_result(text, max_bytes=settings.bounded_max_bytes())
    except Exception as e:
        logger.warning("db_health_check failed: %s", redact_for_audit(str(e)))
        return _tool_error("Database health check failed.", max_bytes=settings.bounded_max_bytes())


async def tool_db_list_schemas(settings: Settings, limit: int | None) -> dict:
    """List schemas with bounded output."""
    max_rows = settings.bounded_max_rows()
    if limit is not None:
        max_rows = min(max_rows, int(limit))

    async def _op(conn: asyncpg.Connection):
        sql = """
            SELECT schema_name
            FROM information_schema.schemata
            ORDER BY schema_name
        """
        rows = await _fetch_rows(conn, sql)
        return rows

    try:
        rows = await run_with_timeout(
            with_connection(settings, _op),
            timeout_seconds=settings.query_timeout_seconds,
        )

        rows, truncated_rows = bound_rows(rows, max_rows=max_rows)
        payload = {"schemas": [r["schema_name"] for r in rows]}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        result = _tool_text_result(text, max_bytes=settings.bounded_max_bytes())
        if truncated_rows:
            result["content"][0]["text"] += "\n\n[Row limit reached; results truncated.]"
        return result
    except Exception as e:
        logger.warning("db_list_schemas failed: %s", redact_for_audit(str(e)))
        return _tool_error("Failed listing schemas.", max_bytes=settings.bounded_max_bytes())


async def tool_db_list_tables(settings: Settings, schema: str, limit: int | None) -> dict:
    """List tables in a schema with bounded output."""
    max_rows = settings.bounded_max_rows()
    if limit is not None:
        max_rows = min(max_rows, int(limit))

    async def _op(conn: asyncpg.Connection):
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = $1 AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            schema,
        )
        return [dict(r) for r in rows]

    try:
        rows = await run_with_timeout(
            with_connection(settings, _op),
            timeout_seconds=settings.query_timeout_seconds,
        )
        rows, truncated_rows = bound_rows(rows, max_rows=max_rows)
        payload = {"schema": schema, "tables": [r["table_name"] for r in rows]}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        result = _tool_text_result(text, max_bytes=settings.bounded_max_bytes())
        if truncated_rows:
            result["content"][0]["text"] += "\n\n[Row limit reached; results truncated.]"
        return result
    except Exception as e:
        logger.warning("db_list_tables failed: %s", redact_for_audit(str(e)))
        return _tool_error("Failed listing tables.", max_bytes=settings.bounded_max_bytes())


async def tool_db_query(settings: Settings, sql: str, max_rows: int | None) -> dict:
    """Execute a read-only SELECT query with hard bounds."""
    try:
        _ensure_select_only(sql)
    except Exception as e:
        return _tool_error(str(e), max_bytes=settings.bounded_max_bytes())

    row_cap = settings.bounded_max_rows()
    if max_rows is not None:
        row_cap = min(row_cap, int(max_rows))

    async def _op(conn: asyncpg.Connection):
        rows = await _fetch_rows(conn, sql)
        return rows

    try:
        rows = await run_with_timeout(
            with_connection(settings, _op),
            timeout_seconds=settings.query_timeout_seconds,
        )
        rows, truncated_rows = bound_rows(rows, max_rows=row_cap)

        # Size bound (approx): if too large, truncate by rows until within max_bytes.
        max_bytes = settings.bounded_max_bytes()
        payload: dict[str, Any] = {"rows": rows, "rowCount": len(rows)}
        while len(json_bytes(payload)) > max_bytes and len(payload["rows"]) > 0:
            payload["rows"] = payload["rows"][: max(1, len(payload["rows"]) // 2)]
            payload["rowCount"] = len(payload["rows"])
            truncated_rows = True

        text = json.dumps(payload, ensure_ascii=False, indent=2)
        result = _tool_text_result(text, max_bytes=max_bytes)
        if truncated_rows:
            result["content"][0]["text"] += "\n\n[Results truncated due to row/size limits.]"
        return result
    except Exception as e:
        logger.warning(
            "db_query failed: %s",
            redact_for_audit({"error": str(e), "sql": sql}),
        )
        return _tool_error("Query failed.", max_bytes=settings.bounded_max_bytes())
