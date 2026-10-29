"""Spans for Juku's MCP server, with content off (Phase 2 M6, SM5; fitness function FF9).

Each tool call gets a span carrying the decision, its reason category, the
tool, the acting agent and the chain's length: what Project 6's viewer
needs to follow a request. Never the arguments, the result or the learner.
"""

from __future__ import annotations

from juku_common import telemetry
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SpanExporter

SERVICE_NAME = "juku-mcp"
# Attribute names that would carry content; no span here may have one (FF9).
CONTENT_ATTRIBUTE_PREFIXES = ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "mcp.tool.arguments")

tracer = trace.get_tracer("juku_mcp")


def install_tracing(exporter: SpanExporter | None = None) -> None:
    telemetry.install_tracing(SERVICE_NAME, exporter)
