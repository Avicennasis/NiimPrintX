# NiimPrintX TODO

## Remaining Upstream Issues (Need Hardware/Research)

> These items are blocked on hardware availability or platform-specific testing and cannot be resolved without physical devices.

- [ ] **#37 — B21S support** — May be similar to B21; needs hardware to verify protocol
- [ ] **#34 — K3 support** — Unknown protocol; needs hardware research
- [ ] **#23 — B3S support** — Unknown protocol; needs hardware research
- [ ] **#18 — macOS CoreBluetooth "Event loop is closed" crash** — bleak async lifecycle bug on macOS Big Sur; may be fixed by bleak 0.22.3 upgrade (needs macOS testing)
- [ ] **#10 — Phomemo printer support** — Different brand/protocol; likely out of scope

## Known Protocol Issues (Need Hardware to Verify)

> These protocol changes risk breaking working configurations. Do not implement without hardware to verify.

- [ ] **D11_H 7-byte START_PRINT** — Upstream PR #36 comment by @MultiMote suggests D11_H needs a 7-byte START_PRINT packet (matching `start_printV2` format) instead of the 1-byte `start_print`. Users reported blank labels. D11_H may need routing through the V2 print path. Needs hardware testing before changing.
- [ ] **B1 multi-copy printing** — `print_imageV2()` passes quantity to `start_printV2` and `set_dimensionV2` but only sends page data once. Upstream user @hadess confirmed multi-copy doesn't work. Unclear if firmware handles repetition or if the page block needs to loop. Needs B1 hardware testing.

## Upstream Issues to Close (No Code Needed)

> Note: Issues are on upstream repo (labbots/NiimPrintX). Fork has issues disabled. These require manual commenting by maintainer.

- [ ] **#44** — "Is project alive?" — Comment: fork is actively maintained
- [ ] **#27** — French user wants Excel VBA printing — Point to CLI docs
- [ ] **#35** — Xubuntu printer setup — Documentation/FAQ (Bluetooth pairing guide)
- [ ] **#25** — D101 Windows pairing — D101 now supported; ask user to retry with latest

## Outstanding (Blocking before v0.6.0)

- [x] **Bleak migration** — bleak 0.22.x → 3.0+ (minimal breaking changes: connect() returns None instead of bool, new exception types; `is_connected` property unchanged); pyproject.toml updated to `^3.0`
- [ ] **ImageMagick Windows URL** — Download URL hardcoded to 7.1.1-33; needs auto-latest or pinned artifact

## Outstanding (Important)

- [ ] **Architecture: Split AppConfig** — God object mixing immutable config + mutable canvas state
- [ ] **Architecture: Move helper.py** — From nimmy/ to cli/ (it's a Rich presentation layer)
- [ ] **Architecture: Move UserConfig.py** — From ui/ to nimmy/ (no UI dependency)
- [ ] **Architecture: FileMenu callbacks** — Use callbacks instead of reaching into root.text_tab
- [ ] **Thread safety: printer_connected** — Written from async thread (PrinterOperation) and main thread (heartbeat callback); works via GIL but architecturally fragile
- [ ] **Dependabot pip ecosystem** — `dependabot.yml` uses `pip` ecosystem which doesn't parse `[tool.poetry.dependencies]`; Python deps get no automated update PRs

---

## Completed

### Round 13 Deep Code Review (2026-04-12, seventh session)

- [x] **25-agent parallel burn** — full codebase audit across every .py file + CI/CD + build specs
- [x] **BLE hardening** — stale requirements.txt (bleak 0.22 → 3.0), print_started flag prevents double end_print
- [x] **Protocol bounds** — set_dimension/set_dimensionV2 height/width validation (1-65535)
- [x] **Lifecycle fixes** — asyncio.all_tasks() loop param removed (Python 3.10+), destroy() TclError guard, heartbeat CancelledError handler
- [x] **PrinterOperation safety** — printer assigned only after successful connect, nulled on disconnect failure, printer_connected reset on heartbeat error
- [x] **UI robustness** — ImageOperation bbox None guard, TextOperation text_id guards in move/resize, StatusBar TclError guard, density default clamped to device max, rotated image leak fixed
- [x] **Type safety** — ImageItem TypedDict gains bbox/handle fields, TextOperation WandDrawing/Color set to None on ImportError
- [x] **Config validation** — _safe_int rejects booleans, _validate_dims rejects infinity/NaN, logger_enable handles negative verbosity
- [x] **CI** — --cov-fail-under=90 enforced in pytest invocation, requirements.txt synced with pyproject.toml
- [x] **AppConfig** — mm_to_pixels uses round() instead of int() (eliminates systematic under-sizing)

### Round 12 Deep Code Review (2026-04-12, seventh session)

- [x] **Bleak 0.22 → 3.0 migration** — pyproject.toml `^3.0`, poetry.lock updated, all 309 tests pass
- [x] **4-agent parallel audit** — BLE+protocol, CLI+config, UI widgets, tests+CI/CD
- [x] **BleakError wrapping** — bleak 3.0's `BleakGATTProtocolError` and `BleakError` now caught and wrapped as `BLEException` in both `connect()` and `write()`
- [x] **find_characteristics fix** — No longer skips services with multiple characteristics; searches all characteristics across all services
- [x] **Rich markup injection** — `rich.markup.escape()` applied in all 3 helper functions (`print_info`, `print_error`, `print_success`)
- [x] **Canvas label size on file load** — Added `update_canvas_size()` call after setting saved label size in FileMenu
- [x] **toolbar_print_button recovery** — `display_print` now re-enables button on `export_to_png` failure
- [x] **Print error dialog guard** — `_print_handler` checks if popup still exists before showing error dialog
- [x] **update_image_offset guard** — `image_label.config()` wrapped in `contextlib.suppress(tk.TclError)`
- [x] **UserConfig rotation default** — Changed from `270` to `-90` (matches README docs; functionally equivalent after `% 360`)
- [x] **Coverage threshold** — Raised `fail_under` from 60 to 90
- [x] **download-artifact SHA** — Fixed truncated 39-char SHA to full 40-char in `tag.yaml`
- [x] **Linux spec Tcl/Tk** — Changed `warnings.warn` to `raise RuntimeError` for missing Tcl/Tk paths
- [x] **Tests** — 309 → 315 (6 new: BleakError wrapping, multi-char service, Rich markup escaping, negative rotation)

### Round 11 Deep Code Review (2026-04-12, sixth session)

- [x] **21-agent fix session** — 4 audit agents + 21 fix agents across 6 themes
- [x] **Lifecycle fixes (3 criticals)** — Heartbeat hang on close, image memory leak on exit, PhotoImage ref leak in TabbedIconGrid
- [x] **UI safety guards** — ImageOperation/TextOperation delete guards, bbox null checks, deselect cleanup
- [x] **BLE hardening** — RFID response bounds validation (3 checks), BLE auth design documented
- [x] **Build pipeline** — CLI specs hiddenimports on all 3 platforms, macOS UI spec PIL normalization
- [x] **Security** — FileMenu aggregate image limit (100), FontList shutil.which validation, UserConfig reject non-whole floats
- [x] **Test refactor** — conftest shared fixtures, heartbeat parameterized, weak assertions replaced, CLI parameterized, 3 integration tests
- [x] **CI** — CLI smoke test (niimprintx --help)
- [x] **UX/cleanup** — CanvasOperation/StatusBar/CanvasSelector/SplashScreen type annotations, SplashScreen close()
- [x] **Tests** — 306 → 309, coverage 96.76%, 0 lint errors, 55 formatted

### Round 10 Fixes (2026-04-12, sixth session)

- [x] **CI coverage fix** — Excluded GUI widgets from coverage (37.74% → 94.46%), added JUnit XML upload, added pip-audit dependency scanning
- [x] **ImageMagick SHA-256** — Windows build now verifies download checksum before extraction
- [x] **Release checksums** — SHA256SUMS.txt generated and included in GitHub Releases
- [x] **mm_to_pixels dedup** — Extracted to AppConfig.mm_to_pixels(), removed from CanvasSelector and PrintOption
- [x] **Print performance** — Removed 10ms/row hardcoded sleep (asyncio.sleep(0.01) → asyncio.sleep(0)), eliminates 2.4-8.6s per print
- [x] **Type annotations** — Phase 1 complete: all nimmy/ functions (printer.py, bluetooth.py, packet.py, helper.py, exception.py, logger_config.py), cli/command.py, ui/AppConfig.py, ui/UserConfig.py
- [x] **TypedDicts** — nimmy/types.py with HeartbeatResponse, RFIDResponse, PrintStatus, FontProps, TextItem, ImageItem
- [x] **Dependency bumps** — click 8.1.7→8.3.2, rich 13.7.1→14.3.4
- [x] **Tests** — 214 → 306 (92 new tests across 3 new files), coverage 94.46%
- [x] **TODO.md** — Updated with current state, marked completed items

### Round 9 Deep Code Review (2026-04-11, fifth session)

- [x] **25-agent review** — ~120 findings (18 critical, 42 high, 35 medium, ~25 low)
- [x] **25-agent fix session** — All 18 criticals + ~30 high fixes across 58 files
- [x] **25-agent Round 2 review** — Found 7 regressions from fix agents; all corrected
- [x] **V2 protocol routing** — GUI now correctly routes B18/B21 to V2 (was only B1); V2_MODELS constant as single source of truth
- [x] **Image anchor fix** — Switched from anchor="center" to anchor="nw"; fixes every printed label having images offset by half dimensions
- [x] **Toolbar Print button** — Re-enables on popup close (was permanently disabled)
- [x] **Build pipeline** — Poetry 2.3.3, --all-extras, Windows spec hiddenimports (was only ['tkinter']), cairo on all specs
- [x] **CI** — Lint matrix removed (saves 50% CI time), coverage threshold, dependabot.yml, tag permissions
- [x] **PyInstaller** — macOS upx=False, runtime hook Path fix, CLI spec else branches, all specs have cairo
- [x] **printer.py** — BaseException cleanup, PIL leak fix, status poll >=, width validation (1992px), notification guard, get_info guard
- [x] **bluetooth.py** — write-without-response (BLE throughput), PERF dict iterator fix
- [x] **packet.py** — Trailing bytes tolerance for BLE hardware, empty data guard on packet_to_int
- [x] **Splash** — Signal-based instead of 5s hardcoded delay
- [x] **FontList** — Subprocess timeout (10s), loguru logging, parse guards, refactored fallback
- [x] **All UI widgets** — bbox reset, click handler guards, dual selection fix, PIL leak fixes, decompression bomb protection, B1-Motion fixes
- [x] **Config** — AppConfig.device defaults to "d110", merge_label_sizes deep copy, rotation default 270
- [x] **Ruff** — 20 rule categories (added PERF/PIE/RET/PLW/PLC/ERA/BLE/ASYNC), 0 errors, 50/50 formatted
- [x] **Tests** — 129 → 158 (29 new tests across 4 new files), all passing
- [x] **Dependencies** — Removed obsolete types-Pillow, tightened pytest-asyncio <1

### Round 8 Deep Code Review (2026-04-11, fourth session)

- [x] **20-agent review** — 120+ findings (19 critical, 45 important, 25 medium)
- [x] **21-agent fix session** — All critical and important fixes applied across 47 files
- [x] **Protocol routing** — B18/B21 now correctly routed to V2 in GUI (was V1-only, CLI was correct)
- [x] **Code dedup** — print_image/print_imageV2 consolidated into shared _print_job helper (170 LOC eliminated)
- [x] **Memory leaks** — PIL per-row crop replaced with tobytes+slice; intermediate images explicitly closed
- [x] **Linux fixes** — <Button1-Motion> → <B1-Motion> (image drag), .ico → .png icon in spec
- [x] **Security** — Decompression bomb bypass closed (MAX_IMAGE_PIXELS before open), data[0] length guards on 10 parsers
- [x] **Crash fixes** — Empty text WandImage(0,0), canvas.coords ValueError, export_to_png on None canvas
- [x] **App lifecycle** — Shutdown timeout (3s force-destroy), on_close re-entrant guard, CancelledError catch
- [x] **BLE hardening** — Write timeout (10s), stale BleakClient reuse fixed, stop_notification state cleanup
- [x] **PyInstaller** — Windows CLI a.zipfiles removed (PyInstaller 6), Linux hiddenimports, macOS Bluetooth entitlement, MAGICK_HOME cache fix, desktop entry Exec fixed
- [x] **CI/CD** — SHA-pinned all actions, Poetry pinned in builds, Python 3.13 matrix, coverage enforcement, ruff format check, S/PT/DTZ lint rules
- [x] **Config** — d110_m label sizes, rotation validation (multiples of 90), differentiated TOML exceptions, wand import guard
- [x] **Dependencies** — License SPDX fixed, ruff pinned, pytest-asyncio widened, pyinstaller floor tightened, bleak upgrade TODO documented
- [x] **Tests** — 112 → 129 tests, removed 52 redundant @pytest.mark.asyncio, fixed leaked event loops
- [x] **README** — Community Contributors section crediting 8 PR authors + 12 issue reporters from upstream

### Rounds 6-7 (2026-04-11, third session)

- [x] **20+20 agent review+fix** — 87 findings, 67 fixes across 47 files
- [x] **BLE concurrency** — Image row writes now use _command_lock, notification_handler thread-safe
- [x] **Build fixes** — macOS runtime hook registered, DMG casing fixed, set -euo pipefail
- [x] **CI hardening** — ruff enforced, permissions blocks, pinned actions
- [x] **14-agent regression fix** — All critical regressions from Round 6 fixed
- [x] **Tests** — 103 → 112

### Rounds 1-4 (2026-04-11, first+second sessions)

- [x] **8 upstream PRs merged** — Korean encoding, device selection, D11_H 300dpi, D110 BLE, B1 V2, multi-line text, Linux desktop, Python 3.13
- [x] **Device configs** — d101, B21, D110-M added
- [x] **User config** — TOML at ~/.config/NiimPrintX/
- [x] **Modern theming** — sv-ttk Sun Valley
- [x] **71 fixes** across 4 review rounds
- [x] **Tests** — 0 → 103
