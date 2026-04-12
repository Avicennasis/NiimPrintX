# Code Review Round 23 — Full Codebase Audit (2026-04-12)

**Method:** 20-agent parallel deep dive across all 57 Python files, CI/CD workflows, build specs, and tests.
**Codebase state:** 358 tests passing, 0 lint errors, v0.8.0 post-refactor (AppConfig split, BLE lifecycle, V2 rename, UI type annotations).

---

## Critical / High Findings

### BUGS

1. **HIGH — PrintOption.py:64 — Heartbeat guard always truthy (refactor regression)**
   `self.print_op.printer` now resolves to `PrinterState` (always truthy) instead of the old BLE client reference. The heartbeat loop fires even when no BLE client exists, causing unnecessary `heartbeat()` calls that return `(False, {})`. The `else` branch (show "Not Connected") can never fire while `print_job` is inactive. **Fix:** Change to `self.print_op._client` or add a `PrinterOperation.is_connected` property.

2. **HIGH — printer.py:145 — `code_label` unbound in timeout handler**
   If `send_command()` fails before line 126 (e.g., reconnect failure), `code_label` is never assigned. The `except TimeoutError` handler on line 145 references it, causing `UnboundLocalError` that masks the real error.

3. **HIGH — PrintOption.py:468 — `_print_handler` missing TclError guard on `root.after`**
   If the Tk root is destroyed during a print job, `self.root.after(0, _update)` raises `TclError`. The `print_job` flag is never reset to `False`, permanently blocking future prints.

4. **HIGH — bluetooth.py:64-67 — No configurable connection timeout**
   `BleakClient.connect()` uses bleak's 30-second default with no way to override. Inconsistent with `write()` which has explicit timeout handling.

5. **HIGH — bluetooth.py:99 — CancelledError leaks phantom notification UUIDs**
   `start_notification` catches `Exception` but not `BaseException`. `asyncio.CancelledError` (a BaseException in Python 3.9+) leaves the UUID in `_notifying_uuids` as a phantom entry, permanently breaking notification subscriptions until disconnect.

6. **HIGH — Windows spec: ImageMagick DLLs classified as `datas` instead of `binaries`**
   `spec_files/ui_app/NiimPrintX-windows.spec` puts all ImageMagick files into `datas`, unlike macOS which correctly splits dylibs into `binaries`. Windows DLLs won't get PE import scanning.

7. **HIGH — All specs: Path resolution uses `os.getcwd()` instead of `SPECPATH`**
   All 6 spec files use CWD to compute `src_path`. PyInstaller from non-repo-root directories will fail silently or bundle wrong files.

### SECURITY

8. **MEDIUM — FileMenu.py:221 — `Image.open` accepts all formats on untrusted data**
   Load accepts any PIL-supported format (TIFF, BMP, etc.) when only PNG is ever saved. Restricting to PNG-only would reduce attack surface from historical PIL parser CVEs.

### PERFORMANCE

9. **MEDIUM — PrintOption.py:205 — Full canvas-sized Cairo surface allocated regardless of bbox**
   A 1920x1080 canvas allocates ~8MB just to crop a 200x100 label region.

10. **MEDIUM — PrintOption.py:214-219 — Cairo image surfaces never `.finish()`-ed in render loops**
    Each iteration creates `img_surface` via `create_from_png` but never calls `finish()`, accumulating native memory.

11. **MEDIUM — TextOperation.py:181-198 — Resize drag bypasses debounce, heavy Wand rendering**
    Each `B1-Motion` event triggers a full Wand render pipeline. The 150ms debounce only protects the text property change path, not resize drag.

### ARCHITECTURE

12. **MEDIUM — PrinterOperation.py:48,54 — `printer_connected` never updated after auto-reconnect**
    After `print()` auto-reconnects, `printer_connected` remains `False`. Every subsequent `print()` re-scans BLE and reconnects wastefully.

13. **MEDIUM — printer.py:277 — `except BaseException` catches KeyboardInterrupt/SystemExit**
    Cleanup code attempts BLE writes which could hang for 10+ seconds, delaying Ctrl+C.

14. **MEDIUM — config.py — ImmutableConfig is mutable in name only**
    No `__slots__`, `__setattr__` guard, or frozen dataclass. AppConfig.label_sizes has a public setter that mutates "immutable" data.

### TEST GAPS

15. **HIGH — No tests for `ImmutableConfig`, `CanvasState`, `PrinterState` directly**
    New config classes only tested indirectly through AppConfig delegation layer.

16. **HIGH — `set_dimension()` / `set_quantity()` boundary validation untested**
    Four `raise PrinterException` paths in printer.py have zero test coverage.

17. **HIGH — `end_page_print` retry loop (200 iterations) never tested**
    Both integration test suites mock immediate success. Timeout path completely uncovered.

18. **HIGH — 300-DPI model width limits (d11_h/d110_m at 354px) never tested**
    `MODEL_MAX_WIDTH` entries for these models have zero test coverage.

---

## Medium Findings (Summary)

| # | Area | Finding |
|---|------|---------|
| 19 | printer.py | Two independent effective_height calculations could diverge |
| 20 | printer.py | `_expecting_response` flag not thread-safe under free-threaded Python |
| 21 | printer.py | PIL mode "1" `tobytes()` packing behavior undocumented/fragile |
| 22 | bluetooth.py | TOCTOU races on `_notifying_uuids` and `is_connected` checks |
| 23 | bluetooth.py | `stop_notification` does not wrap BleakError in BLEException |
| 24 | command.py | `disconnect()` in finally block unguarded — can mask real error |
| 25 | command.py | Vertical/horizontal offsets unbounded — no IntRange |
| 26 | PrintOption.py | Cairo surfaces leak if cropping setup raises (outside try/finally) |
| 27 | PrintOption.py | `export_to_png` returns None silently when canvas empty |
| 28 | CanvasSelector.py | Print area margin asymmetric (2mm width vs 4mm height) |
| 29 | TextTab.py | Thread-unsafe font dict assignment from background thread |
| 30 | TextOperation.py | delete-during-debounce race → KeyError on deleted text_id |
| 31 | CI/CD | macOS/Linux ImageMagick installed without version pin/checksum |
| 32 | specs | entitlements_file path relative to CWD, not SPECPATH |
| 33 | specs | UPX enabled inconsistently (macOS off, Linux/Windows on) |
| 34 | pyproject.toml | Missing `[tool.ruff]` section — CI may use defaults only |
| 35 | README | Test count (331) and rotation default (-90) outdated |

---

## Low / Info Findings (69 total, grouped by theme)

### Thread Safety (5)
- PrinterState.printer_connected/print_job accessed cross-thread without sync
- _heartbeat_active flag accessed from both threads
- TabbedIconGrid PIL images created in bg thread, handed to main thread
- Font list assignment from bg thread without lock
- Logger handlers not thread-safe during `logger_enable`

### Resource Management (8)
- PIL original images held open indefinitely per load_image
- tk.PhotoImage instances accumulate on font changes
- Wand Color objects not context-managed
- Cairo img_surface never finished in export loops
- PIL images leaked if TabbedIconGrid after() callback never fires
- Intermediate resize image not closed on exception path
- Log retention 500MB total on constrained systems
- Tempfile timing fragile (deleted while popup references data)

### Error Handling (7)
- Several `contextlib.suppress(Exception)` should be narrower
- Log directory permissions default (not restrictive)
- Rotation warning reports normalized value, not user's input
- No post-merge validation of user config structure
- Exception message may be empty for bare Exception()
- save_image error dialog already exists (prior review confirmed)
- Error message leaks internal paths

### Cross-Platform (4)
- LD_LIBRARY_PATH set after process start (no effect on dynamic linker)
- SplashScreen winfo_reqwidth may return 1 on Wayland
- Mouse wheel events incomplete for Wayland
- Multi-monitor centering uses primary screen only

### Test Quality (12)
- `fake_write` pattern duplicated 22+ times across test_printer.py
- conftest `make_client` uses __new__ bypass, drifts from __init__
- Several near-duplicate disconnect tests
- test_ui_guards.py misnamed — tests data logic, not UI guards
- Dead `_make_config` helper in test_round22_gaps.py
- BLETransport tests missing naming prefix consistency
- Several missing edge case tests (write with disconnected client, etc.)
- asyncio_mode=auto tests become no-ops if changed to strict
- Font test macOS hasattr patch is dead code
- No test for scan_timeout passthrough
- No test for PrinterOperation.print() with already-connected client

### Documentation (5)
- CHANGELOG missing [0.8.0] compare link
- README test count (331) stale, should be 358
- TODO.md V2 rename description is self-referential (copy-paste error)
- TODO.md #18 references bleak 0.22 but project is on bleak 3.0
- `current_dir` attribute name misleading (should be `ui_dir`)

---

## Statistics

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 18 |
| MEDIUM | 35 |
| LOW/INFO | 69+ |
| **Total** | **~122** |

## Recommended Fix Priority

1. **Heartbeat guard bug** (#1) — Quick fix, high user impact
2. **`code_label` unbound** (#2) — Crash path, easy fix
3. **`_print_handler` TclError guard** (#3) — Can permanently block prints
4. **CancelledError phantom UUIDs** (#5) — BLE session corruption
5. **Windows spec DLL classification** (#6) — Build correctness
6. **New config class tests** (#15) — Coverage gap for new code
7. **printer_connected not updated after reconnect** (#12) — Performance waste
8. **Cairo surface leaks** (#10, #26) — Memory leaks in UI
