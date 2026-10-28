"""`juku-mcp serve`: run Juku's MCP server (in its container, on the gateway's upstream network)."""

from __future__ import annotations

from typing import Annotated

import typer
import uvicorn

from juku_mcp.app import create_app
from juku_mcp.settings import McpSettings

app = typer.Typer(help="Juku's MCP server.", no_args_is_help=True)
DEFAULT_PORT = 8000


@app.callback()
def main() -> None:
    """Juku's MCP server."""


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Address to listen on.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on.")] = DEFAULT_PORT,
) -> None:
    """Serve the tools over Streamable HTTP at /mcp."""
    settings = McpSettings()  # pyright: ignore[reportCallIssue] (fields come from the environment)
    uvicorn.run(create_app(settings), host=host, port=port, log_level="warning")
