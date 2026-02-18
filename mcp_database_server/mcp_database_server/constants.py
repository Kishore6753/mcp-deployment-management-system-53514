"""Constants and safety limits for MCP-database-server."""

# Hard upper bound regardless of env configuration.
HARD_MAX_ROWS = 1000

# Hard upper bound to avoid flooding STDIO with huge responses.
HARD_MAX_BYTES = 500_000

# Conservative default for tool results.
DEFAULT_MAX_ROWS = 100

# Default maximum total bytes for textual outputs (approx; enforced by truncation).
DEFAULT_MAX_BYTES = 200_000

# Default query timeout.
DEFAULT_QUERY_TIMEOUT_SECONDS = 10
