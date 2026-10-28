"""Tracing setup shared by Juku's services, with Project 6's conventions (Phase 2 M6).

OTLP over HTTP to the URL in OTEL_EXPORTER_OTLP_ENDPOINT, and nothing at
all when it isn't set. Content stays off: services add decisions,
categories, tools and timings to spans, never arguments, results,
questions or answers (fitness function FF9).
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter

ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"


def install_tracing(service_name: str, exporter: SpanExporter | None = None) -> None:
    """Send spans to `exporter` (tests), or to the OTLP endpoint if one is set; otherwise do nothing."""
    if exporter is None:
        if not os.environ.get(ENDPOINT_ENV):
            return
        processor: SimpleSpanProcessor | BatchSpanProcessor = BatchSpanProcessor(OTLPSpanExporter())
    else:
        processor = SimpleSpanProcessor(exporter)
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
