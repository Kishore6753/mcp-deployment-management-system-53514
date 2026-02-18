from __future__ import annotations

import asyncio
import json

import pytest

from mcp_database_server.bounding import bound_rows, truncate_text
from mcp_database_server.config import Settings
from mcp_database_server import tools_impl


def test_truncate_text_preserves_valid_utf8() -> None:
    # 'é' is two bytes in UTF-8; choose max_bytes that cuts between characters.
    s = "é" * 10
    out, truncated = truncate_text(s, max_bytes=5)
    assert truncated is True
    # Output should still be valid unicode text and not exceed byte limit
    assert len(out.encode("utf-8")) <= 5


def test_bound_rows_caps_list() -> None:
    rows = [{"i": i} for i in range(10)]
    bounded, did_truncate = bound_rows(rows, max_rows=3)
    assert did_truncate is True
    assert bounded == [{"i": 0}, {"i": 1}, {"i": 2}]


@pytest.mark.asyncio
async def test_db_query_truncates_by_size_and_adds_note(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Simulate a db_query returning a very large row set and ensure size bounding truncates.

    We patch with_connection/run_with_timeout to avoid a real DB and to return controlled rows.
    """
    # Create a payload that's definitely larger than a small max_bytes.
    big_rows = [{"col": "x" * 2000, "i": i} for i in range(50)]

    async def fake_with_connection(settings: Settings, fn):
        class DummyConn:
            async def fetch(self, sql: str):
                return [type("R", (), {"items": lambda self: r.items()})() for r in []]  # unused

        # Call fn with a dummy conn, but we won't use it because we also patch _fetch_rows
        return await fn(DummyConn())

    async def fake_run_with_timeout(coro, timeout_seconds: int):
        return await coro

    async def fake_fetch_rows(conn, sql: str):
        return big_rows

    monkeypatch.setattr(tools_impl, "with_connection", fake_with_connection)
    monkeypatch.setattr(tools_impl, "run_with_timeout", fake_run_with_timeout)
    monkeypatch.setattr(tools_impl, "_fetch_rows", fake_fetch_rows)

    # Very small max bytes to force truncation.
    s = Settings(MCP_DB_MAX_BYTES=3000, MCP_DB_MAX_ROWS=100, MCP_DB_QUERY_TIMEOUT_SECONDS=2)  # type: ignore[call-arg]
    result = await tools_impl.tool_db_query(s, sql="SELECT 1", max_rows=None)

    assert "content" in result and result["content"][0]["type"] == "text"
    text = result["content"][0]["text"]
    assert "[Results truncated due to row/size limits.]" in text

    payload = json.loads(text.split("\n\n[Results truncated")[0])
    assert payload["rowCount"] >= 1
    assert payload["rowCount"] < len(big_rows)


@pytest.mark.asyncio
async def test_tool_text_result_appends_truncation_note_when_bytes_exceeded() -> None:
    # Directly exercise _tool_text_result via public tool behavior (db_query with patched result).
    # Ensure the generic note "[Truncated due to output size limits.]" is applied.
    s = Settings(MCP_DB_MAX_BYTES=50, MCP_DB_MAX_ROWS=100, MCP_DB_QUERY_TIMEOUT_SECONDS=2)  # type: ignore[call-arg]

    # Patch to return a single large row so JSON exceeds max_bytes, triggering _tool_text_result truncation.
    big_rows = [{"x": "y" * 500}]

    async def fake_with_connection(settings: Settings, fn):
        return await fn(None)

    async def fake_run_with_timeout(coro, timeout_seconds: int):
        return await coro

    async def fake_fetch_rows(conn, sql: str):
        return big_rows

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(tools_impl, "with_connection", fake_with_connection)
    monkeypatch.setattr(tools_impl, "run_with_timeout", fake_run_with_timeout)
    monkeypatch.setattr(tools_impl, "_fetch_rows", fake_fetch_rows)

    try:
        result = await tools_impl.tool_db_query(s, sql="SELECT 1", max_rows=None)
        text = result["content"][0]["text"]
        assert "[Truncated due to output size limits.]" in text
    finally:
        monkeypatch.undo()
