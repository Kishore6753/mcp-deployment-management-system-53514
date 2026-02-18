# MCP-database-server

An MCP (Model Context Protocol) **STDIO JSON-RPC** server that provides safe, schema-validated tools for querying and managing a PostgreSQL database.

## Key properties (per MCP-development-standards)

- **STDIO-safe**: protocol messages use stdout; **all logs go to stderr**.
- **Strict tool schemas**: JSON Schema input validation enforced server-side.
- **Bounded outputs**: hard caps on rows and payload size; truncation notes returned.
- **Secret redaction**: credentials are never echoed; connection info is never returned.

## Tools (scaffold)

This scaffold defines the structure and initial tools; implementation will be expanded in later steps:

- `db_health_check` – checks database connectivity with a short timeout.
- `db_list_schemas` – list schemas (bounded).
- `db_list_tables` – list tables in a schema (bounded).
- `db_query` – run **read-only** SELECT queries with row/payload limits.

## Configuration

This server reads DB config from environment variables (recommended), or optionally from a local connection string file.

### Environment variables

- `POSTGRES_URL` (recommended): full connection URI, e.g. `postgresql://user:pass@host:port/db`
- Or individual fields:
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_DB`
  - `POSTGRES_HOST` (default: `localhost`)
  - `POSTGRES_PORT` (default: `5432`)

Optional:
- `MCP_DB_MAX_ROWS` (default: `100`, max: `1000`)
- `MCP_DB_MAX_BYTES` (default: `200000`)
- `MCP_DB_QUERY_TIMEOUT_SECONDS` (default: `10`)

### Local development convenience (optional)

You may place a file at:
- `mcp_database_server/config/db_connection.txt`

Format:
- `psql postgresql://user:pass@host:port/db`
- or `postgresql://user:pass@host:port/db`

**Never commit real credentials.** The repository may contain canonical connection info elsewhere; this server must not print it.

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

## Host configuration example (Claude Desktop)

Example snippet (adjust paths):

```json
{
  "mcpServers": {
    "mcp-database-server": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "mcp_database_server"],
      "env": {
        "POSTGRES_URL": "postgresql://USER:PASSWORD@HOST:PORT/DB",
        "MCP_DB_MAX_ROWS": "100"
      }
    }
  }
}
```

## Security notes

- The `db_query` tool is scaffolded as **read-only** (SELECT only). Write operations (DDL/DML) should be added only with explicit allowlists and confirmation patterns.
- Tool results are truncated and will never include connection strings or credentials.

---
Scaffold created in step 01.01. Subsequent steps should implement full MCP protocol handling, expanded tool set, and robust Postgres operations.
