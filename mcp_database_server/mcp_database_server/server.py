"""MCP STDIO server implementation for MCP-database-server.

This module intentionally avoids writing anything to stdout except MCP protocol
traffic produced by the MCP SDK.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_database_server.config import Settings
from mcp_database_server.logging_utils import get_logger, redact_for_audit
from mcp_database_server.tools_definitions import get_tool_definitions
from mcp_database_server.tools_impl import (
    tool_db_health_check,
    tool_db_list_schemas,
    tool_db_list_tables,
    tool_db_query,
)

logger = get_logger(__name__)


def _build_app(settings: Settings) -> FastMCP:
    """Create the FastMCP server and register tools."""
    app = FastMCP(
        name="MCP-database-server",
        instructions=(
            "Tools for safely querying a PostgreSQL database. "
            "Read-only queries are supported in this scaffold."
        ),
    )

    # Register tools using the FastMCP decorator-based API.
    # We keep implementations async and bounded.

    @app.tool(
        name="db_health_check",
        description=get_tool_definitions()[0]["description"],
    )
    async def db_health_check() -> str:
        """Check PostgreSQL connectivity."""
        res = await tool_db_health_check(settings)
        return res["content"][0]["text"]

    @app.tool(
        name="db_list_schemas",
        description=get_tool_definitions()[1]["description"],
    )
    async def db_list_schemas(limit: int | None = None) -> str:
        """List schemas in the database."""
        res = await tool_db_list_schemas(settings, limit=limit)
        return res["content"][0]["text"]

    @app.tool(
        name="db_list_tables",
        description=get_tool_definitions()[2]["description"],
    )
    async def db_list_tables(schema: str, limit: int | None = None) -> str:
        """List tables for a given schema."""
        res = await tool_db_list_tables(settings, schema=schema, limit=limit)
        return res["content"][0]["text"]

    @app.tool(
        name="db_query",
        description=get_tool_definitions()[3]["description"],
    )
    async def db_query(sql: str, max_rows: int | None = None) -> str:
        """Execute a read-only SELECT query."""
        res = await tool_db_query(settings, sql=sql, max_rows=max_rows)
        return res["content"][0]["text"]

    return app


# PUBLIC_INTERFACE
def run_stdio_server() -> None:
    """Run the MCP server over STDIO.

    This function blocks until the server is terminated.
    """
    settings = Settings()
    app = _build_app(settings)

    # FastMCP provides synchronous .run() which manages its own event loop.
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt; shutting down.")
    except Exception as e:
        logger.error("Fatal server error: %s", redact_for_audit(str(e)))
        raise
