import json
from collections.abc import Iterable

import pytest

from mcp_database_server.config import Settings


@pytest.fixture()
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """
    Create Settings with conservative defaults and without requiring real DB env.

    Individual tests can override env vars via monkeypatch before instantiating their own Settings
    if needed.
    """
    # Ensure we don't accidentally pick up a real POSTGRES_URL from the environment in CI.
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    return Settings()


def parse_json_lines(text: str) -> list[dict]:
    """Parse newline-delimited JSON objects from text."""
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def iter_json_objects(lines: Iterable[str]) -> list[dict]:
    """Parse a sequence of JSON lines."""
    return [json.loads(line) for line in lines if line.strip()]
