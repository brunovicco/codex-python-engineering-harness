# Security policy

## Supported versions

Security fixes are provided for the latest minor release of the harness and the latest release of
the plugin. Generated projects are snapshots: they do not receive fixes automatically and must be
upgraded explicitly.

| Component | Supported line |
|---|---|
| Harness generator | 1.2.x |
| Python Engineering Harness plugin | 1.0.x |

## Reporting a vulnerability

Report vulnerabilities privately through the repository's
[GitHub Security Advisory form](https://github.com/brunovicco/codex-python-engineering-harness/security/advisories/new):

<https://github.com/brunovicco/codex-python-engineering-harness/security/advisories/new>

Include the affected component and version, reproduction steps, impact, and any suggested
mitigation. Do not include secrets or exploit details in a public issue. You should receive an
initial acknowledgement within seven calendar days. Remediation and coordinated disclosure
timelines depend on severity and complexity and will be agreed with the reporter.

## Scope

Reports are especially useful for destination-path or symlink escapes, unsafe merge behavior,
hook bypasses, secret exposure, MCP trust-boundary failures, command validation bypasses, and
supply-chain weaknesses in generated projects or the plugin.

The hooks, scanners, validators, and generated policies are defense-in-depth guardrails. They are
not a sandbox, do not replace operating-system isolation or least-privilege credentials, and do
not guarantee security or regulatory compliance.
