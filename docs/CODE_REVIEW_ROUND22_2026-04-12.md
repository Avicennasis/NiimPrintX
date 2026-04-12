# NiimPrintX Code Review — Round 22 (2026-04-12)

**25-agent deep dive across: type safety, architecture, security, CI/CD, code quality, tests, performance, build, cross-platform, error handling, docs**

## Summary

- **25 agents** analyzed 55 Python files, 5 CI workflows, 6 PyInstaller specs, all docs
- **~130 findings** across all categories
- **13 CRITICAL**, **45 HIGH**, remainder MEDIUM/LOW
- Organized into implementation phases below

---

## Phase 1 — CRITICAL Bugs & Security (implement immediately)

### C1. mypy printer.py:89 — union-attr (`self.transport.client` may be None)
```python
# Add guard at top of find_characteristics:
if self.transport.client is None:
    raise PrinterException("BLE client not initialized")
```

### C2. mypy printer.py:132 — arg-type (`notification_data` may be None)
```python
# Add guard after wait_for:
if self.notification_data is None:
    raise PrinterException("Notification arrived but contained no data")
```

### C3. ImageOperation.select_image:61 — bbox() None dereference (BUG)
Missing `if bb is None: return` guard (TextOperation has this, ImageOperation doesn't).

### C4. ImageOperation.start_image_resize:51 — missing initial_y (BUG)
Only sets `initial_x` on resize handle click. Missing `initial_y` causes stale drag values.

### C5. PrintOption:429 — wrong value passed to status bar (BUG)
Passes print job result (`True`) instead of `self.config.printer_connected`.

### C6. TextOperation.delete_text:87 — handle None check missing (BUG)
`canvas.delete(handle)` without checking `handle is not None`.

### C7. `_encode_image` P mode transparency — palette images silently lose transparency
`P` mode images with transparency key fall through to `convert("L")` without compositing.
Need new `elif image.mode == "P": image = image.convert("RGBA")` before RGBA branch.

### C8. Security: unbounded base64 decode in FileMenu (memory bomb)
`load_text`/`load_image` decode base64 with no size cap before pixel check.
Add `_MAX_B64_IMAGE_BYTES = 10 * 1024 * 1024` guard before `base64.b64decode()`.

### C9. Security: TabbedIconGrid missing MAX_IMAGE_PIXELS
Only `Image.open()` call site without `PIL.Image.MAX_IMAGE_PIXELS = 5_000_000`.

### C10. CI: Windows build script injection (_build-windows.yaml:111,117)
VERSION interpolated directly in PowerShell `run:` blocks. Use `env:` context.

### C11. CI: macOS build script injection (_build-macos.yaml:68)
VERSION passed as shell argument. Use `env:` context.

### C12. Cross-platform: AppConfig.py:19 — hardcoded `/` separator
`f"{self.current_dir}/icons"` → `os.path.join(self.current_dir, "icons")`

### C13. Cross-platform: __main__.py:23 — DYLD_LIBRARY_PATH wrong
Set on Linux (wrong OS), points to base dir not `lib/` on macOS.

---

## Phase 2 — HIGH Priority Fixes

### H1. set_dimensionV2 missing copies bounds check (printer.py:530)
### H2. RFID barcode/serial no control-char sanitization (printer.py:408,416)
### H3. packet.py trailing bytes — add warning log
### H4. process_png.py @-prefix ImageMagick injection
### H5. Cairo img_surface never .finish()'d in export_to_png loops
### H6. save_image() swallows all exceptions — no error dialog (PrintOption.py:146)
### H7. `raise e` breaks traceback in print_label (PrintOption.py:413) → bare `raise`
### H8. add_text_to_canvas no exception handling for Wand errors
### H9. notification_handler silent drop when _loop is None — add logging
### H10. Image.MAX_IMAGE_PIXELS global mutation — save/restore pattern
### H11. send_command code_label resolution 4x duplication → resolve once
### H12. _encode_image PA/RGBA branch duplication with intermediate leak
### H13. info_command `success` variable potentially unbound → init `success = False`
### H14. `was_connecting` local variable shadowed immediately (PrintOption.py:88)
### H15. ui/types.py dead — never imported (wire up or delete)
### H16. CI: coverage threshold mismatch (CI=90%, pyproject.toml=80%)
### H17. CI: PrintOption.py missing from coverage omit list
### H18. CI: no concurrency control on tag/ci workflows
### H19. CI: pin windows-latest, macos-latest to specific versions
### H20. CI: apt → apt-get consistency
### H21. Poetry lock stale (`<3.14` vs `<3.16` in pyproject.toml)
### H22. pytest-asyncio `<1` blocks stable 1.x
### H23. README version stale (v0.6.1 → v0.7.0)
### H24. README test count stale

---

## Phase 3 — Architecture Refactors

### A1. Move helper.py from nimmy/ to cli/
- Clean move, zero dependencies, 2 files to update + 8 test import lines
- No circular import risk

### A2. Move UserConfig.py from ui/ to nimmy/userconfig.py
- Clean move, enables CLI to share user config
- 1 production file + 5 test files need import updates
- Rename to lowercase `userconfig.py` per nimmy/ convention

### A3. FileMenu callback decoupling (5 coupling points)
- `on_close`, `on_deselect_all`, `on_load_canvas_config`, `on_bind_text_select`, `on_bind_image_select`
- Removes `self.root` dependency on sibling widget internals

### A4. AppConfig God object split (future — large scope)
- ImmutableConfig (os_system, current_dir, icon_folder, label_sizes, cache_dir)
- CanvasState (canvas, bounding_box, text_items, image_items, current_selected, frames)
- PrinterState (device, current_label_size, printer_connected, print_job)
- 12 files need updating, recommend separate session

---

## Phase 4 — Code Quality & Modernization

### Q1. camelCase V2 methods → snake_case (print_image_v2, start_print_v2, set_dimension_v2)
### Q2. Mixed absolute/relative imports in ui/main.py
### Q3. Scattered Image.MAX_IMAGE_PIXELS → shared constant
### Q4. logging.getLogger in main.py → loguru get_logger()
### Q5. os.path in AppConfig.py → pathlib
### Q6. Duplicate coords validation in FileMenu
### Q7. Duplicate bbox/handle update in TextOperation/ImageOperation
### Q8. isinstance tuple form → union (packet.py, UserConfig.py, FileMenu.py)
### Q9. FontList.py if/elif platform → match/case
### Q10. TabbedIconGrid scroll loop → single yview_scroll(3*direction)

---

## Phase 5 — Performance

### P1. start_notify/stop_notify on every command (up to 800 BLE round-trips per print)
### P2. TextTab no debounce on Wand render (UI freeze on fast property changes)
### P3. Font disk cache (avoid subprocess re-run on every launch)
### P4. export_to_png PNG round-trip on every offset spinbox tick
### P5. NiimbotPacket.to_bytes tuple spread → bytearray

---

## Phase 6 — Build & Packaging

### B1. macOS entitlements.plist for Bluetooth TCC (entitlements_file=None)
### B2. macOS ImageMagick dylibs in datas instead of binaries (rpath not fixed)
### B3. Windows ImageMagick path relative to CWD, not spec file
### B4. CLI specs: no excludes (tkinter/wand/cairo bloating CLI binary)
### B5. Linux spec: icon=nimx-512.png ignored, TK path derivation no existence guard

---

## Phase 7 — Test Gaps (20 proposed tests)

### T1. _encode_image PA mode (zero coverage)
### T2. _encode_image LA mode (zero coverage)
### T3. get_rfid serial-length overrun
### T4. get_rfid trailer-fields underrun
### T5. write_raw with char_uuid=None
### T6. merge_label_sizes non-dict devices value
### T7. PrinterOperation.printer_disconnect exception path
### T8. PrinterOperation.print pre-connected fast path
### T9. FontList group_fonts_by_family System-prefix exclusion
### T10. _validate_dims three-element list
### T11. _print_job KeyboardInterrupt cleanup
### T12. concurrent send_command serialization
### T13. notification_data=None at from_bytes
### T14. find_characteristics empty services / multiple matches
### T15. BLE drop mid image-row writes
### T16. helper.py NO_COLOR env var
### T17. CLI zero-byte file handling
### T18. CLI large offset exceeding protocol limit
### T19. CLI verbose=2 same as verbose=1
### T20. FontList bundled unknown platform magick=None

---

## Phase 8 — Documentation

### D1. README version v0.6.1 → v0.7.0
### D2. README test count update
### D3. Document niimprintx/niimprintx-ui entry points
### D4. Dev section: add ruff format + mypy steps
### D5. Python version badge
### D6. CHANGELOG.md
### D7. macOS setup: brew --prefix for arch-agnostic paths
### D8. ImageMagick noted as GUI-only requirement
### D9. Lint command: add tests/ to path
### D10. Dependabot pip entry: comment out or remove
