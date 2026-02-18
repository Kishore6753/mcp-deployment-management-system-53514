from __future__ import annotations

import asyncio

import pytest

from mcp_database_server.server import _handle_request


@pytest.mark.asyncio
async def test_tools_call_timeout_returns_isError_true(monkeypatch: pytest.MonkeyPatch, settings) -> None:
    async def slow_tool(args):
        raise asyncio.TimeoutError()

    # Patch _tool_map so db_health_check triggers timeout.
    from mcp_database_server import server as server_mod

    monkeypatch.setattr(server_mod, "_tool_map", lambda _settings: {"db_health_check": slow_tool})

    resp = await _handle_request(
        settings,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "db_health_check", "arguments": {}},
        },
    )
    assert resp["result"]["isError"] is True
    assert resp["result"]["content"][0]["text"] == "Operation timed out."
