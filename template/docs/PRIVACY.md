# Privacy and data handling

Complete this document before processing personal or regulated data.

## Data inventory

| Data category | Source | Purpose | Legal/contractual basis | Destination | Retention | Deletion method |
|---|---|---|---|---|---|---|
| None documented | | | | | | |

## Controls

- Data minimization:
- Access control:
- Encryption in transit:
- Encryption at rest:
- Masking/tokenization:
- Non-production data strategy:
- Logging and tracing restrictions: document any enabled backend, content-capture approval,
  redaction, retention, and access policy. Add and follow a backend-specific policy before enabling
  content-bearing tracing. Generic OpenTelemetry spans are metadata-only: custom attributes pass
  through a bounded allowlist and must never contain prompts, responses, credentials,
  authorization headers, personal data, arbitrary URLs, tool output, or production payloads.
  The public tracing wrappers enforce this policy for span and event attributes, operation names,
  status descriptions, and exception details. W3C baggage is not propagated by default.
- Data-subject deletion/anonymization:
- External processors:
- Incident-response owner:

## Prohibited logging

Secrets, authentication headers, personal identifiers, full financial identifiers, complete request/response payloads, prompts, and model outputs containing sensitive data.
