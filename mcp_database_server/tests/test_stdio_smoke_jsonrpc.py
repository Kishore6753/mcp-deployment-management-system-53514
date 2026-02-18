from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

import pytest


def _read_json_line(pipe) -> dict[str, Any]:
    line = pipe.readline()
    assert line, "Expected a JSON-RPC response line on stdout"
    line = line.strip()
    return json.loads(line)


@pytest.mark.timeout(10)
def test_stdio_jsonrpc_smoke_initialize_and_tools_list_no_stdout_pollution() -> None:
    """
    Start the server as a subprocess and speak JSON-RPC over stdio.

    Assertions:
    - stdout contains only JSON-RPC objects (one per line)
    - stderr contains logs (not stdout), and secrets are not leaked
    """
    env = os.environ.copy()
    # Ensure we don't require a real DB for this smoke test. We never call DB tools.
    env.pop("POSTGRES_URL", None)
    env.pop("POSTGRES_USER", None)
    env.pop("POSTGRES_PASSWORD", None)
    env.pop("POSTGRES_DB", None)

    # Put a fake secret in env to ensure it doesn't accidentally show up in logs.
    env["POSTGRES_URL"] = "postgresql://user:supersecret@localhost:5432/db"
    env["LOG_LEVEL"] = "INFO"

    p = subprocess.Popen(
        [sys.executable, "-m", "mcp_database_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert p.stdin and p.stdout and p.stderr

    try:
        # initialize
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
        p.stdin.flush()
        resp1 = _read_json_line(p.stdout)
        assert resp1["jsonrpc"] == "2.0"
        assert resp1["id"] == 1
        assert resp1["result"]["serverInfo"]["name"] == "MCP-database-server"

        # tools/list
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
        p.stdin.flush()
        resp2 = _read_json_line(p.stdout)
        assert resp2["id"] == 2
        tools = resp2["result"]["tools"]
        assert isinstance(tools, list)
        assert [t["name"] for t in tools] == ["db_health_check", "db_list_schemas", "db_list_tables", "db_query"]

        # Ensure no non-JSON pollution: the two lines we read must parse; any extra stdout is allowed
        # only if it is JSON-RPC as well. We don't read further; just ensure stderr got logs.
        p.terminate()
        out, err = p.communicate(timeout=5)

        # Any extra stdout must be either empty or parseable JSON lines.
        if out.strip():
            for line in out.splitlines():
                json.loads(line)

        # Stderr should not contain the raw secret; if it mentions the URL, it must be redacted.
        assert "supersecret" not in err
        if "postgresql://" in err:
            assert "postgresql://user:***@" in err
    finally:
        if p.poll() is None:
            p.kill()
            p.communicate(timeout=5)


@pytest.mark.timeout(10)
def test_stdio_notification_produces_no_response() -> None:
    """JSON-RPC notifications (no id) must not produce any stdout response."""
    p = subprocess.Popen(
        [sys.executable, "-m", "mcp_database_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )
    assert p.stdin and p.stdout and p.stderr
    try:
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "tools/list", "params": {}}) + "\n")
        p.stdin.flush()
        p.terminate()
        out, _ = p.communicate(timeout=5)
        assert out.strip() == ""
    finally:
        if p.poll() is None:
            p.kill()
            p.communicate(timeout=5)
