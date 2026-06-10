# 2026-06-09 — in-house-spec v1.2.0 baseline audit

**Spec**: in-house-spec v1.2.0 (`IN-HOUSE-CONVENTIONS.md`)
**Auditor**: Claude (automated `bin/check-spec.py --audit` + manual review)
**Repo state at audit**: branch `main`, commit `4d2bf00`

## Deployment-model assessment

NiimPrintX is **not a deployed fleet service**. It is a **Python
library + CLI/GUI** for NiimBot Bluetooth label printers (Poetry
project, console scripts `niimprintx` / `niimprintx-ui`), a
substantially-diverged fork of `labbots/NiimPrintX`, distributed as
source and as multi-OS PyInstaller release binaries via operator-managed
CI. It runs on the consumer's machine; its only external communication
is BLE to the printer. No server component, no network API, no systemd
unit, no container. The wiki has no `projects/niimprintx.md` service
page; the git-standards rollout log
(`operations/git-standards-rollout.md`) records it as a fork-pattern
product repo with a release-tier opt-out (Finding Y: multi-OS
PyInstaller pipelines). The in-house-spec's service baseline
(systemd/Docker profile, FastAPI auth/CSRF/rate-limiting/health/metrics
contracts, deploy.sh) therefore does not apply.

**Recommendation: adopt-on-deploy.** If a hosted print service is ever
built on top of this library, that service must adopt the full
in-house-spec baseline at deploy time. Until then, only the cheap
universal items apply.

## Checker output (before)

`check-spec.py --audit NiimPrintX` — 5 findings:

1. missing required file: `requirements.in`
2. missing required file: `requirements.lock`
3. missing required file: `docs/audits/README.md`
4. missing required file: `deploy.sh`
5. missing unit file `NiimPrintX-host.service` (and no compose file for
   the Docker profile)

(`.pre-commit-config.yaml` and `.gitignore` venv/ already pass.)

## Disposition

| Finding | Disposition |
|---|---|
| `requirements.in` / `requirements.lock` | **N/A — library, deliberate.** The spec's pip-compile lockfile contract targets deployed *applications*. NiimPrintX is a **library**: it pins loosely in `pyproject.toml` (Poetry caret ranges) by design so consumers can resolve compatible versions, and `poetry.lock` provides dev/CI reproducibility. The committed `requirements.txt` is a documented convenience export for pip users, not a lockfile. **No `requirements.lock` was (or should be) generated.** If an app/service is ever deployed from this code, that deployment adopts the lockfile contract. |
| `docs/audits/README.md` | **Fixed** — index created, this shard is the first entry. |
| `deploy.sh` | **N/A** — no deploy target; distribution is source + PyInstaller release artifacts. Adopt-on-deploy. |
| unit file / compose file | **N/A** — no runtime host. Adopt-on-deploy. |
| `SECURITY.md` threat model (§Documentation, manual check) | **Fixed** — threat model appended to the existing fork-aware policy: untrusted-BLE-peripheral boundary, library-consumer process boundary, image-input pipeline, release distribution chain; Authelia assumption explicitly N/A; library-vs-app pinning policy recorded. |

Checker quirk (same as TaskAlarm audit): expected unit name is derived
from the directory name verbatim (`NiimPrintX-host.service`). Not
actionable — unit is N/A.

## Checker output (after)

4 findings remain, all N/A per the table above (`requirements.in`,
`requirements.lock`, `deploy.sh`, unit/compose file). Finding 3
(docs/audits index) is resolved.

## Secrets scan

No inline secrets found in tracked files. `.env` is gitignored and
absent; no hardcoded tokens or credential literals. Upstream contact
emails in SECURITY.md/NOTICE.md are intentional public attribution,
not secrets.
