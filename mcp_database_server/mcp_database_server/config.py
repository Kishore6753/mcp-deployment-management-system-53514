"""Configuration for MCP-database-server (env-driven).

Never print or return credential material.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_database_server.constants import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_ROWS,
    DEFAULT_QUERY_TIMEOUT_SECONDS,
    HARD_MAX_BYTES,
    HARD_MAX_ROWS,
)


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_url: str | None = Field(
        default=None,
        alias="POSTGRES_URL",
        description="Full PostgreSQL connection URI. Preferred over individual fields.",
    )

    postgres_user: str | None = Field(default=None, alias="POSTGRES_USER")
    postgres_password: str | None = Field(default=None, alias="POSTGRES_PASSWORD")
    postgres_db: str | None = Field(default=None, alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    max_rows: int = Field(default=DEFAULT_MAX_ROWS, alias="MCP_DB_MAX_ROWS", ge=1)
    max_bytes: int = Field(default=DEFAULT_MAX_BYTES, alias="MCP_DB_MAX_BYTES", ge=1000)
    query_timeout_seconds: int = Field(
        default=DEFAULT_QUERY_TIMEOUT_SECONDS,
        alias="MCP_DB_QUERY_TIMEOUT_SECONDS",
        ge=1,
        le=120,
    )

    def bounded_max_rows(self) -> int:
        """Return max_rows clamped to the hard upper bound."""
        return min(self.max_rows, HARD_MAX_ROWS)

    def bounded_max_bytes(self) -> int:
        """Return max_bytes clamped to the hard upper bound."""
        return min(self.max_bytes, HARD_MAX_BYTES)
