"""One in-memory span exporter for the whole test run (a pytest plugin).

OpenTelemetry allows one global tracer provider per process, and setting
another is silently ignored, so each package's tests can't install their
own. They share this one and clear it before looking.
"""

from __future__ import annotations

import pytest
from juku_common.telemetry import install_tracing
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_EXPORTER = InMemorySpanExporter()
_installed = False


@pytest.fixture
def spans() -> InMemorySpanExporter:
    """Every span the code under test finishes, from a clean start."""
    global _installed
    if not _installed:
        install_tracing("juku-tests", _EXPORTER)
        _installed = True
    _EXPORTER.clear()
    return _EXPORTER
