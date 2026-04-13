# NiimPrintX Code Review — Round 23

**Date:** 2026-04-13
**Agents:** 25 parallel reviewers (layer-based + cross-cutting)
**Codebase:** v0.8.0 (380 tests, 0 ruff errors, 90% coverage)

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 5 |
| HIGH | 40 |
| MEDIUM | 35 |
| **Total** | **80** |

---

## CRITICAL Findings

### C1. Shutdown never disconnects BLE printer
- **File:** `ui/main.py:182-184`
- **Category:** bug
- **Agents:** 9, 13, 24, 25 (4 independent confirmations)
- **Description:** `_shutdown()` calls `self.print_option.print_op.printer.disconnect()`, but `print_op.printer` is a `PrinterState` object (always truthy, no `disconnect()` method). The `contextlib.suppress(Exception)` silently swallows the `AttributeError`. The actual BLE client (`print_op._client`) is never disconnected on app close.
- **Fix:** `await self.print_option.print_op.printer_disconnect()` or access `_client` directly.

### C2. Linux frozen build has no ImageMagick bundled
- **File:** `spec_files/ui_app/NiimPrintX-linux.spec`
- **Category:** build
- **Agent:** 21
- **Description:** The Linux UI spec bundles zero ImageMagick binaries/libs. `load_libraries()` in `__main__.py` sets `MAGICK_HOME`, `LD_LIBRARY_PATH`, and `MAGICK_CONFIGURE_PATH` to nonexistent `sys._MEIPASS/imagemagick/` paths. Wand/font rendering is completely broken in frozen Linux builds. Windows and macOS specs both bundle ImageMagick correctly.
- **Fix:** Bundle a portable ImageMagick for Linux, or raise `RuntimeError` at spec-eval time if missing.

### C3. Linux UI spec is one-file while Windows/macOS are one-dir
- **File:** `spec_files/ui_app/NiimPrintX-linux.spec`
- **Category:** build
- **Agent:** 21
- **Description:** Linux extracts everything to a per-run temp dir under `/tmp/_MEIxxxxxx` (deleted on exit). This architectural inconsistency with Windows/macOS one-dir builds causes maintenance confusion and platform-specific debugging surprises.
- **Fix:** Convert to one-dir layout (`exclude_binaries=True` + `COLLECT`) matching other platforms.

### C4. CancelledError during print cleanup skips end_print
- **File:** `nimmy/printer.py:282-287`
- **Category:** bug (hardware risk)
- **Agent:** 8
- **Description:** The `except BaseException` cleanup uses `contextlib.suppress(Exception)` for `end_page_print()` and `end_print()`. `CancelledError` is a `BaseException`, not `Exception`. If cancellation arrives at an `await` inside `end_page_print()`, it propagates out, skipping `end_print()` entirely. The printer is left in a mid-print state requiring a power cycle.
- **Fix:** Change to `contextlib.suppress(BaseException)` or use `try/except BaseException: pass` for each cleanup call.

### C5. Windows build uses `${{ }}` interpolation in `run:` blocks
- **File:** `_build-windows.yaml:59,63`
- **Category:** security / ci-cd
- **Agent:** 22
- **Description:** `${{ env.IMAGEMAGICK_VERSION }}` and `${{ env.IMAGEMAGICK_SHA256 }}` are interpolated directly into PowerShell `run:` blocks instead of using `$env:` references. Prior rounds fixed this pattern for `VERSION` but missed ImageMagick vars. While currently safe (values are workflow-internal), this violates the established convention.
- **Fix:** Use `$env:IMAGEMAGICK_VERSION` and `$env:IMAGEMAGICK_SHA256` via step-level `env:` mapping.

---

## HIGH Findings

### Protocol / BLE Layer

**H1. BleakError from start_notification propagates unwrapped** (bluetooth.py:96-105)
- `start_notify` can raise `BleakError` which is not caught and wrapped as `BLEException`. Callers in `printer.py` only catch `BLEException`.
- Fix: Add `except BleakError as e: raise BLEException(...) from e` in `start_notification`.

**H2. connect() never returns False — dead guard branches everywhere** (bluetooth.py:53-74, PrinterOperation.py:30-34, command.py:144-146,209-210)
- `BLETransport.connect()` always returns `True` or raises. All `if not await connect()` guards are dead code.
- Fix: Change connect to `-> None`, remove all dead False-return branches.

**H3. Stale char_uuid after unilateral BLE disconnect** (printer.py:119)
- When BLE drops without `disconnect()` being called, `char_uuid` retains the old value. Reconnect skips `find_characteristics()` and reuses the stale UUID.
- Fix: Reset `self.char_uuid = None` before `self.connect()` in the reconnect path.

**H4. start_notification phantom UUID race** (bluetooth.py:99-105)
- UUID is added to `_notifying_uuids` BEFORE `start_notify` succeeds. If cancelled between add and await, the UUID stays as a phantom, blocking future subscriptions.
- Fix: Move `_notifying_uuids.add()` to AFTER `start_notify` succeeds.

**H5. Write timeout leaves transport desynchronized** (bluetooth.py:85-94)
- `asyncio.wait_for` cancels the Python coroutine but not the OS-level GATT write. Printer may respond to the timed-out command during the next command, causing protocol desync.
- Fix: Document as fatal transport error; disconnect after write timeout.

**H6. Cleanup timeout blocks for 20 extra seconds** (printer.py:278-287)
- When `_print_job` fails, cleanup calls `end_page_print()` and `end_print()` with default 10s timeouts each. If printer is unreachable, caller is blocked 20s extra while `_print_lock` is held.
- Fix: Pass `timeout=2.0` to cleanup calls.

**H7. Alpha channel Image leak in _encode_image** (printer.py:318)
- `image.split()[-1]` creates a PIL Image for the alpha mask but never explicitly closes it. Every other intermediate Image in the function is closed.
- Fix: Capture in variable, close in `finally`.

**H8. end_page_print timeout causes redundant cleanup call** (printer.py:259-265)
- After 200 retries, `page_started` remains True, causing cleanup to call `end_page_print()` again with full 10s timeout.
- Fix: Track `epp_timed_out` flag, skip redundant cleanup.

**H9. Effective-dimension check occurs after printer commands sent** (printer.py:243)
- Validation that could be done before any BLE traffic triggers after `start_print` + `start_page_print`, requiring cleanup round-trips.
- Fix: Move dimension check before `set_label_density`.

### UI Layer

**H10. PrinterOperation.print() writes printer_connected from async thread** (PrinterOperation.py:58)
- Cross-thread write to `PrinterState` attribute without `after()` dispatch. Race with heartbeat's Tk-thread updates.
- Fix: Remove the write; let heartbeat observe connection state.

**H11. Heartbeat double-start no guard** (PrintOption.py:53)
- `check_heartbeat()` can start a second concurrent heartbeat coroutine if called during reconnect. No guard against double-start.
- Fix: Add `if self._heartbeat_active: return` guard.

**H12. update_status asymmetric connect/disconnect guard** (PrintOption.py:86-93)
- `_connecting` guard suppresses heartbeat status during connect but not disconnect, allowing button flicker.
- Fix: Early-return from `update_status` while `_connecting` is True.

**H13. PrinterState/is_connected dual truth divergence** (PrinterOperation.py:53-58)
- `printer_connected` (UI flag) and `_client is not None` (actual state) can diverge, causing `print()` to skip reconnect or use stale client.
- Fix: Use `is_connected` property instead of `printer_connected` flag.

**H14. Debounce fires on stale/deselected text item** (TextTab.py:153-155)
- Lambda captures `current_selected` at schedule time. If user deselects within 150ms, the old item's properties are silently overwritten.
- Fix: Add `if text_id != self.canvas_state.current_selected: return` in `update_canvas_text`.

**H15. update_bbox_and_handle crashes when bbox is None** (TextOperation.py:204-215)
- `canvas.coords(None, ...)` raises TypeError. Missing guard that `ImageOperation` already has.
- Fix: Add `if text_items[text_id].get("bbox") is None: return`.

**H16. resize_image no None bbox guard** (ImageOperation.py:116-117)
- `canvas.bbox()` return not checked before subscripting. Inconsistent with other methods.
- Fix: Add `if current_bbox is None: return`.

**H17. TabbedIconGrid tab_names KeyError** (TabbedIconGrid.py:68)
- Bare dict lookup without `.get()` guard, unlike the pattern at line 57.
- Fix: Use `.get()` with early return.

**H18. TabbedIconGrid sets MAX_IMAGE_PIXELS in background thread** (TabbedIconGrid.py:128)
- Process-global PIL mutation from non-main thread, racing with concurrent `Image.open()`.
- Fix: Move to module level.

**H19. Dead font_image .close() code** (CanvasSelector.py:103-106)
- `tk.PhotoImage` and `ImageTk.PhotoImage` have no `.close()` method. The `hasattr` guard always returns False.
- Fix: Remove the dead conditional.

**H20. original_image not closed on error path** (FileMenu.py:259-266)
- PIL Image leaked when resized-image decode fails after original is opened.
- Fix: Wrap in `try/except` with `original_image.close()` on error.

**H21. Item count guard bypassable with non-dict values** (FileMenu.py:161-163)
- `_MAX_ITEMS_PER_FILE` check uses `len()` on unvalidated types. Non-dict `text`/`image` values bypass the limit.
- Fix: Move type validation before count check.

**H22. Case normalization not passed to callback** (FileMenu.py:183)
- Device name lowercased for validation but original-cased string passed to `_on_load_canvas_config`.
- Fix: Pass normalized `device` and `label_size` variables.

### Security (.niim file deserialization)

**H23. Font family unvalidated from .niim file** (FileMenu.py:205-236)
- `fp["family"]` receives no type check, length bound, or whitelist validation. Passed directly to Wand.
- Fix: Validate type, length <= 256, existence in font list.

**H24. Unbounded content string from .niim file** (FileMenu.py:213-215)
- No length limit on `data["content"]`. Multi-megabyte string causes heap exhaustion in Wand.
- Fix: Cap at 10,000 characters.

**H25. Kerning accepts infinity/NaN from .niim file** (FileMenu.py:210-211)
- `fp["kerning"]` checked for type but not `math.isfinite()` or range. Extreme values crash Wand.
- Fix: Add `isfinite()` check and range clamp [-100, 100].

**H26. resize_image no upper bound on dimensions** (ImageOperation.py:128-135)
- No cap on `new_width` during drag resize. Arbitrarily large PIL allocation possible.
- Fix: Cap at `MAX_CANVAS_DIM = 32767`.

### CLI Layer

**H27. _ALL_MODELS duplicated with no sync mechanism** (command.py:22)
- Model list in `command.py` must manually stay in sync with `printer.py` constants.
- Fix: Derive from printer.py's authoritative sources.

**H28. Image.MAX_IMAGE_PIXELS set inside function body** (command.py:106)
- Process-global mutation on every `print_command` call. Breaks test isolation.
- Fix: Move to module level.

**H29. NO_COLOR empty string spec violation** (helper.py:9)
- `bool(os.getenv("NO_COLOR"))` returns False for `NO_COLOR=""`, violating no-color.org spec.
- Fix: `"NO_COLOR" in os.environ`.

**H30. CLI __main__.py unconditional module-level import** (cli/__main__.py:1)
- Import of `niimbot_cli` outside `if __name__ == "__main__"` guard triggers heavy transitive imports.
- Fix: Move import inside the guard.

### Config Layer

**H31. Rotation default -90 misleading** (userconfig.py:109)
- Default `-90` relies on Python modulo to produce `270`. Should be `270` directly.

**H32. ImmutableConfig.label_sizes setter breaks immutability contract** (AppConfig.py:58-60)
- Dead code setter that violates the class's documented immutability guarantee.
- Fix: Remove the setter.

**H33. AppConfig unused in production** (AppConfig.py:15-156)
- 140-line facade class never instantiated in production code. "Phase 2 migration" never completed.
- Fix: Remove or track with an issue.

**H34. PrinterOperation.immutable stored but never read** (PrinterOperation.py:16-17)
- Dead attribute stored in `__init__`.
- Fix: Remove parameter and attribute.

### Build / CI

**H35. macOS CLI strip=True corrupts code-signed binaries** (cli_app/NiimPrintX-mac.spec:33)
- macOS UI spec correctly uses `strip=False`. CLI spec inconsistent.

**H36. entitlements.plist missing Hardened Runtime keys** (entitlements.plist)
- Missing `allow-unsigned-executable-memory` (required for PyInstaller) and `disable-library-validation` (required for unsigned bundled dylibs).

**H37. Manual Tcl/Tk path derivation fragile** (ui_app/NiimPrintX-linux.spec:25)
- PyInstaller's built-in tkinter hook handles this correctly. Manual approach fragile on non-Debian.

**H38. macOS ImageMagick unpinned via Homebrew** (_build-macos.yaml:61)
- No version pinning or checksum. Inconsistent with Windows which pins and verifies.

**H39. DMG builder pgrep triggers set -e** (mac-dmg-builder.sh:38)
- `pgrep XProtect` in `while` condition exits 1 when no processes found, triggering `set -e` abort.

**H40. Release pipeline no artifact count validation** (tag.yaml:78-81)
- Silent partial release possible if a platform build produces 0 artifacts.

---

## MEDIUM Findings (35 total — abbreviated)

### Code Quality
- M1. `verbose=2` (-vv) maps to same level as `-v` (logger_config.py:49)
- M2. `packet_to_int` should be a method on `NiimbotPacket` (packet.py:8)
- M3. Non-dict device config entries silently skipped without warning (userconfig.py:73-75)
- M4. Config names have no length limit (userconfig.py:73, security)
- M5. `bbox` field name misleading (ui/types.py:24-25 — stores canvas item ID, not coordinates)
- M6. Redundant hasattr guards on always-present attributes (CanvasSelector.py:100, TextTab.py:151)
- M7. Floating instance attributes should be initialized in `__init__` (PrintOption.py:267,393,404)
- M8. Dead `success = False` initialization (command.py:190)
- M9. Redundant inline comments in PrintOption (lines 151-152, 157-158, 169)
- M10. Redundant mid-iteration heartbeat active checks (PrintOption.py:66-67, 74-75)
- M11. Dead `__main__` guard in command.py (lines 228-229)
- M12. Lazy contextlib/tkinter imports in __main__.py (lines 57-58, 75-76)
- M13. Spurious WARNING log for normal PATH magick usage (FontList.py:53-55)
- M14. `type: ignore[unreachable]` could use assert instead (printer.py:142)
- M15. Absolute imports in packet.py/userconfig.py inconsistent with package (packet.py:3, userconfig.py:11)
- M16. process_png.py double-resize (PIL after mogrify, redundant)

### Security
- M17. font_props missing required keys not validated (FileMenu.py:234-240)
- M18. coords from .niim not checked for infinity/NaN (FileMenu.py:196-202, 248-253)
- M19. Write timeout desync risk undocumented (bluetooth.py:85)
- M20. Stale client notifications after reconnect (bluetooth.py:58-64)
- M21. stop_notification non-BleakError exceptions unwrapped (bluetooth.py:107-114)

### Build / CI
- M22. Dead macOS-13 conditional steps (_build-macos.yaml)
- M23. $GITHUB_OUTPUT unquoted in bash (_build-linux.yaml:23, _build-macos.yaml:26)
- M24. No job timeouts in CI (ci.yaml)
- M25. Python 3.14 not in CI matrix despite declared support (ci.yaml:23)
- M26. mypy scoped too narrowly — should cover full package (ci.yaml:78)
- M27. pip-audit without hashes (ci.yaml:102)
- M28. No automated Python dependency update PRs (dependabot.yml)
- M29. Poetry install not cached per job (ci.yaml:27-28)
- M30. Job-level permissions not explicit (ci.yaml)
- M31. Windows artifact arch "X64" inconsistent with Unix "x86_64"
- M32. DMG background asset path not validated (mac-dmg-builder.sh:14)
- M33. pgrep output not suppressed (mac-dmg-builder.sh:38)

### Tests
- M34. ~15 duplicate tests should be consolidated (test_printer.py vs test_printer_uncovered.py, test_review_fixes.py, test_ui_guards.py, test_coverage_gaps.py)
- M35. Several weak/smoke-only assertions (test_coverage_gaps.py:192, test_cli.py:93, test_appconfig.py:103)

### UI
- M36. Wayland splash geometry returns 1x1 (SplashScreen.py:22-27)
- M37. SplashScreen destroy() inside __init__ (SplashScreen.py:17-19)
- M38. NamedTemporaryFile lifecycle fragile on non-Windows (PrintOption.py:155-158)
- M39. move_text no None bbox guard (TextOperation.py:170-172)
- M40. export_to_png coords can be empty list (PrintOption.py:213, 226)
- M41. FontList convert fallback uses ambiguous is_bundled flag (FontList.py:139)
- M42. TabbedIconGrid background thread no cancellation (TabbedIconGrid.py:110-112)
- M43. Discarded setup command return values (printer.py:255-256)
- M44. send_command error message misleading for encoding errors (printer.py:151)
- M45. DEFAULT_MAX_WIDTH_V1=240 too permissive for d11 (command.py:17-18)

---

## Recommended Fix Order

1. **C1** — Shutdown disconnect (1 line change, immediate hardware impact)
2. **C4** — CancelledError cleanup (1 line change, hardware risk)
3. **C5** — Windows build interpolation (2 line change, security)
4. **H23-H26** — .niim deserialization security (input validation)
5. **H14-H16** — UI crash guards (None checks)
6. **H1, H4** — BLE exception wrapping and phantom UUID
7. **H6, H8** — Cleanup timeout reduction
8. **C2-C3** — Linux build fixes (larger effort)
9. **H27-H30** — CLI cleanup
10. **H35-H40** — Build/CI hardening
11. **M34** — Test deduplication
12. Everything else
