"""Tests for the structured logging bootstrap."""

import json
import logging
from collections.abc import Iterator

import pytest
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from {{PACKAGE_NAME}}.entrypoints.logging import (
    bind_correlation_id,
    clear_request_context,
    configure_logging,
)


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    """Reset stdlib logging handlers before and after each test."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    yield
    root.handlers = original_handlers


def test_configure_logging_emits_json_with_service_fields_when_json_format(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configured logger writes one JSON line with the bound service fields."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging(service="billing", environment="test", version="1.2.3")

    logging.getLogger(__name__).info("order_created")

    output = capsys.readouterr().out.strip()
    payload = json.loads(output)
    assert payload["service"] == "billing"
    assert payload["environment"] == "test"
    assert payload["version"] == "1.2.3"
    assert payload["event"] == "order_created"


def test_configure_logging_respects_log_level(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DEBUG record is dropped when LOG_LEVEL is INFO."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging(service="billing", environment="test", version="1.2.3")

    logging.getLogger(__name__).debug("noisy_detail")

    assert capsys.readouterr().out.strip() == ""


def test_clear_request_context_keeps_process_wide_fields(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clearing per-request context drops correlation IDs but keeps service fields."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging(service="billing", environment="test", version="1.2.3")
    bind_correlation_id("req-1")

    clear_request_context()
    logging.getLogger(__name__).info("after_clear")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["service"] == "billing"
    assert "correlation_id" not in payload
    assert "trace_id" not in payload


def test_logs_include_only_valid_current_trace_context(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid current spans are correlated; the ambient no-span state is not."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    configure_logging(service="billing", environment="test", version="1.2.3")
    tracer = TracerProvider().get_tracer("test")

    structlog.contextvars.bind_contextvars(trace_id="forged-trace", span_id="stale-span")
    logging.getLogger(__name__).info("outside", extra={"trace_id": "forged-extra"})
    with tracer.start_as_current_span("inside") as span:
        logging.getLogger(__name__).info("inside")
        context = span.get_span_context()

    outside, inside = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert "trace_id" not in outside
    assert "span_id" not in outside
    assert inside["trace_id"] == trace.format_trace_id(context.trace_id)
    assert inside["span_id"] == trace.format_span_id(context.span_id)
