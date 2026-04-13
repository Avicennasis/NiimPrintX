# Round 23 Deep Code Review — Design Spec

**Date:** 2026-04-13
**Version:** 0.8.0 (current)
**Goal:** Comprehensive blind audit of entire codebase. Converge toward 3-6 minor findings per round.

## Context

NiimPrintX is a Python CLI + Tkinter GUI app for NiimBot BLE label printers. Forked from abandoned `labbots/NiimPrintX`, with 22 prior review rounds producing 400+ fixes across 101 files (17,745 insertions). Current state: 380 tests, 0 ruff errors, 90% coverage threshold, mypy on core/CLI layers.

## Approach

**Layer-based audit with cross-cutting specialists.** 25 parallel agents, each owning a slice of the codebase, reporting findings in a structured format. Three cross-cutting agents catch issues that span layers.

## Agent Allocation

### Group 1 — Core Protocol (5 agents)

| Agent | Scope | Focus |
|-------|-------|-------|
| 1 | `nimmy/printer.py` | BLE state machine, print jobs, error paths, async flow |
| 2 | `nimmy/bluetooth.py` | BLE transport, connect/disconnect lifecycle, write paths |
| 3 | `nimmy/packet.py`, `nimmy/exception.py`, `nimmy/logger_config.py` | Packet encoding/decoding, error types, logging config |
| 4 | `nimmy/userconfig.py`, `nimmy/types.py` | Config loading/validation, TypedDict definitions |
| 5 | Cross-review of agents 1-4 | Interactions between printer-bluetooth-packet, async flow correctness |

### Group 2 — CLI Layer (3 agents)

| Agent | Scope | Focus |
|-------|-------|-------|
| 6 | `cli/command.py` | Click commands, argument validation, print flow |
| 7 | `cli/helper.py`, `cli/__init__.py`, `cli/__main__.py` | Rich output, entry points |
| 8 | CLI integration | End-to-end CLI paths, error propagation from core to user |

### Group 3 — UI Widgets (6 agents)

| Agent | Scope | Focus |
|-------|-------|-------|
| 9 | `ui/AppConfig.py`, `ui/config.py` | State management, former god object split |
| 10 | `ui/widget/FileMenu.py`, `ui/SplashScreen.py` | File I/O, save/load, startup |
| 11 | `ui/widget/CanvasOperation.py`, `ui/widget/CanvasSelector.py` | Canvas drawing, selection, resize |
| 12 | `ui/widget/ImageOperation.py`, `ui/widget/TextOperation.py`, `ui/widget/TextTab.py` | Content manipulation |
| 13 | `ui/widget/PrinterOperation.py`, `ui/widget/PrintOption.py`, `ui/widget/StatusBar.py` | Print flow UI, status |
| 14 | `ui/widget/IconTab.py`, `ui/widget/TabbedIconGrid.py`, `ui/component/FontList.py`, `ui/__init__.py`, `ui/__main__.py`, `ui/types.py` | Components, grids, fonts |

### Group 4 — Tests (4 agents)

| Agent | Scope | Focus |
|-------|-------|-------|
| 15 | `test_printer.py`, `test_bluetooth.py`, `test_packet.py` | Core test quality, assertion strength, mock correctness |
| 16 | `test_cli.py`, `test_cli_command.py`, `test_config.py`, `test_userconfig.py` | CLI/config test quality |
| 17 | `test_fontlist.py`, `test_image_encoding.py`, `test_integration.py`, `test_print_integration.py` | Integration test quality |
| 18 | `test_coverage_gaps.py`, `test_round22_gaps.py`, `test_review_fixes.py`, `test_ui_guards.py`, remaining test files | Gap coverage audit, test quality |

### Group 5 — CI/CD + Build (4 agents)

| Agent | Scope | Focus |
|-------|-------|-------|
| 19 | `ci.yaml`, `dependabot.yml` | CI pipeline completeness, linting, audit job |
| 20 | `tag.yaml`, release flow | Release pipeline, version validation |
| 21 | All 6 PyInstaller spec files | Build correctness, cross-platform issues |
| 22 | `_build-linux.yaml`, `_build-windows.yaml`, `_build-macos.yaml`, `mac-dmg-builder.sh` | Build workflow correctness |

### Group 6 — Cross-cutting (3 agents)

| Agent | Scope | Focus |
|-------|-------|-------|
| 23 | All source files | Security: input validation, BLE attack surface, injection, resource exhaustion |
| 24 | All async code | Concurrency: race conditions, lock usage, event loop lifecycle |
| 25 | All source files | Code quality: dead code, redundancy, naming, structure, simplification |

## Finding Format

Each agent reports findings as:

```
- SEVERITY: CRITICAL / HIGH / MEDIUM / LOW
- FILE: path:line_number
- CATEGORY: bug / security / performance / code-quality / test-gap / ci-cd / dead-code / simplification
- DESCRIPTION: What's wrong
- SUGGESTION: How to fix it
- CONFIDENCE: HIGH / MEDIUM
```

No LOW-confidence findings. If not at least medium confident, don't report.

## Post-Audit Process

1. Deduplicate and consolidate all 25 agent reports
2. Sort by severity (CRITICAL > HIGH > MEDIUM > LOW)
3. Present prioritized report to user
4. Fix in severity order
5. Run tests + lint after each batch of fixes
6. Update TODO.md and CHANGELOG.md with results

## Success Criteria

Round is successful when a subsequent audit finds only 3-6 minor (LOW/MEDIUM) issues. This round aims to close the gap toward that target.

## Existing Tooling

- **Ruff:** 22 rule categories, line-length 120, Python 3.12 target
- **mypy:** strict on `nimmy/` and `cli/`, `ignore_missing_imports=True`
- **pytest:** 380 tests, asyncio_mode=auto, branch coverage, fail_under=90
- **CI:** test (3.12+3.13 matrix), lint, dependency audit, release builds (3 platforms)
