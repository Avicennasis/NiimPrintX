# NiimPrintX Deep Dive Code Review — Round 11

**Date:** 2026-04-12
**Method:** 4 audit agents (UI, build, tests, security) + 21 parallel fix agents
**Baseline:** 306 tests, 97.58% coverage, 0 ruff errors, 54 files formatted

---

## Executive Summary

**Total fixes applied: 21 across 6 themes**
- Theme A: App Lifecycle & Thread Safety — 5 fixes (3 critical)
- Theme B: BLE Protocol Hardening — 2 fixes (1 high)
- Theme C: Build Pipeline — 4 fixes (2 high)
- Theme D: Test Quality Overhaul — 5 improvements
- Theme E: Security Hardening — 3 fixes
- Theme F: UX & Code Cleanup — 3 fixes
- Theme G: CI/CD — 1 improvement

**Result:** 309 tests, 96.76% coverage, 0 lint errors, 55 files formatted

---

## Theme A: App Lifecycle & Thread Safety

### A1. Heartbeat Loop Hang on Close (CRITICAL)
**File:** `PrintOption.py:33-57`
**Issue:** `schedule_heartbeat` loop caught `TclError` to break but never set `_heartbeat_active = False`, causing potential infinite loop during shutdown.
**Fix:** Set `_heartbeat_active = False` before every `break`. Wrapped `root.after()` calls in individual `try/except TclError` blocks. Added `_heartbeat_active` check before `root.after()` calls.

### A2. Image Memory Leak on App Exit (CRITICAL)
**File:** `main.py:112-120`
**Issue:** PIL images in `config.image_items` and `config.text_items` never closed on app quit.
**Fix:** Added cleanup in `_shutdown` that iterates and closes all `original_image` PIL objects, then clears both dicts.

### A3. PhotoImage Reference Leak in TabbedIconGrid (CRITICAL)
**File:** `TabbedIconGrid.py:140-143`
**Issue:** Old PhotoImage lists replaced without cleanup when tab icons reloaded.
**Fix:** Pop and clear old refs before assigning new ones. Added `winfo_exists()` guard in `on_icon_click`.

### A4. ImageOperation Delete Safety
**File:** `ImageOperation.py`
**Fix:** Close `original_image` PIL on delete. Set bbox/handle to None after canvas deletion in `deselect_image`.

### A5. TextOperation Safety Guards
**File:** `TextOperation.py`
**Fix:** Guard `bbox()` return for None in `draw_bounding_box` and `update_bbox_and_handle`. Guard `delete_text` against missing dict key.

---

## Theme B: BLE Protocol Hardening

### B1. RFID Response Bounds Validation (HIGH)
**File:** `printer.py:get_rfid()`
**Issue:** Length-prefixed fields parsed without bounds checking — crafted BLE response could cause IndexError.
**Fix:** Added 3 bounds checks: `barcode_len`, `serial_len`, and struct.unpack trailer. Each logs error and returns None.

### B2. BLE Authentication Documentation
**File:** `bluetooth.py`
**Fix:** Added design-limitation comment documenting that Niimbot printers use unauthenticated BLE pairing (hardware protocol limitation).

---

## Theme C: Build Pipeline

### C1-C3. CLI Specs Missing Hiddenimports (HIGH)
**Files:** All 3 CLI spec files (Linux, macOS, Windows)
**Issue:** `hiddenimports=[]` — CLI builds would crash with ImportError.
**Fix:** Added `collect_submodules('PIL') + collect_submodules('bleak') + ['click', 'loguru', 'rich', 'platformdirs']`.

### C4. macOS UI Spec PIL Collection Gap
**File:** `spec_files/ui_app/NiimPrintX-mac.spec`
**Issue:** Missing `collect_submodules('PIL')` and `collect_submodules('tkinter')` — Linux/Windows had them.
**Fix:** Normalized to match Linux/Windows specs.

---

## Theme D: Test Quality Overhaul

### D1. Shared Test Fixtures
**File:** `tests/conftest.py`
**Fix:** Added `make_fake_write(client, response_pkt)` shared helper for mocking BLE notification delivery.

### D2. Heartbeat Test Parameterization
**File:** `tests/test_printer.py`
**Fix:** Replaced 5 individual heartbeat tests with single `@pytest.mark.parametrize` test with 5 cases.

### D3. Weak Assertion Tests
**File:** `tests/test_utils.py`
**Fix:** Replaced 5 "no-crash" tests with meaningful assertions (captured output, handler verification, level changes).

### D4. CLI Test Parameterization
**File:** `tests/test_cli_command.py`
**Fix:** Parameterized density capping, disconnect behavior, and quantity validation tests. ~60 lines saved.

### D5. Integration Tests
**File:** `tests/test_integration.py` (NEW)
**Fix:** 3 end-to-end tests: V1 print workflow, V2 B21 print workflow, print failure recovery with end_print cleanup.

---

## Theme E: Security Hardening

### E1. FileMenu Aggregate Image Limit
**File:** `FileMenu.py`
**Fix:** Added `_MAX_ITEMS_PER_FILE = 100` limit on total text+image items loaded from .niim files. Prevents OOM via crafted files.

### E2. FontList Magick Path Hardening
**File:** `FontList.py`
**Fix:** Replaced bare binary name fallbacks with `shutil.which()` validation. Logs warnings for PATH-resolved binaries.

### E3. UserConfig Type Validation
**File:** `UserConfig.py`
**Fix:** `_safe_int` now rejects non-whole floats (e.g., `density = 3.7`) instead of silently rounding. Whole-number floats (3.0) still accepted.

---

## Theme F: UX & Code Cleanup

### F1. CanvasOperation Type Annotations
**File:** `CanvasOperation.py`
**Fix:** Confirmed not dead code (bound in CanvasSelector.py:134). Added type annotations.

### F2. StatusBar + CanvasSelector Annotations
**Files:** `StatusBar.py`, `CanvasSelector.py`
**Fix:** Added `from __future__ import annotations` and full method type annotations.

### F3. SplashScreen Resource Cleanup
**File:** `SplashScreen.py`
**Fix:** Initialize `self.image = None` before try block. Added `close()` method. Added type annotations.

---

## Theme G: CI/CD

### G1. CLI Smoke Test
**File:** `.github/workflows/ci.yaml`
**Fix:** Added `poetry run niimprintx --help` step after dependency install to verify CLI imports resolve.

---

## Summary Table

| Metric | Before | After |
|--------|--------|-------|
| Tests | 306 | **309** |
| Coverage | 97.58% | **96.76%** |
| Lint errors | 0 | **0** |
| Formatted files | 54 | **55** |
| Files changed | — | **~30** |
| Agents dispatched | — | **21** |
