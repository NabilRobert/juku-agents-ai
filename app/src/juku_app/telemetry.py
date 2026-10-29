"""The app's spans: PydanticAI's own instrumentation, with content off (Phase 2 M6; FF9)."""

from __future__ import annotations

from juku_common import telemetry
from opentelemetry.sdk.trace.export import SpanExporter

SERVICE_NAME = "juku-app"


def install_tracing(exporter: SpanExporter | None = None) -> None:
    telemetry.install_tracing(SERVICE_NAME, exporter)
