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

## Threat model

NiimPrintX is a **Python library + CLI/GUI for NiimBot Bluetooth label
printers**, distributed via source / PyInstaller release binaries. It
runs entirely on the user's machine with the user's privileges; there
is no server component, no account system, and no telemetry. Its only
external communication is the Bluetooth (BLE) link to the printer.

### Trust boundaries

- **BLE link to the printer** — the primary boundary. The printer is an
  untrusted peripheral: NiimBot protocol responses (status frames,
  RFID/label metadata, ack packets) are untrusted input and must be
  length-checked and parsed defensively. Pairing and link-layer
  security are delegated to the OS Bluetooth stack (via `bleak`).
- **Library consumer ↔ library** — as a library, NiimPrintX runs in the
  consumer's process with the consumer's privileges; it must not
  require elevated rights beyond what the platform needs for BLE, and
  it makes no network calls of its own.
- **User-supplied content** — images and label content passed to the
  print pipeline are untrusted input to the imaging stack
  (Pillow/optional cairo+wand); decoding failures must be handled, and
  consumers should treat third-party image files as hostile.
- **Distribution chain** — consumers trust PyPI-style source installs /
  the fork's PyInstaller release artifacts built by the operator-managed
  multi-OS CI; no fleet deploy.

### Sensitive data handled

Label content and printer metadata only — typically low sensitivity,
local to the user's machine, transmitted only to the printer the user
selects. Logs (`loguru`) may echo label content locally.

### Adversaries in scope

- A hostile or spoofed BLE peripheral sending malformed/oversized
  protocol responses.
- Malicious or malformed image inputs handed to the print pipeline.
- (Fork-specific, per scope above) CI/build-pipeline compromise of
  release artifacts.

### Adversaries out of scope

- A compromised OS, Python runtime, or Bluetooth stack.
- Vulnerabilities in upstream NiimPrintX core (report upstream) or in
  dependencies (`bleak`, Pillow, etc. — report to their maintainers).
- Consumers running the CLI with unnecessary elevated privileges.

### Fleet-spec note

The in-house-spec (v1.2.0) Authelia/Traefik proxy-auth assumptions do
**not** apply: NiimPrintX is a distributed library/CLI with no deployed
service, no proxy, and no proxy-injected identity headers. As a
**library**, it pins dependencies loosely in `pyproject.toml` (caret
ranges) by design — application-style hard lockfiles apply only to
deployed apps; `poetry.lock` covers dev/CI reproducibility. If a hosted
print service is ever built on top of it, that service must adopt the
full in-house-spec baseline (auth, CSRF, rate limiting, health
contract, metrics, locked requirements) at deploy time.
