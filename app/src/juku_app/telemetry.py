"""The app's spans (stub: lands with the chat)."""

from __future__ import annotations

from opentelemetry.sdk.trace.export import SpanExporter


def install_tracing(exporter: SpanExporter | None = None) -> None:
    raise NotImplementedError
