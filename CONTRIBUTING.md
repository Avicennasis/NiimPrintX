# Contributing to NiimPrintX (this fork)

Thanks for considering a contribution. Before you open a PR, please note
the **fork relationship** — see [NOTICE.md](NOTICE.md) for the full
upstream attribution.

- **Bug reports and feature requests against NiimPrintX core** belong
  upstream at [labbots/NiimPrintX](https://github.com/labbots/NiimPrintX/issues).
  Patches that would benefit the upstream community land best upstream
  first; this fork can carry them as cherry-picks afterward.
- **PRs for this fork** are welcome for: the multi-OS build pipeline,
  the security-review patch series, fork-side bug fixes, repo-meta
  improvements, and changes the upstream maintainer has indicated they
  do not want to merge.

## Dev setup

```bash
git clone https://github.com/Avicennasis/NiimPrintX.git
cd NiimPrintX
pipx install poetry
poetry install --with dev
poetry run pre-commit install
```

The project is Poetry-managed (`pyproject.toml` `[tool.poetry]`) — `pip
install -e .` won't work because Poetry's dependency format is not
PEP 621.

## Running the tests

```bash
poetry run pytest
```

CI runs the tests against Python 3.12 / 3.13 (3.14 is in the matrix as
`continue-on-error`). Make sure they pass locally before opening a PR.

## Code style

This project uses [ruff](https://github.com/astral-sh/ruff) for linting
and formatting, plus [mypy](https://mypy.readthedocs.io/) for type
checking and [pip-audit](https://github.com/pypa/pip-audit) for
known-vulnerability scans. All three are wired in via pre-commit.

```bash
poetry run pre-commit run --all-files
```

CI runs the same hooks. The ruff configuration lives at `ruff.toml` —
the rule set has been intentionally tuned for this codebase's BLE
state-machine and printer-API patterns; if you find a flagged
violation that's a false positive for those domains, please open an
issue rather than blanket-suppressing.

## PR checklist

- [ ] Tests added or updated; `poetry run pytest` is green locally.
- [ ] `poetry run pre-commit run --all-files` is clean.
- [ ] README and docs updated if public behavior changed.
- [ ] `CHANGELOG.md` updated under `[Unreleased]`.
- [ ] If the patch is fork-only and shouldn't go upstream, note that
      in the PR description so it doesn't accidentally get sent
      upstream later.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
Be respectful; assume good faith.
