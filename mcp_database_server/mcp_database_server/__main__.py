"""Module entrypoint for running the MCP server via `python -m mcp_database_server`."""

from mcp_database_server.server import run_stdio_server


def main() -> None:
    """Run the MCP database server over STDIO."""
    run_stdio_server()


if __name__ == "__main__":
    main()
