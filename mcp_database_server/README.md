# MCP-database-server

An MCP (Model Context Protocol) **STDIO JSON-RPC** server that provides safe, schema-validated tools for querying and managing a PostgreSQL database.

## Key properties (per MCP-development-standards)

This server is designed to be safe to run under an MCP host (Claude Desktop, Cursor, etc.) where STDIO is the protocol transport and mistakes can easily leak secrets.

It keeps STDIO safe and predictable in the following ways:

- It is **STDIO-safe**: protocol messages are written to stdout; **all logs go to stderr**.
- It enforces **strict tool schemas**: JSON Schema input validation is enforced server-side.
- It returns **bounded outputs**: rows and payload bytes are capped; truncation notes are returned when limits are reached.
- It provides **secret redaction**: credentials are not returned in tool results and are redacted from log messages.

## Tools

The server exposes the following tools via `tools/list`:

- `db_health_check` – checks database connectivity with a short timeout.
- `db_list_schemas` – lists schemas (bounded).
- `db_list_tables` – lists tables in a schema (bounded).
- `db_query` – executes **read-only** SELECT queries with row/payload limits.

## Secure configuration

Configuration is environment-driven. The database connection is resolved using the following precedence order:

1. `POSTGRES_URL` (environment variable override; recommended for production)
2. A repository connection file at `mcp-deployment-management-system-53515/database/db_connection.txt` (default behavior if present)
3. Individual `POSTGRES_*` parts (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, with host/port defaults)

The server must never print connection strings or credentials to stdout, and it should not log them to stderr.

### Environment variables

The table below documents what the server currently reads. Defaults and hard safety caps are enforced in code.

#### Database connection

| Name | Required | Default | Purpose |
|---|---:|---|---|
| `POSTGRES_URL` | No | None | Full PostgreSQL URI. If set, it is used and takes precedence over all other connection sources. Example: `postgresql://user:pass@host:5432/db`. |
| `POSTGRES_USER` | Conditionally | None | Username, used only if `POSTGRES_URL` is not set and the repo connection file is not available. |
| `POSTGRES_PASSWORD` | Conditionally | None | Password, used only if `POSTGRES_URL` is not set and the repo connection file is not available. |
| `POSTGRES_DB` | Conditionally | None | Database name, used only if `POSTGRES_URL` is not set and the repo connection file is not available. |
| `POSTGRES_HOST` | No | `localhost` | Host used with individual `POSTGRES_*` parts. |
| `POSTGRES_PORT` | No | `5432` | Port used with individual `POSTGRES_*` parts. |

The `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` variables are required only when neither `POSTGRES_URL` nor the repo connection file can be used.

#### Safety and bounding controls

| Name | Required | Default | Range / Hard cap | Purpose |
|---|---:|---:|---|---|
| `MCP_DB_MAX_ROWS` | No | `100` | Minimum 1. Hard cap `1000` | Caps the number of rows returned by tools. Even if configured higher, it is clamped to 1000. |
| `MCP_DB_MAX_BYTES` | No | `200000` | Minimum 1000. Hard cap `500000` | Caps tool output size. When limits are reached, responses are truncated with an explicit note. |
| `MCP_DB_QUERY_TIMEOUT_SECONDS` | No | `10` | 1–120 | Application-level timeout used for DB operations. This value is used for connection timeout and for tool execution timeouts. |

#### Logging

| Name | Required | Default | Purpose |
|---|---:|---:|---|
| `LOG_LEVEL` | No | `INFO` | Controls stderr logging verbosity. |

### Connection file behavior (default repo integration)

If `POSTGRES_URL` is not set, the server attempts to read a canonical connection string from:

- `mcp-deployment-management-system-53515/database/db_connection.txt`

The server accepts either of the following formats in the file:

- `psql postgresql://user:pass@host:port/db`
- `postgresql://user:pass@host:port/db`
- `postgres://user:pass@host:port/db`

This behavior is intended for the repository’s paired database container and local development. In production deployments, prefer `POSTGRES_URL` instead of relying on a file path.

## Security and redaction guarantees

### STDIO safety

This server must only emit JSON-RPC protocol messages to stdout. Logging is configured to write to stderr only. Any accidental writes to stdout (such as `print(...)`) can corrupt the MCP protocol stream and are considered a correctness and security issue.

### Secrets and connection information

The server aims to ensure that credentials are not exfiltrated through tool outputs or logs.

- Tool results do not include the configured connection string or credentials.
- When exceptions occur, the server returns generic error messages to the client.
- Logs are passed through a redaction formatter that masks common secret patterns, including:
  - `postgresql://user:password@...` style URIs (password is replaced with `***`)
  - `password=...` fragments (value is replaced with `***`)
- Structured values that are logged via the audit redaction helper will also redact values for common secret key names (for example keys containing `password`, `secret`, `token`, or `key`).

Redaction is best-effort and pattern-based; it is not a substitute for not logging secrets in the first place. Operationally, you should assume logs might still contain sensitive information if upstream libraries include secrets in unexpected formats, so logs must be treated as sensitive.

### Query constraints and side effects

- `db_query` enforces a defense-in-depth “SELECT only” policy (non-SELECT statements are rejected).
- The server enforces bounded output and will truncate results when row or size limits are reached.
- Timeouts are enforced at the application level using asyncio timeouts, and the server is designed to support database-side statement timeouts as an additional layer.

## Safe operational guidance

### Recommended production configuration

In production, you should:

- Provide the database credentials via `POSTGRES_URL` (or via a secret manager mapped into environment variables).
- Ensure that `.env` files containing real credentials are not committed and are protected with appropriate file permissions.
- Run with conservative limits (the defaults are conservative) and increase only if necessary.
- Keep logs available for debugging, but treat them as sensitive and route them to a secure log sink.

### Host (Claude Desktop) configuration example

Example snippet (adjust paths and connection info). This example uses `POSTGRES_URL` because it is explicit and does not rely on a repo file.

```json
{
  "mcpServers": {
    "mcp-database-server": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "mcp_database_server"],
      "env": {
        "POSTGRES_URL": "postgresql://USER:PASSWORD@HOST:PORT/DB",
        "MCP_DB_MAX_ROWS": "100",
        "MCP_DB_MAX_BYTES": "200000",
        "MCP_DB_QUERY_TIMEOUT_SECONDS": "10",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Install / Run

From repository root:

```bash
cd mcp-deployment-management-system-53514/mcp_database_server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the MCP server (STDIO):

```bash
python -m mcp_database_server
```

Task completed: Step 01.04 documentation added by updating README.md with secure configuration details, env var requirements/defaults, and safe operational guidance.
