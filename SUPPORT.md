# Support policy

This project is maintained on a best-effort basis. It does not provide a service-level agreement,
guaranteed response time, production operations support, or consulting through public issues.

## Supported requests

Open a GitHub issue using the appropriate form for:

- reproducible defects in the bootstrap, plugin, hooks, validators, or generated profiles;
- documentation that is incorrect or prevents successful evaluation;
- focused feature requests that benefit the reusable harness;
- compatibility problems with supported Python, Codex, or uv versions.

Include a minimal reproduction, version or commit, environment details, and sanitized output.

## Feature requests

Features are evaluated according to reusable value, maintenance cost, portability, backward
compatibility, security and privacy impact, and whether deterministic enforcement belongs in the
harness. Application-specific behavior, vendor-specific production infrastructure, and controls
that only create the appearance of compliance may be declined even when technically feasible.

Acceptance of an issue does not commit the maintainer to a delivery date. A focused pull request is
welcome after the proposal's scope and design have been discussed.

## Questions and troubleshooting

Review `README.md`, its five-minute evaluation, `docs/UPGRADING.md`, and generated project
documentation before opening an issue. Usage questions without a reproducible harness problem may
be closed or converted into documentation suggestions.

## Security and conduct

Do not report suspected vulnerabilities in public issues. Use the private reporting process in
`SECURITY.md`. Participation in project spaces is governed by `CODE_OF_CONDUCT.md`.

## Support window

Only the latest release and the default branch receive fixes. Generated repositories remain owned
by their users and are not automatically patched when the harness changes.
