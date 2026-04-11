# NiimPrintX Code Review - Round 7

**Date:** 2026-04-11
**Method:** 20-agent parallel deep dive (Opus 4.6) — regression verification + integration flows
**Scope:** Post-Round 6 fix verification, E2E flow tracing, cross-cutting concerns

---

## Executive Summary

Round 7 focused on verifying Round 6 fixes and tracing end-to-end flows. Found **1 regression that breaks text completely**, **1 protocol routing bug**, and **several incomplete fixes** from Round 6.

| Severity | Count |
|----------|-------|
| Critical | 11 |
| Important | 18 |
| Minor | 5 |

---

## Critical Findings

### R1. `base64.b64encode()` returns bytes, not str — text creation completely broken
**File:** `TextOperation.py:43` | **Confirmed by:** 2 agents (text rendering, regression UI)

`tk.PhotoImage(data=base64.b64encode(img_blob))` passes `bytes` to Tkinter, which stringifies it as `"b'iVBOR...'"` — an invalid base64 literal. Every `create_text_image` call crashes with `TclError`.

**Fix:** `tk.PhotoImage(data=base64.b64encode(img_blob).decode('ascii'))`

### R2. b18/b21 models routed to V1 print path instead of V2
**File:** `command.py:128` | **Confirmed by:** 3 agents (V1 E2E, V2 E2E, CLI)

`if model == "b1"` only routes B1 to `print_imageV2`. B18 and B21 fall through to `print_image` (V1), sending wrong protocol commands.

**Fix:** `if model in ("b1", "b18", "b21"):`
Also: forward `vertical_offset` and `horizontal_offset` to `print_imageV2`.

### R3. Dead `CommandCollection` still in command.py
**File:** `command.py:187-189` | **Confirmed by:** 2 agents

C22 fix updated the entry point but left the dead `cli = click.CommandCollection(...)` object. Import trap for future contributors.

**Fix:** Delete lines 187-189.

### R4. `_loop` not initialized in `__init__` — AttributeError before first connect
**File:** `printer.py:46-53, 143` | **Confirmed by:** 4 agents

`self._loop` is only set in `connect()`. If a BLE notification fires before connect completes, `notification_handler` crashes.

**Fix:** `self._loop = None` in `__init__`, guard in `notification_handler`.

### R5. `asyncio.get_event_loop()` deprecated in async context
**File:** `printer.py:59` | **Confirmed by:** 2 agents

Python 3.10+ deprecates this from non-main threads. Use `asyncio.get_running_loop()`.

### R6. `write_raw` doesn't catch ValueError from `to_bytes()`
**File:** `printer.py:130-138` | **Confirmed by:** 2 agents (V1 E2E, regression)

`NiimbotPacket.to_bytes()` raises `ValueError` on oversized data. `write_raw` only catches `BLEException`. `ValueError` escapes the `except PrinterException` cleanup in `print_image`, so `end_print` is never called.

**Fix:** Add `ValueError` to the except clause in `write_raw`.

### R7. `connect()` doesn't disconnect transport on `find_characteristics` failure
**File:** `printer.py:56-63` | **Confirmed by:** 3 agents

If `find_characteristics()` raises, the BLE link is left connected. The discarded `PrinterClient` orphans the `BleakClient`. Printer may reject new connections.

**Fix:** Wrap `find_characteristics()` in try/except, disconnect transport before re-raising.

### R8. `done_callback` calls Tkinter from asyncio thread
**File:** `main.py:102-103` | **Confirmed by:** 2 agents

`Future.add_done_callback` runs on the asyncio thread. `self.after(0, self.destroy)` calls into Tcl from a non-main thread — undefined behavior, potential segfault.

**Fix:** Use polling pattern: set a `threading.Event`, poll it from the main thread.

### R9. Async loop never stopped, BLE never disconnected on shutdown
**File:** `main.py:93-103` | **Confirmed by:** 2 agents

`on_close` cancels tasks but never calls `printer_disconnect()` or `loop.stop()`. Heartbeat `_heartbeat_active` never set to False. Daemon thread runs forever until process exit.

### R10. `deselect_image` has same None bbox issue (missed by C15 fix)
**File:** `ImageOperation.py:76-78` | **Confirmed by:** 2 agents

The C15 fix was applied to `delete_image` but not `deselect_image`. `"bbox" in dict` is True (key exists with value None), so `canvas.delete(None)` is called.

**Fix:** Change guard to `if item.get("bbox") is not None:`

### R11. `ImageTk.getimage()` on `tk.PhotoImage` crashes — text export broken
**File:** `PrintOption.py:156` | **Confirmed by:** 1 agent (text rendering)

`export_to_png` calls `ImageTk.getimage()` on `tk.PhotoImage` objects (from text). This method only works on `ImageTk.PhotoImage`. Need isinstance guard like FileMenu.

---

## Important Findings

### I1. `_notifying_uuids` not cleared on same-address reconnect (`bluetooth.py:46`)
### I2. `notification_data` still written from BLE thread — incomplete C2 fix (`printer.py:141-143`)
### I3. "Print job failed" log has no exception context (`printer.py:195, 250`)
### I4. Aspect ratio breaks at minimum height clamp (`ImageOperation.py:110-114`)
### I5. Dead `dy` and `initial_height` expressions (`ImageOperation.py:98, 102`)
### I6. Missing `image.load()` on resized image — I7 fix gap (`FileMenu.py:153`)
### I7. Cross-device .niim load crashes with KeyError (`FileMenu.py:109-111`)
### I8. Label size dropdown not updated after file load (`FileMenu.py:109-111`)
### I9. `update_status` redundant `after(0)` → direct call (`PrintOption.py:47`)
### I10. `_heartbeat_active` never wired to shutdown (`PrintOption.py:30`)
### I11. Print failures completely silent to user — no error dialog (`PrintOption.py:322-334`)
### I12. `scrollregion` bbox called before geometry propagation (`TabbedIconGrid.py:148`)
### I13. `print_imageV2` call missing offset params (`command.py:130`)
### I14. `print_dpi` not bounds-validated for user devices (`UserConfig.py:79`)
### I15. Print density Spinbox default hardcoded to 3 regardless of device (`PrintOption.py:197`)
### I16. `test_coverage_gaps.py` duplicate `_make_client`, should use conftest (`tests/`)
### I17. `make_client` fixture missing `_loop` attribute (`tests/conftest.py`)
### I18. Startup crash handler uses bare `print()` — invisible on Windows PyInstaller (`ui/__main__.py:55`)

---

## Action Plan

### Phase 1: Critical regressions (fix immediately)
1. R1 — TextOperation base64 decode
2. R2 — b18/b21 V2 routing + offset params
3. R3 — Remove dead CommandCollection
4. R4+R5 — _loop initialization + get_running_loop
5. R6 — write_raw ValueError catch
6. R7 — connect() cleanup on find_characteristics failure
7. R8+R9 — Shutdown: polling pattern, loop.stop, printer disconnect, heartbeat stop
8. R10 — deselect_image None bbox
9. R11 — export_to_png isinstance guard for tk.PhotoImage

### Phase 2: Important fixes
10-27. All I1-I18 items

### Phase 3: Test + docs cleanup
28. Fix test_coverage_gaps.py to use conftest fixture + add _loop
29. Update README --quantity annotation
30. Fix stale TODO.md test count
