"""Tests for the optional Langfuse tracing adapter."""

import sys
import types
from typing import Any, Self

import pytest

from {{PACKAGE_NAME}}.adapters.tracing import (
    NullLlmCallObserver,
    build_llm_call_observer,
    sanitize_metadata,
)


class _FakeGeneration:
    """Stand-in for the Langfuse SDK's generation context manager."""

    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def update(self, **kwargs: Any) -> None:
        """Record the fields passed to this generation."""
        self.updates.append(kwargs)


class _FakeLangfuseClient:
    """Stand-in for ``langfuse.get_client()`` that records every call."""

    def __init__(self) -> None:
        self.generation = _FakeGeneration()

    def start_as_current_observation(self, **_: Any) -> _FakeGeneration:
        """Return the single tracked generation for inspection in tests."""
        return self.generation


def _install_fake_langfuse(monkeypatch: pytest.MonkeyPatch, client: _FakeLangfuseClient) -> None:
    """Inject a fake ``langfuse`` module so tests don't need the real package."""
    fake_module = types.ModuleType("langfuse")
    fake_module.get_client = lambda: client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", fake_module)


def test_build_llm_call_observer_is_a_no_op_when_credentials_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tracing stays opt-in: no credentials means no observer is built."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    observer = build_llm_call_observer()

    assert isinstance(observer, NullLlmCallObserver)


def test_build_llm_call_observer_is_a_no_op_with_only_one_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both keys are required; a partial credential pair still no-ops."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    observer = build_llm_call_observer()

    assert isinstance(observer, NullLlmCallObserver)


def test_build_llm_call_observer_is_a_no_op_when_package_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credentials alone are not enough; the optional package must be installed."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setitem(sys.modules, "langfuse", None)

    observer = build_llm_call_observer()

    assert isinstance(observer, NullLlmCallObserver)


def test_null_observer_record_never_raises() -> None:
    """The no-op observer silently discards any call outcome."""
    NullLlmCallObserver().record(
        name="classify-ticket",
        model="gpt-5",
        latency_seconds=0.42,
        prompt="ignored",
        completion="ignored",
    )


def test_observer_withholds_content_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt/completion are withheld unless capture is explicitly enabled."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.delenv("LANGFUSE_CAPTURE_CONTENT", raising=False)
    client = _FakeLangfuseClient()
    _install_fake_langfuse(monkeypatch, client)

    observer = build_llm_call_observer()
    observer.record(
        name="classify-ticket",
        model="gpt-5",
        latency_seconds=0.5,
        input_tokens=10,
        output_tokens=20,
        prompt="secret prompt",
        completion="secret completion",
    )

    recorded = client.generation.updates[0]
    assert recorded["input"] is None
    assert recorded["output"] is None
    assert recorded["usage_details"] == {"input": 10, "output": 20}
    assert recorded["metadata"]["latency_seconds"] == 0.5


def test_observer_forwards_content_when_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting LANGFUSE_CAPTURE_CONTENT=true forwards prompt and completion."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_CAPTURE_CONTENT", "true")
    client = _FakeLangfuseClient()
    _install_fake_langfuse(monkeypatch, client)

    observer = build_llm_call_observer()
    observer.record(name="classify-ticket", model="gpt-5", latency_seconds=0.1)

    recorded = client.generation.updates[0]
    assert recorded["input"] is None  # no prompt was supplied for this call
    assert recorded["usage_details"] is None


def test_sanitize_metadata_drops_content_and_unbounded_values() -> None:
    """Only approved bounded metadata reaches the tracing backend."""
    sanitized = sanitize_metadata(
        {
            "provider": "anthropic",
            "outcome": "success",
            "prompt": "must not leave the process",
            "custom": {"nested": "object"},
            "feature": "x" * 257,
        }
    )

    assert sanitized == {"provider": "anthropic", "outcome": "success"}


def test_observer_does_not_propagate_backend_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tracing outages never fail a completed business operation."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    client = _FakeLangfuseClient()
    client.start_as_current_observation = lambda **_: (_ for _ in ()).throw(RuntimeError("down"))  # type: ignore[method-assign]
    _install_fake_langfuse(monkeypatch, client)

    observer = build_llm_call_observer()
    observer.record(name="classify-ticket", model="gpt-5", latency_seconds=0.1)
