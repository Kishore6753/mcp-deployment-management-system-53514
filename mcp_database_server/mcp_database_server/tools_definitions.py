"""Tool definitions (names, descriptions, JSON Schemas) for MCP-database-server.

These are the public tool contracts exposed via tools/list.

Design goals (per MCP-development-standards):
- Stable tool names: snake_case.
- Strict JSON Schema validation:
  - JSON Schema draft 2020-12
  - additionalProperties: false (no unknown inputs)
  - required fields specified
- Explicit side effects: every tool describes whether it mutates DB state (here: none).
- Bounded outputs: every tool describes hard/soft output bounds and truncation behavior.
"""

from __future__ import annotations

from typing import Any


def _strict_object_schema(*, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """Build a strict JSON Schema object definition."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


# PUBLIC_INTERFACE
def get_tool_definitions() -> list[dict[str, Any]]:
    """Return the MCP tool definitions for tools/list.

    Each entry follows the MCP tool shape:
      { name, title?, description, inputSchema }

    Notes:
    - Names are stable snake_case and should not be changed without a major-version bump.
    - Schemas are strict: unknown input keys are rejected.
    - Side effects are explicitly stated in each tool description.
    - Output is bounded by server configuration and hard limits; tools may truncate and
      will include an explicit truncation note in returned text when truncation occurs.
    """
    common_bounds = (
        "Output is bounded: rows are capped by MCP_DB_MAX_ROWS (hard cap 1000) and "
        "payload size is capped by MCP_DB_MAX_BYTES (hard cap 500000 bytes). "
        "If limits are reached, results are truncated and an explicit truncation note is appended."
    )

    return [
        {
            "name": "db_health_check",
            "title": "Database Health Check",
            "description": (
                "Checks PostgreSQL connectivity and returns minimal non-secret metadata.\n\n"
                "Side effects: none (read-only).\n"
                f"{common_bounds}"
            ),
            "inputSchema": _strict_object_schema(properties={}, required=[]),
        },
        {
            "name": "db_list_schemas",
            "title": "List Database Schemas",
            "description": (
                "Lists schemas in the PostgreSQL database.\n\n"
                "Side effects: none (read-only).\n"
                f"{common_bounds}"
            ),
            "inputSchema": _strict_object_schema(
                properties={
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "description": (
                            "Maximum number of schemas to return. "
                            "Server will clamp to its configured/hard max."
                        ),
                    }
                },
                required=[],
            ),
        },
        {
            "name": "db_list_tables",
            "title": "List Tables in a Schema",
            "description": (
                "Lists base tables in a given schema.\n\n"
                "Side effects: none (read-only).\n"
                f"{common_bounds}"
            ),
            "inputSchema": _strict_object_schema(
                properties={
                    "schema": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Schema name (e.g., 'public').",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "description": (
                            "Maximum number of tables to return. "
                            "Server will clamp to its configured/hard max."
                        ),
                    },
                },
                required=["schema"],
            ),
        },
        {
            "name": "db_query",
            "title": "Run a Read-only SQL Query",
            "description": (
                "Executes a READ-ONLY SQL query against PostgreSQL and returns rows.\n\n"
                "Security constraints:\n"
                "- Only SELECT statements are allowed; non-SELECT statements are rejected.\n\n"
                "Side effects: none (read-only).\n"
                f"{common_bounds}"
            ),
            "inputSchema": _strict_object_schema(
                properties={
                    "sql": {
                        "type": "string",
                        "minLength": 1,
                        "description": (
                            "A SELECT query to execute. Non-SELECT statements are rejected."
                        ),
                    },
                    "max_rows": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "description": (
                            "Row cap for this query. Server will clamp to its configured/hard max."
                        ),
                    },
                },
                required=["sql"],
            ),
        },
    ]
