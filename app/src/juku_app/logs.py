"""Structured logs (structlog): JSON lines with the request and trace IDs, never content (Phase 2 M6; FF9).

Log events name what happened and its numbers: a path, a status, a
duration, a reason category. Never a question, an answer, a nickname or a
code. The trace ID ties a line to Project 6's trace.
"""

from __future__ import annotations

import logging

import structlog
from opentelemetry import trace
from structlog.typing import EventDict, WrappedLogger


def add_trace_id(_: WrappedLogger, __: str, event: EventDict) -> EventDict:
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        event["trace_id"] = f"{context.trace_id:032x}"
    return event


def configure_logging(level: int = logging.INFO) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_trace_id,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )
