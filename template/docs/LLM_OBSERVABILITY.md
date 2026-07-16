# LLM observability policy

## Vendor-neutral application tracing

The service profile also provides a separate OpenTelemetry trace foundation in
`src/{{PACKAGE_NAME}}/adapters/observability.py`. Install it with
`uv sync --extra observability`. It uses the OpenTelemetry API/SDK, `BatchSpanProcessor`, and the
OTLP HTTP/protobuf exporter. This does not replace or alter the `LlmCallObserver` contract or the
existing `tracing` extra described below.

The lifecycle is disabled when `OTEL_SDK_DISABLED=true` or neither
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` nor `OTEL_EXPORTER_OTLP_ENDPOINT` is set. In either case it
does not construct an exporter, start a worker, or attempt a network connection. When enabled,
instantiate `TelemetryLifecycle` at process startup, use its returned `tracer`, and call its
bounded `force_flush()` and `shutdown()` methods during graceful termination. Exporter setup,
flush, shutdown, and asynchronous export failures are isolated from business operations.

Resource attributes are limited to `service.name`, `service.version`, and
`deployment.environment.name`. `OTEL_SERVICE_NAME` and safe values for those keys in
`OTEL_RESOURCE_ATTRIBUTES` are supported; all other resource keys are discarded. The custom span
attribute helper likewise accepts only a small set of non-content keys and bounded scalar values.
The lifecycle exposes `SafeTracer` and `SafeSpan` wrappers that apply the same policy to attributes
provided during span creation or mutation. Unsafe operation and event names are replaced with
stable redacted names; status descriptions and exception messages are not recorded. Never put
prompts, responses, credentials, authorization headers, personal data, arbitrary URLs, tool
output, or production payloads into spans.

Use `inject_trace_context()` and `extract_trace_context()` at transport boundaries. They use only
W3C `traceparent`/`tracestate`; baggage is intentionally not propagated. Structured logs derive
`trace_id` and `span_id` from a valid current span automatically and omit both otherwise.

### OpenTelemetry configuration

| Variable | Required | Purpose |
|---|---|---|
| `OTEL_SDK_DISABLED` | no | `true` forces a network-silent no-op |
| `OTEL_SERVICE_NAME` | no | Overrides the configured service name |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | one endpoint | Base OTLP HTTP endpoint |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | one endpoint | Trace-specific OTLP HTTP endpoint; takes precedence in the exporter |
| `OTEL_RESOURCE_ATTRIBUTES` | no | Only the three approved resource keys are accepted |

Tests use in-memory exporters and invalid placeholder endpoint names; they never require a
collector, network access, credentials, or an external service.

## Langfuse LLM tracing

This project can optionally trace LLM calls (latency, token usage, cost, and model name) to
Langfuse through `src/{{PACKAGE_NAME}}/adapters/tracing.py`. Structured application logging itself
is always configured through `src/{{PACKAGE_NAME}}/entrypoints/logging.py` and is not part of this
policy—it never carries prompts or model responses; see the security and observability contract
in `AGENTS.md`.

## Design principle

Tracing is opt-in and defaults to metadata only. `build_llm_call_observer()` returns a no-op
observer whenever the `tracing` optional dependency is not installed or Langfuse credentials are
not set, so application code never needs to branch on whether tracing is enabled.

## Default behavior

- No prompt or completion content is sent to Langfuse unless `LANGFUSE_CAPTURE_CONTENT=true` is
  set explicitly.
- Only metadata is recorded by default: call name, model, latency, token counts, and the bounded
  allowlisted fields enforced by `sanitize_metadata()`. Unknown, nested, content-bearing, and
  oversized metadata is discarded.

## Enabling tracing

1. Confirm a business need for prompt/response-level debugging or evaluation that latency and
   token metrics alone do not satisfy.
2. Choose a Langfuse deployment: cloud (`https://cloud.langfuse.com` EU,
   `https://us.cloud.langfuse.com` US, `https://jp.cloud.langfuse.com` Japan,
   or the HIPAA-eligible region) or self-hosted.
3. `uv sync --extra tracing` to install the `langfuse` package.
4. Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` from a secret manager
   or environment injection - never commit real values; `.env.example` documents the variable
   names only.
5. Keep `LANGFUSE_CAPTURE_CONTENT=false` unless the approval checklist below has been completed
   for this project.
6. Record the decision (scope, data classes, retention) in `docs/PRIVACY.md`.

## Approval checklist before enabling `LANGFUSE_CAPTURE_CONTENT=true`

- Named business and technical owner for the tracing data.
- Data classification of what a prompt or completion is expected to contain (PII, credentials,
  regulated data must not appear; if they can, redact at the call site before recording).
- Retention period configured in Langfuse and a deletion procedure.
- Access control for who can read traces in the Langfuse project.
- Non-production data used for any test or staging traces.
- Confirmation that no MCP tool output, secrets, or credentials can reach `prompt`/`completion`
  fields. The tracing adapter allowlists metadata, but when content capture is enabled the caller
  remains responsible for redacting the explicit `prompt` and `completion` values.

## Configuration reference

| Variable | Required | Purpose |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | to enable tracing | Project public key |
| `LANGFUSE_SECRET_KEY` | to enable tracing | Project secret key; environment-injected only |
| `LANGFUSE_BASE_URL` | no (defaults to EU cloud) | Cloud region or self-hosted URL |
| `LANGFUSE_CAPTURE_CONTENT` | no (defaults to `false`) | Set `true` only after the approval checklist |

## Uninstrumented by default

Leaving all four variables unset keeps the project fully untraced; `build_llm_call_observer()`
returns `NullLlmCallObserver`, which discards every call outcome. This matches the harness's MCP
governance model: nothing external is connected until a project deliberately opts in.
