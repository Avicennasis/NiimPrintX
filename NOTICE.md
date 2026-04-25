# NOTICE

This repository is a substantially-diverged source fork of the upstream
**NiimPrintX** project, originally authored by **labbots**.

## Upstream

- **Project:** NiimPrintX
- **Original author:** labbots &lt;labbots@gmail.com&gt;
- **Upstream repository:** https://github.com/labbots/NiimPrintX
- **License:** GNU General Public License v3.0 only (GPL-3.0-only)
- **License text:** [`LICENSE`](LICENSE) (verbatim GPL-3.0)

The upstream project provides a Python library / CLI / GUI for driving
NiimBot Bluetooth label printers — supported models include D11/B21/B1,
D110, B18, and several others (see upstream README for the canonical list).

## Divergence

This fork was created via manual import (the GitHub fork relationship is
not preserved — `parent: null` per `gh repo view`). At time of this
notice, divergence consists of approximately **94 commits authored by
Avicennasis** on top of the upstream baseline, while the upstream's
93 commits remain attributable to labbots and other upstream
contributors.

Avicennasis-side changes include (non-exhaustive):

- **CI / supply chain** — multi-Python matrix CI (`ci.yaml`), pre-commit
  config (ruff + mypy + pip-audit), per-OS PyInstaller build pipelines
  (`_build-{linux,macos,windows}.yaml`), tag-triggered release workflow
  (`tag.yaml`), pinned Action SHAs, GitHub Actions dependabot, ruff
  configuration (`ruff.toml`).
- **Security hardening** — multiple deep-code-review rounds (Rounds 14
  through 26 in the changelog history), CVE remediation (e.g.
  pygments CVE-2026-4539), input validation tightening, exception-flow
  cleanup.
- **Bug fixes carried as patches** — e.g. Tcl raw-bytes vs base64 image
  export handling.
- **Standard repo plumbing** added by the
  [`/git-standards`](https://github.com/Avicennasis/wiki.simmons.systems/blob/main/operations/new-github-repo-setup.md)
  rollout: `.editorconfig`, `.gitattributes`, `.github/FUNDING.yml`,
  `.github/CODEOWNERS`, `.github/pull_request_template.md`,
  `.github/ISSUE_TEMPLATE/*`,
  `.github/workflows/{scorecard,release-drafter,stale}.yml`,
  `.github/release-drafter.yml`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`,
  `SECURITY.md`, and this `NOTICE.md`. The pre-existing
  `.github/dependabot.yml` and `CHANGELOG.md` were left in place — both
  were already in fork-tuned shape (the dependabot config notes Poetry's
  incompatibility with the `pip` ecosystem; the changelog already
  follows Keep a Changelog).

The combined work is released under the same **GPL-3.0-only** license
as upstream — Avicennasis-side modifications are licensed under the
same terms; the upstream license governs the combined work.

## Reporting issues / sending patches

- **Bugs that affect upstream NiimPrintX** — please file upstream at
  the [labbots/NiimPrintX issue tracker](https://github.com/labbots/NiimPrintX/issues).
  Patches that would benefit upstream users belong upstream first.
- **Issues specific to this fork** (the multi-OS build pipeline, the
  Avicennasis-side CI, the security-review patch series) — file in this
  repository's [issue tracker](https://github.com/Avicennasis/NiimPrintX/issues).

The files [`UPSTREAM_ISSUES.md`](UPSTREAM_ISSUES.md) and
[`UPSTREAM_PULL_REQUESTS.md`](UPSTREAM_PULL_REQUESTS.md) at the repo
root track outstanding fork-side patches that are candidates for
upstreaming.
