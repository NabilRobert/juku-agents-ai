"""Spans for Juku's MCP server (stub: lands in the next commit)."""

from __future__ import annotations

from opentelemetry.sdk.trace.export import SpanExporter

CONTENT_ATTRIBUTE_PREFIXES = ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "mcp.tool.arguments")


def install_tracing(exporter: SpanExporter | None = None) -> None:
    raise NotImplementedError
