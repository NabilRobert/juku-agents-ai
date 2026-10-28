"""Spans for Juku's MCP server, with content off (Phase 2 M6, SM5; fitness function FF9).

Each tool call gets a span carrying the decision, its reason category, the
tool, the acting agent and the chain's length: what Project 6's viewer
needs to follow a request. Never the arguments, the result or the
learner. Export follows Project 6's conventions: OTLP over HTTP to the URL
in OTEL_EXPORTER_OTLP_ENDPOINT, and nothing at all when it isn't set.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter

SERVICE_NAME = "juku-mcp"
ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
# Attribute names that would carry content; no span here may have one (FF9).
CONTENT_ATTRIBUTE_PREFIXES = ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "mcp.tool.arguments")

tracer = trace.get_tracer("juku_mcp")


def install_tracing(exporter: SpanExporter | None = None) -> None:
    """Send spans to `exporter` (tests), or to the OTLP endpoint if one is set; otherwise do nothing."""
    if exporter is None:
        if not os.environ.get(ENDPOINT_ENV):
            return
        processor: SimpleSpanProcessor | BatchSpanProcessor = BatchSpanProcessor(OTLPSpanExporter())
    else:
        processor = SimpleSpanProcessor(exporter)
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
