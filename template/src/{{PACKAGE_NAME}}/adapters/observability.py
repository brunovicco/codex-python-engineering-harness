"""Opt-in, vendor-neutral OpenTelemetry tracing.

No SDK or exporter is created unless an OTLP endpoint is explicitly configured. Callers receive
the API's no-op tracer in every disabled state, keeping the default runtime network-silent.
"""

import contextlib
import os
import re
import threading
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
from typing import Any

from opentelemetry.context import Context
from opentelemetry.propagators.textmap import CarrierT
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import (
    Link,
    NoOpTracerProvider,
    Span,
    SpanContext,
    SpanKind,
    Status,
    StatusCode,
    Tracer,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util import types as otel_types

type AttributeScalar = str | bool | int | float

ALLOWED_SPAN_ATTRIBUTE_KEYS = frozenset(
    {
        "app.operation",
        "app.outcome",
        "app.retry_count",
        "error.type",
        "messaging.operation.type",
        "rpc.method",
    }
)
MAX_SPAN_ATTRIBUTES = 16
MAX_ATTRIBUTE_STRING_LENGTH = 128
MAX_OPERATION_NAME_LENGTH = 128
_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
_RESOURCE_KEYS = frozenset({"service.name", "service.version", "deployment.environment.name"})
_PROPAGATOR = TraceContextTextMapPropagator()
_SAFE_OPERATION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")


def sanitize_span_attributes(attributes: Mapping[str, Any] | None) -> dict[str, AttributeScalar]:
    """Return only bounded, explicitly safe custom span attributes."""
    sanitized: dict[str, AttributeScalar] = {}
    for key, value in (attributes or {}).items():
        if len(sanitized) >= MAX_SPAN_ATTRIBUTES:
            break
        if key not in ALLOWED_SPAN_ATTRIBUTE_KEYS or not isinstance(value, (str, bool, int, float)):
            continue
        if isinstance(value, str) and len(value) > MAX_ATTRIBUTE_STRING_LENGTH:
            continue
        sanitized[key] = value
    return sanitized


def _safe_operation_name(name: str, *, fallback: str) -> str:
    if (
        name
        and len(name) <= MAX_OPERATION_NAME_LENGTH
        and _SAFE_OPERATION_NAME.fullmatch(name) is not None
    ):
        return name
    return fallback


def _safe_links(links: Sequence[Link] | None) -> tuple[Link, ...] | None:
    if links is None:
        return None
    return tuple(Link(link.context, sanitize_span_attributes(link.attributes)) for link in links)


class SafeSpan(Span):
    """Expose span operations while enforcing metadata-only telemetry."""

    def __init__(self, delegate: Span) -> None:
        """Wrap one SDK span without exposing its unrestricted mutation surface."""
        self.__delegate = delegate

    def end(self, end_time: int | None = None) -> None:
        """End the underlying span."""
        self.__delegate.end(end_time=end_time)

    def get_span_context(self) -> SpanContext:
        """Return the immutable context used for propagation."""
        return self.__delegate.get_span_context()

    def set_attributes(self, attributes: Mapping[str, otel_types.AttributeValue]) -> None:
        """Set only allowlisted, bounded attributes."""
        self.__delegate.set_attributes(sanitize_span_attributes(attributes))

    def set_attribute(self, key: str, value: otel_types.AttributeValue) -> None:
        """Set one attribute only when it passes the metadata policy."""
        sanitized = sanitize_span_attributes({key: value})
        if key in sanitized:
            self.__delegate.set_attribute(key, sanitized[key])

    def add_event(
        self,
        name: str,
        attributes: otel_types.Attributes = None,
        timestamp: int | None = None,
    ) -> None:
        """Add an event with a safe name and sanitized attributes."""
        self.__delegate.add_event(
            _safe_operation_name(name, fallback="event.redacted"),
            sanitize_span_attributes(attributes),
            timestamp,
        )

    def add_link(
        self,
        context: SpanContext,
        attributes: otel_types.Attributes = None,
    ) -> None:
        """Add a link without propagating unapproved link attributes."""
        self.__delegate.add_link(context, sanitize_span_attributes(attributes))

    def update_name(self, name: str) -> None:
        """Update the span with a bounded operation identifier."""
        self.__delegate.update_name(_safe_operation_name(name, fallback="operation.redacted"))

    def is_recording(self) -> bool:
        """Return whether the underlying span records telemetry."""
        return self.__delegate.is_recording()

    def set_status(
        self,
        status: Status | StatusCode,
        description: str | None = None,
    ) -> None:
        """Set status without recording a potentially sensitive description."""
        del description
        status_code = status.status_code if isinstance(status, Status) else status
        self.__delegate.set_status(status_code)

    def record_exception(
        self,
        exception: BaseException,
        attributes: otel_types.Attributes = None,
        timestamp: int | None = None,
        escaped: bool = False,
    ) -> None:
        """Record only the exception type, never its message or stack."""
        del attributes, timestamp, escaped
        self.set_attribute("error.type", type(exception).__name__)


class SafeTracer:
    """Create spans through a bounded, metadata-only OpenTelemetry surface."""

    def __init__(self, delegate: Tracer) -> None:
        """Wrap one OpenTelemetry tracer with mandatory sanitization."""
        self.__delegate = delegate

    def start_span(
        self,
        name: str,
        context: Context | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: otel_types.Attributes = None,
        links: Sequence[Link] | None = None,
        start_time: int | None = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ) -> SafeSpan:
        """Start a non-current span through the safe telemetry surface."""
        del record_exception, set_status_on_exception
        return SafeSpan(
            self.__delegate.start_span(
                _safe_operation_name(name, fallback="operation.redacted"),
                context=context,
                kind=kind,
                attributes=sanitize_span_attributes(attributes),
                links=_safe_links(links),
                start_time=start_time,
                record_exception=False,
                set_status_on_exception=False,
            )
        )

    @contextlib.contextmanager
    def start_as_current_span(
        self,
        name: str,
        context: Context | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: otel_types.Attributes = None,
        links: Sequence[Link] | None = None,
        start_time: int | None = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        end_on_exit: bool = True,
    ) -> Iterator[SafeSpan]:
        """Start a sanitized span and make its SDK delegate current."""
        del record_exception, set_status_on_exception
        with self.__delegate.start_as_current_span(
            _safe_operation_name(name, fallback="operation.redacted"),
            context=context,
            kind=kind,
            attributes=sanitize_span_attributes(attributes),
            links=_safe_links(links),
            start_time=start_time,
            record_exception=False,
            set_status_on_exception=False,
            end_on_exit=end_on_exit,
        ) as span:
            yield SafeSpan(span)


def inject_trace_context(carrier: MutableMapping[str, str], context: Context | None = None) -> None:
    """Inject W3C Trace Context headers without propagating baggage."""
    _PROPAGATOR.inject(carrier, context=context)


def extract_trace_context(carrier: CarrierT) -> Context:
    """Extract W3C Trace Context headers without accepting baggage."""
    return _PROPAGATOR.extract(carrier=carrier)


def _resource_attributes(
    *, service_name: str, service_version: str, environment: str
) -> dict[str, str]:
    attributes = {
        "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
        "service.version": service_version,
        "deployment.environment.name": environment,
    }
    for item in os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "").split(","):
        key, separator, value = item.partition("=")
        key = key.strip()
        value = value.strip()
        if (
            separator
            and key in _RESOURCE_KEYS
            and value
            and len(value) <= MAX_ATTRIBUTE_STRING_LENGTH
        ):
            attributes[key] = value
    return attributes


def _is_enabled() -> bool:
    disabled = os.environ.get("OTEL_SDK_DISABLED", "false").strip().lower() in _TRUE_VALUES
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    return not disabled and bool(endpoint and endpoint.strip())


class TelemetryLifecycle:
    """Own one optional tracer provider and its bounded, idempotent lifecycle."""

    def __init__(
        self,
        *,
        service_name: str,
        service_version: str,
        environment: str,
        exporter_factory: Callable[[], SpanExporter] | None = None,
    ) -> None:
        """Configure identity and an optional test exporter factory without side effects."""
        self._service_name = service_name
        self._service_version = service_version
        self._environment = environment
        self._exporter_factory = exporter_factory
        self._provider: TracerProvider | None = None
        self._tracer = SafeTracer(NoOpTracerProvider().get_tracer(service_name, service_version))
        self._initialized = False
        self._shutdown = False
        self._lock = threading.Lock()

    @property
    def tracer(self) -> SafeTracer:
        """Return the initialized tracer, or an OpenTelemetry no-op tracer."""
        return self._tracer

    def initialize(self) -> SafeTracer:
        """Initialize at most once and isolate exporter construction failures."""
        with self._lock:
            if self._initialized or self._shutdown:
                return self._tracer
            self._initialized = True
            if not _is_enabled():
                return self._tracer
            try:
                exporter = (
                    self._exporter_factory()
                    if self._exporter_factory is not None
                    else _build_otlp_exporter()
                )
                provider = TracerProvider(
                    resource=Resource(
                        attributes=_resource_attributes(
                            service_name=self._service_name,
                            service_version=self._service_version,
                            environment=self._environment,
                        )
                    )
                )
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except Exception:
                return self._tracer
            self._provider = provider
            self._tracer = SafeTracer(
                provider.get_tracer(self._service_name, self._service_version)
            )
            return self._tracer

    def force_flush(self, *, timeout_seconds: float = 5.0) -> bool:
        """Attempt a flush without blocking the caller beyond the supplied bound."""
        provider = self._provider
        if provider is None or self._shutdown:
            return True
        return _bounded_call(
            lambda: provider.force_flush(timeout_millis=max(0, int(timeout_seconds * 1000))),
            timeout_seconds,
        )

    def shutdown(self, *, timeout_seconds: float = 5.0) -> bool:
        """Shut down once without propagating or indefinitely waiting on exporter failures."""
        with self._lock:
            if self._shutdown:
                return True
            self._shutdown = True
            provider = self._provider
        if provider is None:
            return True
        return _bounded_call(provider.shutdown, timeout_seconds)


def _bounded_call(operation: Callable[[], Any], timeout_seconds: float) -> bool:
    completed = threading.Event()
    succeeded = False

    def run() -> None:
        nonlocal succeeded
        try:
            result = operation()
            succeeded = result is not False
        except Exception:
            succeeded = False
        finally:
            completed.set()

    threading.Thread(target=run, daemon=True).start()
    completed.wait(timeout=max(0.0, timeout_seconds))
    return completed.is_set() and succeeded


def _build_otlp_exporter() -> SpanExporter:
    """Import the optional exporter only after explicit endpoint configuration."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    return OTLPSpanExporter()
