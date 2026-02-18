from __future__ import annotations

import pytest

from mcp_database_server.server import _handle_request


@pytest.mark.asyncio
async def test_invalid_request_missing_jsonrpc_returns_error(settings) -> None:
    resp = await _handle_request(settings, {"id": 1, "method": "tools/list", "params": {}})
    assert resp["error"]["code"] == -32600
    assert resp["error"]["message"] == "Invalid Request"


@pytest.mark.asyncio
async def test_invalid_params_type_tools_call_returns_error(settings) -> None:
    resp = await _handle_request(
        settings, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": "bad"}
    )
    assert resp["error"]["code"] == -32602
    assert resp["error"]["message"] == "Invalid params"


@pytest.mark.asyncio
async def test_unknown_method_returns_method_not_found(settings) -> None:
    resp = await _handle_request(
        settings, {"jsonrpc": "2.0", "id": 1, "method": "no_such_method", "params": {}}
    )
    assert resp["error"]["code"] == -32601
    assert resp["error"]["message"] == "Method not found"


@pytest.mark.asyncio
async def test_unknown_tool_returns_unknown_tool_error(settings) -> None:
    resp = await _handle_request(
        settings,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        },
    )
    assert resp["error"]["code"] == -32601
    assert resp["error"]["message"].startswith("Unknown tool:")


@pytest.mark.asyncio
async def test_tools_call_schema_validation_failure_sets_isError(settings) -> None:
    # db_list_tables requires 'schema'
    resp = await _handle_request(
        settings,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "db_list_tables", "arguments": {}},
        },
    )
    assert resp["result"]["isError"] is True
    text = resp["result"]["content"][0]["text"]
    assert "Invalid tool arguments:" in text
    assert "required property" in text


@pytest.mark.asyncio
async def test_tools_call_rejects_additional_properties(settings) -> None:
    resp = await _handle_request(
        settings,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "db_health_check", "arguments": {"x": 1}},
        },
    )
    assert resp["result"]["isError"] is True
    text = resp["result"]["content"][0]["text"]
    assert "Additional properties are not allowed" in text


@pytest.mark.asyncio
async def test_notification_no_id_returns_none(settings) -> None:
    resp = await _handle_request(settings, {"jsonrpc": "2.0", "method": "tools/list", "params": {}})
    assert resp is None
