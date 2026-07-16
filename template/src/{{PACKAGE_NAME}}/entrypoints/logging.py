"""Structured logging bootstrap.

Call :func:`configure_logging` once, at process startup, before any other code
emits a log line. Renders JSON to stdout by default; set ``LOG_FORMAT=console``
for a human-readable renderer during local development. Never log secrets,
personal data, prompts, or model responses - see
the security and observability contract in ``AGENTS.md``.
"""

import logging
import os
import sys

import structlog


def add_trace_context(
    _: object, __: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    """Add identifiers only when the current OpenTelemetry span context is valid."""
    event_dict.pop("trace_id", None)
    event_dict.pop("span_id", None)
    try:
        from opentelemetry import trace
    except ImportError:
        return event_dict
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        event_dict["trace_id"] = trace.format_trace_id(context.trace_id)
        event_dict["span_id"] = trace.format_span_id(context.span_id)
    return event_dict


def configure_logging(*, service: str, environment: str, version: str) -> None:
    """Configure structlog and standard-library logging for this process."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    json_logs = os.environ.get("LOG_FORMAT", "json").strip().lower() != "console"

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_trace_context,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        service=service, environment=environment, version=version
    )


def bind_correlation_id(correlation_id: str, *, trace_id: str | None = None) -> None:
    """Bind a correlation ID; retain the old trace argument without trusting it for logs."""
    del trace_id
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def clear_request_context() -> None:
    """Clear per-request context variables without dropping process-wide fields.

    Removes only ``correlation_id``. Using
    :func:`structlog.contextvars.clear_contextvars` here would also drop the
    ``service``/``environment``/``version`` fields bound once at startup by
    :func:`configure_logging`, silently dropping them from every log line for
    the rest of the process.
    """
    structlog.contextvars.unbind_contextvars("correlation_id")
