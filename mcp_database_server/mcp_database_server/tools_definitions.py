"""Tool definitions (names, descriptions, JSON Schemas) for MCP-database-server.

These are the public tool contracts exposed via tools/list.
"""

from __future__ import annotations


# PUBLIC_INTERFACE
def get_tool_definitions() -> list[dict]:
    """Return the MCP tool definitions for tools/list.

    Each entry follows the MCP spec shape:
      { name, title?, description, inputSchema }
    """
    return [
        {
            "name": "db_health_check",
            "title": "Database Health Check",
            "description": (
                "Check PostgreSQL connectivity and return basic server info. "
                "No credentials are returned."
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "db_list_schemas",
            "title": "List Database Schemas",
            "description": "List schemas in the PostgreSQL database (bounded).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "description": "Maximum number of schemas to return (capped).",
                    }
                },
                "required": [],
            },
        },
        {
            "name": "db_list_tables",
            "title": "List Tables in a Schema",
            "description": "List tables in a given schema (bounded).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Schema name (e.g., public).",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "description": "Maximum number of tables to return (capped).",
                    },
                },
                "required": ["schema"],
            },
        },
        {
            "name": "db_query",
            "title": "Run a Read-only SQL Query",
            "description": (
                "Execute a READ-ONLY SQL query (SELECT only) against PostgreSQL and return rows. "
                "Results are bounded by row and size limits."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "minLength": 1,
                        "description": "A SELECT query to execute. Non-SELECT statements are rejected.",
                    },
                    "max_rows": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "description": "Row cap for this query (capped).",
                    },
                },
                "required": ["sql"],
            },
        },
    ]
