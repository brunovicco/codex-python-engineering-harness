"""Tests for the opt-in OpenTelemetry tracing foundation."""

import time
from collections.abc import Iterator
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Status, StatusCode

from {{PACKAGE_NAME}}.adapters.observability import (
    TelemetryLifecycle,
    extract_trace_context,
    inject_trace_context,
    sanitize_span_attributes,
)


@pytest.fixture(autouse=True)
def _clean_otel_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep tests deterministic and independent of the developer environment."""
    for name in (
        "OTEL_SDK_DISABLED",
        "OTEL_SERVICE_NAME",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_RESOURCE_ATTRIBUTES",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


def _lifecycle(exporter: SpanExporter) -> TelemetryLifecycle:
    return TelemetryLifecycle(
        service_name="billing",
        service_version="1.2.3",
        environment="test",
        exporter_factory=lambda: exporter,
    )


def test_no_endpoint_and_disabled_sdk_never_construct_an_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every disabled mode is a no-op with no possible network construction."""
    calls = 0

    def exporter_factory() -> SpanExporter:
        nonlocal calls
        calls += 1
        return InMemorySpanExporter()

    lifecycle = TelemetryLifecycle(
        service_name="billing",
        service_version="1.2.3",
        environment="test",
        exporter_factory=exporter_factory,
    )
    assert not lifecycle.initialize().start_span("no-op").is_recording()
    assert calls == 0

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    disabled = TelemetryLifecycle(
        service_name="billing",
        service_version="1.2.3",
        environment="test",
        exporter_factory=exporter_factory,
    )
    assert not disabled.initialize().start_span("still-no-op").is_recording()
    assert calls == 0


def test_configured_tracing_exports_expected_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured spans use OTLP-compatible SDK data and privacy-safe resources."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector.invalid/v1/traces")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "payments")
    monkeypatch.setenv(
        "OTEL_RESOURCE_ATTRIBUTES",
        (
            "deployment.environment.name=staging,service.version=2.0,"
            "unsafe.payload=secret,prompt=private,url.full=https://private.invalid,"
            "credential.password=secret,arbitrary.resource=value"
        ),
    )
    exporter = InMemorySpanExporter()
    lifecycle = _lifecycle(exporter)
    tracer = lifecycle.initialize()
    with tracer.start_as_current_span("charge") as span:
        span.set_attributes(sanitize_span_attributes({"app.outcome": "ok"}))

    assert lifecycle.force_flush(timeout_seconds=1)
    exported = exporter.get_finished_spans()[0]
    assert exported.attributes == {"app.outcome": "ok"}
    assert exported.resource.attributes["service.name"] == "payments"
    assert exported.resource.attributes["service.version"] == "2.0"
    assert exported.resource.attributes["deployment.environment.name"] == "staging"
    assert set(exported.resource.attributes) == {
        "service.name",
        "service.version",
        "deployment.environment.name",
    }
    for rejected in (
        "unsafe.payload",
        "prompt",
        "url.full",
        "credential.password",
        "arbitrary.resource",
    ):
        assert rejected not in exported.resource.attributes
    assert lifecycle.shutdown(timeout_seconds=1)


def test_w3c_injection_and_extraction_preserve_parent_without_baggage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only traceparent/tracestate cross process boundaries."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid")
    exporter = InMemorySpanExporter()
    lifecycle = _lifecycle(exporter)
    tracer = lifecycle.initialize()
    carrier: dict[str, str] = {"baggage": "customer_id=forbidden"}
    with tracer.start_as_current_span("parent") as parent:
        inject_trace_context(carrier)
    extracted = extract_trace_context(carrier)
    with tracer.start_as_current_span("child", context=extracted):
        pass
    assert lifecycle.force_flush(timeout_seconds=1)
    child: ReadableSpan = next(
        span for span in exporter.get_finished_spans() if span.name == "child"
    )
    assert child.parent is not None
    assert child.parent.trace_id == parent.get_span_context().trace_id
    assert child.parent.span_id == parent.get_span_context().span_id
    assert "traceparent" in carrier
    assert carrier["baggage"] == "customer_id=forbidden"


def test_unsafe_nested_and_oversized_attributes_are_discarded() -> None:
    """The span attribute surface is a small bounded allowlist."""
    assert sanitize_span_attributes(
        {
            "app.outcome": "success",
            "app.operation": "x" * 129,
            "authorization": "Bearer secret",
            "prompt": "private",
            "url.full": "https://example.test/private",
            "tool.output": {"payload": "private"},
        }
    ) == {"app.outcome": "success"}


def test_public_tracing_api_cannot_bypass_metadata_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public tracer sanitizes creation and mutation paths before export."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid")
    exporter = InMemorySpanExporter()
    lifecycle = _lifecycle(exporter)
    tracer = lifecycle.initialize()

    with tracer.start_as_current_span(
        "customer prompt with spaces",
        attributes={"prompt": "private", "app.outcome": "started"},
    ) as span:
        span.set_attribute("prompt", "private")
        span.set_attribute("app.operation", "charge")
        span.set_attributes({"tool.output": "private", "app.retry_count": 1})
        span.add_event(
            "https://private.invalid/customer",
            {"authorization": "Bearer secret", "app.outcome": "retried"},
        )
        span.set_status(Status(StatusCode.ERROR, "secret production payload"))
        span.record_exception(RuntimeError("secret production payload"))

    assert lifecycle.force_flush(timeout_seconds=1)
    exported = exporter.get_finished_spans()[0]
    assert exported.name == "operation.redacted"
    assert exported.attributes == {
        "app.outcome": "started",
        "app.operation": "charge",
        "app.retry_count": 1,
        "error.type": "RuntimeError",
    }
    assert exported.events[0].name == "event.redacted"
    assert exported.events[0].attributes == {"app.outcome": "retried"}
    assert exported.status.status_code is StatusCode.ERROR
    assert exported.status.description is None
    serialized = exported.to_json()
    for forbidden in ("private", "secret", "prompt", "authorization", "tool.output"):
        assert forbidden not in serialized
    assert lifecycle.shutdown(timeout_seconds=1)


class _FailingExporter(SpanExporter):
    def export(self, spans: Any) -> SpanExportResult:
        del spans
        raise RuntimeError("backend unavailable")

    def shutdown(self) -> None:
        return None


class _BlockingTracerProvider(TracerProvider):
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        del timeout_millis
        time.sleep(1)
        return True


def test_export_failure_does_not_escape_business_span(monkeypatch: pytest.MonkeyPatch) -> None:
    """A completed operation remains successful when asynchronous export fails."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid")
    lifecycle = _lifecycle(_FailingExporter())
    with lifecycle.initialize().start_as_current_span("business-operation"):
        result = "completed"
    lifecycle.force_flush(timeout_seconds=1)
    assert result == "completed"
    lifecycle.shutdown(timeout_seconds=1)


def test_lifecycle_is_idempotent_and_operations_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated initialization/shutdown is safe and a blocked exporter cannot block callers."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid")
    exporter = InMemorySpanExporter()
    lifecycle = _lifecycle(exporter)
    first = lifecycle.initialize()
    assert lifecycle.initialize() is first

    lifecycle._provider = _BlockingTracerProvider()
    started = time.monotonic()
    assert not lifecycle.force_flush(timeout_seconds=0.01)
    assert time.monotonic() - started < 0.2
    assert lifecycle.shutdown(timeout_seconds=1)
    assert lifecycle.shutdown(timeout_seconds=0.01)
