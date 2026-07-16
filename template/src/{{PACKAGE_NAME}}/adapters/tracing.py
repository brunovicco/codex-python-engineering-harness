"""Optional, failure-isolated Langfuse tracing for LLM calls.

Tracing is disabled without credentials. Content capture also requires the explicit opt-in
documented in ``docs/LLM_OBSERVABILITY.md``; otherwise only allowlisted metadata is sent.
"""

import os
from collections.abc import Mapping
from typing import Any, Protocol

type TraceScalar = str | int | float | bool | None
ALLOWED_METADATA_KEYS = frozenset(
    {
        "correlation_id",
        "environment",
        "feature",
        "operation",
        "outcome",
        "provider",
        "retry_count",
        "service",
        "trace_id",
    }
)
MAX_METADATA_STRING_LENGTH = 256


def sanitize_metadata(metadata: Mapping[str, Any] | None) -> dict[str, TraceScalar]:
    """Keep only bounded, explicitly approved non-content tracing metadata."""
    sanitized: dict[str, TraceScalar] = {}
    for key, value in (metadata or {}).items():
        if key not in ALLOWED_METADATA_KEYS:
            continue
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            continue
        if isinstance(value, str) and len(value) > MAX_METADATA_STRING_LENGTH:
            continue
        sanitized[key] = value
    return sanitized


class LlmCallObserver(Protocol):
    """Port for recording the outcome of one completed LLM call."""

    def record(
        self,
        *,
        name: str,
        model: str,
        latency_seconds: float,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        prompt: str | None = None,
        completion: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Record one completed LLM call."""
        ...


class NullLlmCallObserver:
    """No-op observer used when Langfuse tracing is not opted in."""

    def record(self, **_: Any) -> None:
        """Discard the call outcome."""
        return


class _LangfuseLlmCallObserver:
    """Observer that forwards call outcomes to a configured Langfuse client."""

    def __init__(self, client: Any, *, capture_content: bool) -> None:
        self._client = client
        self._capture_content = capture_content

    def record(
        self,
        *,
        name: str,
        model: str,
        latency_seconds: float,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        prompt: str | None = None,
        completion: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Record one completed LLM call as a Langfuse generation."""
        usage_details: dict[str, int] = {}
        if input_tokens is not None:
            usage_details["input"] = input_tokens
        if output_tokens is not None:
            usage_details["output"] = output_tokens

        safe_metadata = sanitize_metadata(metadata)
        safe_metadata["latency_seconds"] = latency_seconds
        try:
            with self._client.start_as_current_observation(
                as_type="generation", name=name, model=model
            ) as generation:
                generation.update(
                    input=prompt if self._capture_content else None,
                    output=completion if self._capture_content else None,
                    usage_details=usage_details or None,
                    metadata=safe_metadata,
                )
        except Exception:
            # Telemetry must not turn a completed model call into a business failure.
            return


def build_llm_call_observer() -> LlmCallObserver:
    """Build a Langfuse observer, or a no-op observer if tracing is not opted in.

    Requires the ``tracing`` optional dependency group
    (``uv sync --extra tracing``) and ``LANGFUSE_PUBLIC_KEY``/
    ``LANGFUSE_SECRET_KEY``; returns :class:`NullLlmCallObserver` otherwise.
    """
    if not os.environ.get("LANGFUSE_PUBLIC_KEY") or not os.environ.get("LANGFUSE_SECRET_KEY"):
        return NullLlmCallObserver()

    try:
        from langfuse import get_client
    except ImportError:
        return NullLlmCallObserver()

    capture_content = os.environ.get("LANGFUSE_CAPTURE_CONTENT", "false").strip().lower() == "true"
    return _LangfuseLlmCallObserver(get_client(), capture_content=capture_content)
