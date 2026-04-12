# NiimPrintX Round 14 Deep Code Review

**Date:** 2026-04-12
**Method:** 25-agent parallel burn across all 55 Python files, 5 GitHub workflows, 6 PyInstaller specs, dependabot config
**Baseline:** v0.6.1, 315 tests passing, ruff clean, 96.76% coverage
**Runtime:** 7m 21s

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 8 |
| HIGH | 33 |
| MEDIUM | 22 |
| LOW | 15+ |

---

## CRITICAL Findings

### C1. `printer.py:209` — `start_page_print` never paired with `end_page_print` in error cleanup
**Agent 1** | Confidence: 88

After `start_page_print()` succeeds, the error cleanup block only sends `end_print()`, never `end_page_print()`. The printer sees `START_PRINT → START_PAGE_PRINT → END_PRINT` without the matching `END_PAGE_PRINT`. This leaves the printer locked until BLE connection drops. Reachable via the zero-dimension guard and `set_dimension` failures.

**Fix:** Add a `page_started` flag mirroring `print_started`. In the `except BaseException` cleanup, send `end_page_print()` (suppressed) before `end_print()`.

---

### C2. `TextOperation.py:154-156` — `tag_bind` accumulation on repeated select
**Agent 9** | Confidence: 90

`draw_bounding_box` binds `<B1-Motion>` to text items every time `select_text` is called. Since `tag_bind` appends handlers, repeatedly selecting the same item accumulates N handlers. Each drag event calls `move_text` N times, causing the item to jump by N×dx pixels.

**Fix:** Call `canvas.tag_unbind(text_id, "<B1-Motion>")` before re-binding in `draw_bounding_box`.

---

### C3. `main.py:129-146` — Shutdown coroutine stranded when loop stops mid-gather
**Agent 6** | Confidence: 85

`_poll_shutdown`'s timeout fallback calls `loop.stop()` which kills `_shutdown` mid-`await asyncio.gather(...)`. The coroutine frame is leaked and tasks never complete cleanly. Non-deterministic: works on fast machines, fails on slow ones with active heartbeat.

**Fix:** Restructure so `_poll_shutdown` only calls `loop.stop()` after `_shutdown_complete` is confirmed set. Never use the timeout as a race-bypass.

---

### C4. `PrintOption.py:94-110` — Button label reads shared mutable flag instead of operation result
**Agent 8** | Confidence: 95

`_update_device_status` ignores its `result` parameter and reads `config.printer_connected` instead. A heartbeat `after()` callback queued during connect can flip the flag after the connect succeeds, leaving the button in the wrong state.

**Fix:** Decide button label from `result` directly, not the shared mutable flag.

---

### C5. `ci.yaml:92` — `poetry export` broken in Poetry 2.x
**Agent 18** | Confidence: 92

Poetry 2.0+ unbundled `poetry-plugin-export`. The audit job calls `poetry export` without installing the plugin, so the audit job fails on every run.

**Fix:** Add `pipx inject poetry poetry-plugin-export` after the `pipx install poetry` step.

---

### C6. `tag.yaml` — No version check between git tag and pyproject.toml
**Agent 19** | Confidence: 90

A tag pushed while `pyproject.toml` has an older version creates release artifacts named `v0.6.1` but containing code versioned `0.5.0`.

**Fix:** Add a pre-flight step that extracts the tag version and compares against `pyproject.toml`.

---

### C7. `tag.yaml` — No branch filter on tag trigger
**Agent 19** | Confidence: 88

Any `v*` tag from any branch triggers a full release. Tags on feature branches produce untested binaries in GitHub Releases.

**Fix:** Add branch protection rules for tags, or add a CI-status prerequisite to the release job.

---

### C8. `_encode_image` width check doesn't account for `horizontal_offset`
**Agent 14** | Confidence: 88

`_encode_image` checks `image.width` against the 1992px protocol limit before applying offsets. After `ImageOps.expand()` with a positive `horizontal_offset`, the effective width can exceed the limit, producing silently corrupted packet data.

**Fix:** Check `image.width + max(0, horizontal_offset) > (255 - 6) * 8` before encoding.

---

## HIGH Findings

### Source Code

| # | File:Line | Description | Agent |
|---|-----------|-------------|-------|
| H1 | `bluetooth.py:64` | `connect()` always returns True — printer.py failure branch is dead code | 2 |
| H2 | `bluetooth.py:84` | `response=False` hardcoded — bypasses bleak 3.0 auto-detect | 2 |
| H3 | `bluetooth.py:92-97` | `start_notification` TOCTOU — double `start_notify` possible | 2 |
| H4 | `command.py:105` | `rotated if rotated` should be `rotated is not None` | 11 |
| H5 | `command.py:162,210` | `logger.debug(f"{e}")` loses traceback — should use `exc_info=True` | 11 |
| H6 | `command.py:37,174` | Model choice list duplicated — no shared constant | 11 |
| H7 | `helper.py:9` | NO_COLOR empty string incorrectly disables color per spec | 5 |
| H8 | `types.py:37-49` | TextItem/ImageItem missing `initial_x/y/size` NotRequired fields | 4 |
| H9 | `types.py:29` | `FontProps.size: int` but deserialization accepts float | 4 |
| H10 | `UserConfig.py:66-67` | Missing `isinstance(user_devices, dict)` guard before `.items()` | 7 |
| H11 | `UserConfig.py:79-84` | Silent overwrite of built-in label names — no warning | 7 |
| H12 | `PrintOption.py:360-390` | `print_job=True` set before rotation — stuck forever if `rotate()` raises | 8 |
| H13 | `PrintOption.py:67-68` | `update_status` unconditionally overwrites `printer_connected` | 8 |
| H14 | `printer.py:162` | `notification_data` stores mutable bytearray ref from BLE callback | 1 |
| H15 | `printer.py:122` | `RequestCodeEnum()` ValueError misattributed as "malformed response" | 1 |
| H16 | `printer.py:118-150` | `char_uuid` used without None guard in send_command/write_raw | 25 |
| H17 | `CanvasSelector.py:22` | Hardcoded "D110" mismatches `AppConfig.device` for custom configs | 9 |
| H18 | `PrintOption.py:155-156` | `winfo_reqwidth/reqheight` clips export surface — use actual dimensions | 9 |
| H19 | `TextOperation.py:182` | `font_props["size"]` mutated before confirming `tk_image` success | 9 |
| H20 | `FileMenu.py:140` | No deselect before canvas reset on file load — stale `current_selected` | 10 |
| H21 | `main.py:105-109` | `on_close` shows quit dialog even when `app_config` never created | 6 |
| H22 | `PrintOption.py:386` | `Image.NEAREST` deprecated positional arg — use `Image.Resampling.NEAREST` | 6, 25 |

### Security

| # | File:Line | Description | Agent |
|---|-----------|-------------|-------|
| H23 | `cli/command.py:102` | No `MAX_IMAGE_PIXELS` in CLI path — allows large decomp bombs | 22 |
| H24 | `printer.py:314` | Row counter silently truncated at 65535 for tall GUI images | 22 |
| H25 | `PrintOption.py:229` | No `MAX_IMAGE_PIXELS` in popup open path | 22 |

### CI/CD & Build

| # | File:Line | Description | Agent |
|---|-----------|-------------|-------|
| H26 | `dependabot.yml:7` | `pip` ecosystem silently skips Poetry-managed deps | 18, 21 |
| H27 | `ci.yaml:33` | `poetry install` installs pyinstaller (50MB+) needlessly in test/lint | 18 |
| H28 | `NiimPrintX-mac.spec:39` | macOS CLI spec `upx=True` → crashes on Apple Silicon | 21 |
| H29 | `NiimPrintX-mac.spec:89` | `entitlements_file=None` → Bluetooth denied by macOS TCC | 20 |
| H30 | `_build-windows.yaml:53` | Hardcoded ImageMagick URL — will 404 when old version removed | 20 |
| H31 | `_build-linux.yaml` | No MAGICK_HOME set before Linux PyInstaller — wand libs may be missed | 20 |

### Tests

| # | File:Line | Description | Agent |
|---|-----------|-------------|-------|
| H32 | `test_cli.py/test_cli_command.py` | CliRunner doesn't capture stderr — all error message assertions vacuous | 15 |
| H33 | `conftest.py:14-34` | `make_fake_write` is dead code — defined but never imported | 17 |

---

## MEDIUM Findings

| # | File | Description | Agent |
|---|------|-------------|-------|
| M1 | `bluetooth.py:99-103` | `stop_notification` removes UUID before confirming stop succeeded | 2 |
| M2 | `bluetooth.py:23` | `BleakScanner.discover()` has no timeout parameter | 2 |
| M3 | `UserConfig.py:98-106` | Dual rotation representation (-90 built-in vs 270 custom) | 7 |
| M4 | `FileMenu.py:178,214,223` | `PIL.Image.MAX_IMAGE_PIXELS` mutated as process-global, never restored | 10, 22 |
| M5 | `FileMenu.py:123-129` | Item count check ignores existing canvas items — OOM guard defeated by repeated loads | 10 |
| M6 | `SplashScreen.py:17` | `destroy()` in `__init__` — `close()` double-destroy unguarded | 10 |
| M7 | `FontList.py:63` | IM6 fallback condition doesn't match its comment | 10 |
| M8 | `ImageOperation.py:82` | `move_image` KeyError if item deleted mid-drag | 9 |
| M9 | `AppConfig.py:128-131` | `mm_to_pixels` name misleading — uses print_dpi, not screen_dpi | 6 |
| M10 | `AppConfig.py` | `screen_dpi` computed but never read — dead field | 6 |
| M11 | `bluetooth.py:42-45` | BLE rogue device impersonation — documented hardware limitation | 22 |
| M12 | `printer.py:76,84,126` | Log injection via BLE device name — ANSI escape in loguru | 22 |
| M13 | `ci.yaml` | No `mypy` step despite mypy being a dev dependency | 18 |
| M14 | `ci.yaml:15` | `ubuntu-latest` is non-deterministic — pin to `ubuntu-24.04` | 18 |
| M15 | `_build-macos.yaml:54-56` | TKinter version check runs before brew install | 20 |
| M16 | `mac-dmg-builder.sh:27-34` | `kill_xprotect` on first attempt + no timeout on pgrep wait | 20 |
| M17 | `NiimPrintX-linux.spec:26-37` | Hardcoded TCL/TK paths not set in CI — RuntimeError on stock Ubuntu | 21 |
| M18 | `NiimPrintX-windows.spec:18` | `./resources/ImageMagick` CWD-relative with no existence check | 21 |
| M19 | Tests: Logger tests mutate global loguru state with no teardown | 17 |
| M20 | Tests: Three `_auto_respond` helpers across two files — should be shared | 17 |
| M21 | Tests: Trailing-bytes test duplicated across three files | 17 |
| M22 | Tests: No test for `mm_to_pixels` despite being only arithmetic method | 16 |

---

## Architecture Findings (Agent 24)

### Highest-Impact, Lowest-Risk Refactors

1. **Move `helper.py` to `cli/`** — 29-line file, only imported by `command.py`. Eliminates `rich` as a `nimmy` dependency. Two-line change + file move.

2. **Move `UserConfig.py` to `nimmy/`** — Zero UI imports. Update one import in `AppConfig.py`. Rename to snake_case (`userconfig.py`).

3. **Extract shared bounding-box utility** — `update_bbox_and_handle` is duplicated verbatim between `TextOperation` and `ImageOperation`. One shared function eliminates 20+ lines.

4. **Consolidate model list** — `V2_MODELS`, `MODEL_MAX_DENSITY`, `click.Choice` lists, and `max_width_px` branch are scattered across 4 locations. One `MODELS` dict collapses them all.

5. **Rename V2 methods to snake_case** — `print_imageV2` → `print_image_v2` etc. Mechanical rename across 4 files.

### AppConfig God Object

`AppConfig` mixes 5 responsibility categories: static hardware config, device selection, canvas render state, printer state, environment paths. It's used as a shared-mutable-state bus by every widget. Lowest-risk extractions: delete dead `screen_dpi` field, move `print_job`/`printer_connected` to `PrinterOperation`.

---

## Mypy Analysis (Agent 25)

**224 errors total** (strict mode). Breakdown:
- **CLI module:** 0 errors (fully typed, clean)
- **nimmy core:** 9 errors (real type-safety issues)
- **UI layer:** 215 errors (almost entirely missing annotations)

### Actual Bugs Found by mypy:
1. `printer.py:125` — `notification_data` passed as None to `from_bytes()`
2. `printer.py:118-150` — `char_uuid` used without None narrowing
3. `PrintOption.py:386` — `Image.NEAREST` removed from Pillow type stubs

### Recommended mypy config (add to pyproject.toml):
- Strict for `nimmy/` and `cli/` (9 errors to fix, viable for CI today)
- Relaxed for `ui/` (annotate incrementally)

---

## Dependency Audit (Agent 23)

- **Installed bleak 0.22.3 doesn't match lockfile 3.0.1** — run `poetry install --sync`
- **requirements.txt** is semantically in sync but hand-maintained (not `poetry export`)
- **No known CVEs** in any locked dependency version
- **pip-audit** not installed — should be added to dev deps
- **Python `>=3.12,<3.14`** constraint is appropriate

---

## Stale Venv Fix

```bash
cd ~/github/NiimPrintX && poetry install --sync
```

This fixes the CRITICAL bleak version mismatch (0.22.3 installed vs 3.0.1 locked).
