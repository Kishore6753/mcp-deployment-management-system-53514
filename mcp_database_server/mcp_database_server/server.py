"""MCP STDIO JSON-RPC server implementation for MCP-database-server.

Requirements (step 01.03):
- Implement an explicit STDIO JSON-RPC loop (keep stdout protocol-only).
- Wire tools/list and tools/call routing to tools_impl.
- Enforce tool input validation (strict JSON Schema).
- Ensure bounded outputs (handled by tools_impl).
- Redact secrets from any logs/errors (stderr only).

This module must never print anything to stdout except JSON-RPC responses.
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

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


def _json_dumps(obj: Any) -> str:
    """Serialize JSON compactly but stably."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _write_stdout_line(line: str) -> None:
    """Write a single protocol line to stdout."""
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _read_stdin_lines() -> Any:
    """Yield lines from stdin (blocking)."""
    for line in sys.stdin:
        # Allow blank lines; ignore whitespace-only.
        if line.strip() == "":
            continue
        yield line


def _jsonrpc_error(*, id_value: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    """Build a JSON-RPC error object."""
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id_value, "error": err}


def _jsonrpc_result(*, id_value: Any, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC result object."""
    return {"jsonrpc": "2.0", "id": id_value, "result": result}


def _mcp_initialize_result() -> dict[str, Any]:
    """Return MCP initialize result payload."""
    return {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "MCP-database-server", "version": "0.1.0"},
        "capabilities": {
            "tools": {},
        },
    }


def _tool_map(settings: Settings) -> dict[str, Any]:
    """Tool name -> async callable returning MCP tool result dict."""
    return {
        "db_health_check": lambda args: tool_db_health_check(settings),
        "db_list_schemas": lambda args: tool_db_list_schemas(settings, limit=args.get("limit")),
        "db_list_tables": lambda args: tool_db_list_tables(
            settings, schema=str(args["schema"]), limit=args.get("limit")
        ),
        "db_query": lambda args: tool_db_query(settings, sql=str(args["sql"]), max_rows=args.get("max_rows")),
    }


def _validator_map() -> dict[str, Draft202012Validator]:
    """Tool name -> JSON Schema validator."""
    validators: dict[str, Draft202012Validator] = {}
    for tool in get_tool_definitions():
        validators[tool["name"]] = Draft202012Validator(tool["inputSchema"])
    return validators


async def _handle_request(settings: Settings, req: dict[str, Any]) -> dict[str, Any] | None:
    """Handle a single JSON-RPC request.

    Returns a JSON-RPC response object, or None for notifications (no id).
    """
    id_value = req.get("id", None)
    method = req.get("method")
    params = req.get("params") or {}

    # Notifications: no 'id' -> no response (but we still may log).
    is_notification = "id" not in req

    try:
        if req.get("jsonrpc") != "2.0":
            resp = _jsonrpc_error(id_value=id_value, code=-32600, message="Invalid Request")
            return None if is_notification else resp

        if not isinstance(method, str):
            resp = _jsonrpc_error(id_value=id_value, code=-32600, message="Invalid Request")
            return None if is_notification else resp

        # MCP core methods
        if method == "initialize":
            resp = _jsonrpc_result(id_value=id_value, result=_mcp_initialize_result())
            return None if is_notification else resp

        if method == "notifications/initialized":
            # No response expected typically.
            return None

        if method == "tools/list":
            resp = _jsonrpc_result(id_value=id_value, result={"tools": get_tool_definitions()})
            return None if is_notification else resp

        if method == "tools/call":
            if not isinstance(params, dict):
                resp = _jsonrpc_error(id_value=id_value, code=-32602, message="Invalid params")
                return None if is_notification else resp

            tool_name = params.get("name")
            tool_args = params.get("arguments") or {}

            if not isinstance(tool_name, str):
                resp = _jsonrpc_error(id_value=id_value, code=-32602, message="Invalid params: name must be string")
                return None if is_notification else resp
            if not isinstance(tool_args, dict):
                resp = _jsonrpc_error(
                    id_value=id_value, code=-32602, message="Invalid params: arguments must be object"
                )
                return None if is_notification else resp

            tools = _tool_map(settings)
            validators = _validator_map()

            if tool_name not in tools:
                resp = _jsonrpc_error(id_value=id_value, code=-32601, message=f"Unknown tool: {tool_name}")
                return None if is_notification else resp

            # Strict input validation against declared schema
            try:
                validators[tool_name].validate(tool_args)
            except ValidationError as ve:
                # Do not echo full args; just safe summary.
                resp = _jsonrpc_result(
                    id_value=id_value,
                    result={
                        "content": [
                            {
                                "type": "text",
                                "text": f"Invalid tool arguments: {ve.message}",
                            }
                        ],
                        "isError": True,
                    },
                )
                return None if is_notification else resp

            # Execute tool with both application-level and DB-level timeouts handled inside tools_impl/db.
            try:
                result = await tools[tool_name](tool_args)
            except asyncio.TimeoutError:
                result = {
                    "content": [{"type": "text", "text": "Operation timed out."}],
                    "isError": True,
                }
            except Exception as e:
                # Log redacted details to stderr; return generic error to client.
                logger.warning(
                    "Tool execution failed: %s",
                    redact_for_audit({"tool": tool_name, "error": str(e)}),
                )
                result = {"content": [{"type": "text", "text": "Tool execution failed."}], "isError": True}

            resp = _jsonrpc_result(id_value=id_value, result=result)
            return None if is_notification else resp

        resp = _jsonrpc_error(id_value=id_value, code=-32601, message="Method not found")
        return None if is_notification else resp

    except Exception as e:
        # Defensive catch-all: do not crash loop; never emit secrets.
        logger.error("Request handler error: %s", redact_for_audit(str(e)))
        logger.debug("Traceback (redacted): %s", redact_for_audit(traceback.format_exc()))
        resp = _jsonrpc_error(id_value=id_value, code=-32603, message="Internal error")
        return None if is_notification else resp


async def _run_async_loop() -> None:
    """Async STDIO loop reading JSON-RPC requests and writing responses."""
    settings = Settings()

    # NOTE: We intentionally do not log settings values; they may include secrets.
    logger.info("MCP-database-server starting (STDIO JSON-RPC).")

    loop = asyncio.get_running_loop()

    # Read stdin in a thread to avoid blocking event loop.
    def _stdin_iter():
        return list(_read_stdin_lines())

    while True:
        lines = await loop.run_in_executor(None, sys.stdin.readline)
        if lines == "":
            # EOF
            logger.info("STDIN closed; exiting.")
            return

        line = lines.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception:
            # Invalid JSON; respond only if there is an id (we don't have it).
            logger.warning("Received invalid JSON (redacted).")
            continue

        # Batch requests not supported in this scaffold; handle single object only.
        if not isinstance(req, dict):
            logger.warning("Received non-object JSON-RPC payload (ignored).")
            continue

        resp = await _handle_request(settings, req)
        if resp is None:
            continue

        _write_stdout_line(_json_dumps(resp))


# PUBLIC_INTERFACE
def run_stdio_server() -> None:
    """Run the MCP server over STDIO.

    Blocks until stdin is closed or the process is terminated.
    """
    try:
        asyncio.run(_run_async_loop())
    except KeyboardInterrupt:
        # Don't write to stdout; just exit cleanly.
        logger.info("Received KeyboardInterrupt; shutting down.")
    except Exception as e:
        # Redact and raise to surface in supervisor logs.
        logger.error("Fatal server error: %s", redact_for_audit(str(e)))
        raise
