# Security Policy

## Scope

This repository is a **fork** of upstream NiimPrintX (labbots) — see
[NOTICE.md](NOTICE.md). Vulnerabilities that affect the core library,
CLI, or BLE protocol implementation should be reported upstream so the
canonical maintainer can coordinate disclosure:

- Upstream issues: [labbots/NiimPrintX/issues](https://github.com/labbots/NiimPrintX/issues)
- Or, for a private channel, contact the upstream maintainer at
  **labbots@gmail.com**.

## What this policy covers

The narrow scope handled in this repository's issue tracker is
**fork-specific** issues — anything Avicennasis added on top of the
upstream source: the multi-OS build pipelines, the security-review
patch series, repo-meta files, fork-side CI, fork-side dependabot
config.

Examples of in-scope issues:

- The CI build pipeline pulling a malicious dependency or exposing
  secrets in workflow logs.
- A pinned Action SHA in workflow files that has been revoked or
  republished by GitHub.
- A regression introduced by one of the fork's deep-code-review patch
  series.

## Reporting a vulnerability (fork-specific)

Please **do not** open a public GitHub issue for security problems.

Email **Avicennasis@gmail.com** with:

- A description of the issue.
- Steps to reproduce (or a proof-of-concept).
- The version or commit SHA you found it against.
- Any suggested mitigation if you have one.

Expect an acknowledgement within a week. There is no bug bounty and no
SLA — this is a side-project — but security issues are taken seriously
and a fix and disclosure will be coordinated with you.

## Out of scope

- **Vulnerabilities in upstream NiimPrintX** that exist independently of
  this fork — report upstream (see above).
- Issues in pinned Python dependencies — report to the dependency
  maintainer (and to PyPI Security if appropriate).
- Misconfiguration by consumers (e.g. running the CLI as root with
  raw Bluetooth socket permissions when not needed).
