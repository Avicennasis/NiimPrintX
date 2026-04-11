# NiimPrintX Code Review — Round 8 (2026-04-11)

> 20-agent parallel deep dive across entire codebase: source, tests, CI/CD, build specs, dependencies, security

## Summary

- **Total findings:** 120+
- **Critical:** 19
- **Important:** 45
- **Medium:** 25
- **Minor:** 15
- **Agents:** 20 parallel reviewers covering all 46 Python files, 6 CI/CD workflows, spec files, and dependencies

---

## CRITICAL FINDINGS

### C1. B18/B21 routed to V1 protocol instead of V2 in GUI
**File:** `NiimPrintX/ui/widget/PrinterOperation.py:44`
**Confidence:** 97

The UI only checks `if self.config.device == "b1"` for V2 protocol routing. `b18` and `b21` are silently sent through the D-series V1 protocol (`print_image` instead of `print_imageV2`). The CLI correctly routes all three (`b1`, `b18`, `b21`) to V2. This is a live functional bug for B18/B21 hardware users.

**Fix:** `if self.config.device in ("b1", "b18", "b21"):`

---

### C2. No shutdown timeout — BLE hang makes close button permanently unresponsive
**File:** `NiimPrintX/ui/main.py:116`

`_poll_shutdown` polls indefinitely with no timeout. If `printer.disconnect()` hangs waiting on a BLE response, the app becomes unresponsive with no escape.

**Fix:** Add timeout counter (e.g., 30 polls x 100ms = 3 seconds), then force-destroy.

---

### C3. on_close not re-entrant — double-close orphans shutdown event
**File:** `NiimPrintX/ui/main.py:94-96`

`WM_DELETE_WINDOW` remains active during shutdown. Second close recreates `_shutdown_complete` Event, orphaning the one the running coroutine will `.set()` on.

**Fix:** Guard with `self._shutting_down` flag.

---

### C4. Per-row crop() Image never closed — memory leak proportional to image height
**File:** `NiimPrintX/nimmy/printer.py:285`

`img.crop(...)` in `_encode_image` loop creates a new PIL Image per row, never closed. 1000-row label = 1000 orphaned Image objects.

**Fix:** Use single `img.tobytes()` + stride slicing instead of per-row crop.

---

### C5. Intermediate Image objects from convert chain never closed
**File:** `NiimPrintX/nimmy/printer.py:266`

`ImageOps.invert(image.convert("L")).convert("1")` creates two temp Image objects that are immediately dereferenced but never closed.

**Fix:** Explicitly close intermediate images.

---

### C6. print_image/print_imageV2 are ~170 lines of near-identical duplication
**File:** `NiimPrintX/nimmy/printer.py:154-262`

Only differences: V2 calls `start_printV2`/`set_dimensionV2` vs V1 calls `start_print`/`set_dimension`/`set_quantity`.

**Fix:** Extract shared `_print_common()` helper.

---

### C7. Empty text crashes create_text_image via WandImage(width=0, height=0)
**File:** `NiimPrintX/ui/widget/TextOperation.py:29-34`

User clears text, changes font property or drags resize handle → unhandled WandError.

**Fix:** Guard `if not text or not text.strip(): return None`.

---

### C8. Hardcoded ImageMagick URL in Windows build will 404
**File:** `.github/workflows/_build-windows.yaml:46`

ImageMagick 7.1.1-33 portable URL. Archive directory only keeps current version.

**Fix:** Use GitHub Releases URL (preserved indefinitely) or dynamic folder detection.

---

### C9. a.zipfiles removed in PyInstaller 6 — Windows CLI build hard-fails
**File:** `spec_files/cli_app/NiimPrintX-windows.spec:56`

`a.zipfiles` attribute was removed in PyInstaller 6. `AttributeError` at spec execution time.

**Fix:** Remove `a.zipfiles,` from COLLECT call.

---

### C10. Windows CLI is one-dir but Linux/macOS CLI are one-file
**File:** `spec_files/cli_app/NiimPrintX-windows.spec:33-62`

Windows CLI has COLLECT+BUNDLE (one-dir). Linux/macOS are one-file. Plus spurious BUNDLE block (macOS-only construct).

**Fix:** Match one-file pattern from Linux/macOS specs. Remove BUNDLE.

---

### C11. macOS runtime hook sets MAGICK_HOME to wrong path on cache hit
**File:** `runtime_hooks/macOS/runtime_hook.py:16 vs :22`

Cache-miss branch: `MAGICK_HOME = dest_dir / 'imagemagick'` (correct). Cache-hit branch: `MAGICK_HOME = dest_dir` (wrong — missing `/imagemagick`).

**Fix:** Both branches must set `dest_dir / 'imagemagick'`.

---

### C12. Linux UI spec omits bleak, wand, platformdirs from hiddenimports
**File:** `spec_files/ui_app/NiimPrintX-linux.spec`

Only collects PIL and tkinter. Missing bleak (dynamically imports backends), wand (unconditionally imported in TextOperation), and others. Bundled app crashes at first BLE operation or text tab load.

**Fix:** Add `collect_submodules('bleak')`, `collect_submodules('wand')`, `['platformdirs', 'sv_ttk']`.

---

### C13. No guard prevents opening second print popup during active print job
**File:** `NiimPrintX/ui/widget/PrintOption.py:271`

`display_print` has no `config.print_job` check. Second popup steals `self.print_button` reference, causes UI incoherence.

**Fix:** `if self.config.print_job: return` at top of `display_print`.

---

### C14. CancelledError not caught — print_job flag never reset on app close
**File:** `NiimPrintX/ui/widget/PrintOption.py:330-334`

`except Exception` doesn't catch `asyncio.CancelledError` (BaseException in Python 3.8+). If app closes mid-print, `config.print_job` stays True.

**Fix:** `except BaseException`.

---

### C15. Decompression bomb bypass in .niim file loading
**File:** `NiimPrintX/ui/widget/FileMenu.py:133-135`

Pixel-count guard fires after `Image.open()` + `.load()` (lazy decoding). A crafted .niim can embed a bomb that decompresses before the check.

**Fix:** Set `PIL.Image.MAX_IMAGE_PIXELS = _MAX_LABEL_PIXELS` before `open()`.

---

### C16. frame.after() called from background thread — not thread-safe in Tkinter
**File:** `NiimPrintX/ui/widget/TabbedIconGrid.py:117-118`

Background thread calls `frame.after()`, which modifies Tcl event queue. Can cause silent memory corruption.

**Fix:** Use `self.after()` (long-lived widget) or queue.Queue + main-thread poller.

---

### C17. canvas.coords() on stale item returns [] — 4-tuple unpack raises ValueError
**File:** `NiimPrintX/ui/widget/CanvasOperation.py:13-14`

During rapid clicks or canvas rebuild, stale item ID → `coords()` returns `[]` → unpack crash.

**Fix:** `coords = canvas.coords(bbox); if len(coords) != 4: return`.

---

### C18. `<Button1-Motion>` not valid on Linux/X11 — image drag never fires
**File:** `NiimPrintX/ui/widget/ImageOperation.py:40,68`

Should be `<B1-Motion>`. Silently fails on Linux — images cannot be dragged.

**Fix:** Change to `<B1-Motion>`.

---

### C19. bleak pinned at 0.22.3 — 3 major versions behind, blocks Python 3.14
**File:** `pyproject.toml:18`

`^0.22.3` caps at `<1.0.0`. Bleak now at 3.x. Users on Python 3.14 cannot install.

**Fix:** Audit bluetooth.py for bleak 1.x API changes, then bump to `^1.0` or wider.

---

## IMPORTANT FINDINGS

### BLE Transport (bluetooth.py)

| Line | Issue |
|------|-------|
| 44-53 | Stale BleakClient reused on reconnect; bleak 0.22 instances are single-use |
| 76-81 | stop_notification raises instead of returning when disconnected; _notifying_uuids left dirty |
| 63-67 | write_gatt_char has no timeout; hung write blocks _command_lock permanently |

### Core Printer (printer.py)

| Line | Issue |
|------|-------|
| 104-105 | Reconnect return value not checked; False continues with None char_uuid |
| 264-291 | Generator `img` never closed on partial iteration |
| 154-207 | Offset dimension logic duplicated in three places |
| 281 | Silent return on zero-size post-offset image; printer may hang |
| 289 | `">H3BB"` format string is opaque; should be `">HBBBB"` |
| 259 | Hardcoded "B1" in error message applies to all B-series |
| 379+ | 10 response parsers access `packet.data[0]` without length check |

### CLI (command.py)

| Line | Issue |
|------|-------|
| 97 | Density cap message drops the capped-to value |
| 159 | info_command has no exception handling (print_command does) |
| 12 | setup_logger() at module import — side effects during test collection |
| 181 | print_error(e) passes raw exception instead of str(e) |

### UI Core

| Line | File | Issue |
|------|------|-------|
| 46-47 | __main__.py | Hardcoded 5s splash delay regardless of load time |
| 62 | main.py | DPI read on unmapped widget — stale on multi-monitor |
| 71-82 | AppConfig.py | d110_m label sizes match d11 not d110 (14mm vs 15mm) |
| 80 | UserConfig.py | rotation accepts any integer, not validated to multiples of 90 |
| 18 | UserConfig.py | Bare `except Exception` swallows TOMLDecodeError indistinguishably from OSError |
| 56-60 | UserConfig.py | No warning when user supplies density/rotation for built-in device (silently ignored) |

### UI Widgets

| Line | File | Issue |
|------|------|-------|
| 119-127 | PrintOption.py | export_to_png crashes with AttributeError before canvas/label is initialized |
| 225-232 | PrintOption.py | Non-multiple-of-90 rotation produces combobox mismatch |
| 342 | PrintOption.py | mb.showerror not wrapped in TclError suppression |
| 26-27 | PrintOption.py | _heartbeat_active not initialized in __init__ — startup race |
| 109 | FileMenu.py | .niim device/label_size fields not type-validated (int triggers AttributeError) |
| 118-121 | FileMenu.py | Double canvas creation on file load |
| 29-31 | PrinterOperation.py | printer_disconnect doesn't guard self.printer being None |
| 71-84 | PrinterOperation.py | printer_connected written from async thread without lock (data race) |
| 339 | PrintOption.py | update_status(True) after print doesn't reflect actual BLE state |
| 31-32 | TextOperation.py | Descender double-counted in text image height |
| 67-74 | TextOperation.py | delete_text passes None to canvas.delete() |
| 148-155 | TextOperation.py | resize_text KeyError if drag fires before Button-1 |
| 93-112 | ImageOperation.py | Dead dy/initial_height; aspect ratio breaks at minimum clamp |
| 29 | ImageOperation.py | All images load at (0,0) — stack invisibly |
| 115 | ImageOperation.py | LANCZOS resample on every mouse-move with no debounce |
| 40-41 | CanvasSelector.py | Device change resets printer_connected during active print |
| 78 | CanvasSelector.py | Text item Wand handles not closed on canvas rebuild |
| 67-68 | CanvasSelector.py | Hardcoded 2mm/4mm print margins for all devices |
| 15,98 | TabbedIconGrid.py | icon_size parameter stored but never used (50x50 hardcoded) |
| 50 | IconTab.py | Path built with hardcoded `/` instead of os.path.join |

### FontList / SplashScreen

| Line | File | Issue |
|------|------|-------|
| 37 | FontList.py | `convert` fallback invokes Windows convert.exe on Windows |
| 25-47 | FontList.py | Empty IM7 output not detected; frozen app silently returns {} |
| 25 | FontList.py | Blocking subprocess on main thread freezes UI at startup |
| 6 | SplashScreen.py | Missing withdraw() before geometry computation — flash on X11 |

### Security

| Line | File | Issue |
|------|------|-------|
| 8-16 | ImageOperation.py | No _MAX_LABEL_PIXELS guard on interactive image load |
| 100 | command.py | CLI has no height cap — 240x100000 image generates 100K BLE writes |

### CI/CD

| Line | File | Issue |
|------|------|-------|
| 32 | ci.yaml | pytest-cov installed but --cov never passed |
| 17,38 | ci.yaml | Actions pinned to mutable tags, not SHAs |
| 19-29 | ci.yaml | Poetry cache key incorrect — misses on every run |
| 15 | ci.yaml | Single Python version (3.12) — 3.13 not tested despite `<3.14` bound |
| 5 | ruff.toml | Security (S) rule set absent |

### Build Workflows

| Line | File | Issue |
|------|------|-------|
| 33/36/29 | _build-*.yaml | Poetry unpinned in builds, pinned in CI |
| 37+ | All | checkout/setup-python/upload-artifact/download-artifact unpinned to SHA |
| 56,62 | _build-linux.yaml | Empty VERSION string produces double-hyphen artifact names |
| 14-18 | mac-dmg-builder.sh | Silent no-op if .app is missing |
| 35-41 | mac-dmg-builder.sh | unmount_all_disks detaches ALL disk images system-wide |

### Dependencies / Config

| Line | File | Issue |
|------|------|-------|
| 9 | PrintOption.py | `import cairo` unconditional; crashes without gui extras |
| 5-7 | TextOperation.py | `from wand.*` unconditional; crashes without gui extras |
| 33 | pyproject.toml | `ruff >= 0.4` effectively unbounded |
| 31 | pyproject.toml | `pytest-asyncio ^0.23` blocks 0.24+ loop scope fixes |
| 1-6 | requirements.txt | Semantically inconsistent with pyproject.toml; missing requirements-gui.txt |

### PyInstaller Specs

| Line | File | Issue |
|------|------|-------|
| 100-105 | NiimPrintX-mac.spec | BUNDLE missing NSBluetoothAlwaysUsageDescription entitlement |
| 84-89 | NiimPrintX-windows.spec | Spurious BUNDLE block (macOS-only construct) |
| 5 | niimprintx (desktop entry) | Exec invokes CLI binary not GUI |
| 70 | NiimPrintX-linux.spec | Uses .ico icon (Windows format) on Linux |
| 6-9 | NiimPrintX-linux.spec | src_path undefined if CWD is neither ui_app nor NiimPrintX |
| 26-29 | NiimPrintX-windows.spec | hook_path computed but never used (runtime_hooks=[]) |

### Test Quality

| Area | Issue |
|------|-------|
| printer.py:56-68 | PrinterClient.connect()/disconnect() — zero test coverage |
| printer.py:145-152 | notification_handler — zero test coverage |
| All async tests | ~40 redundant @pytest.mark.asyncio decorators (auto mode is set) |
| conftest.py:49 | 8 leaked event loops from asyncio.new_event_loop() in sync tests |
| printer.py:431-432 | get_print_status short-response guard untested |
| printer.py:230-231 | print_imageV2 zero-dimension path untested |
| bluetooth.py:48-52 | BLETransport.connect() exception path untested |

---

## MEDIUM FINDINGS (Selected)

- Verbose -v flag maps to INFO (same as default) — no observable effect
- Row index >H overflows at 65535 rows (no guard)
- Window geometry computed before DPI scaling on HiDPI Linux
- Click.Choice positional False should be case_sensitive=False keyword
- No test timeout — async tests can hang indefinitely
- No dependency vulnerability audit (pip-audit)
- No ruff format check
- ARM Linux build missing
- ImageMagick download has no checksum verification
- Matrix fail-fast blocks release on transient single-runner failure
- License "GNU GPLv3" not valid SPDX identifier
- E501 ignored but line-length set — contradictory config
- Missing PT, DTZ rule sets in ruff
- Dead __main__ block in main.py bypasses ImageMagick setup
- Animated GIFs silently truncated to first frame
- RGBA transparency composited against black

---

## README UPDATE

Added Community Contributors section crediting 8 PR authors and 12 issue reporters from the upstream labbots/NiimPrintX repository.

---

## Previous Rounds

| Round | Date | Findings | Fixes |
|-------|------|----------|-------|
| 1 | 2026-04-11 | 9 | 9 |
| 2 | 2026-04-11 | 29 | 29 |
| 3 | 2026-04-11 | 30 | 30 |
| 4 | 2026-04-11 | 95 | 67 |
| 5 | 2026-04-11 | (merged into 6) | — |
| 6 | 2026-04-11 | 87 | 67 |
| 7 | 2026-04-11 | 29 | 29 |
| **8** | **2026-04-11** | **120+** | **TBD** |
