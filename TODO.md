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

## Future Improvements (Phase 3-6 from Round 4 Review)

- [x] **CI/CD pipeline** — Add test runner workflow, lint/type check, dependency audit, PR build check
- [x] **Expand test suite** — 60 tests total (UserConfig merge, CLI CliRunner, bluetooth find_device, PrinterClient heartbeat/validation/info)
- [x] **User config documentation** — Document TOML config format in README
- [x] **Rotation UI control** (#38) — Added rotation dropdown to print preview popup
- [x] **Update Flatpak metadata** — Change developer_name from "labbots" to fork maintainer
- [x] **Screenshot for metainfo** — Extracted main-window.png from NiimPrintX.gif
- [x] **README install instructions** — Fix contradictory venv + poetry install guidance
- [x] **Python version floor** — Document why >=3.12 (tomllib needs 3.11, bleak winrt needs 3.12)

- [x] **Error handling** — Add error handling to save_to_file, load_text/image, display_print, load_image (#69-74)
- [x] **Input validation** — Validate density spinbox, quantity IntRange, TOML config scalars (#45, #54, #55, #65)
- [x] **CLI exit codes** — CLI exits code 0 on all errors; needs sys.exit(1) (#62, #63)
- [x] **Dependencies** — Bump Pillow to ^12.1.1 (CVE fix), replace appdirs with platformdirs, remove unused devtools
- [x] **GitHub Actions** — Fix Linux job name, macOS runtime_hooks, version extraction, poetry cache, apt-get update
- [x] **Performance** — Replace getpixel() loop with tobytes()
- [x] **Dead code cleanup** — Remove dead imports, commented-out code in TextTab/CanvasSelector

## Code Review Fixes (2026-04-11, second session)

### Round 1 — Initial audit (9 fixes)
- [x] Removed leftover devtools import in cli/command.py
- [x] Replaced deprecated device.metadata with bleak 0.22+ API
- [x] Fixed struct.pack endianness in start_printV2
- [x] Fixed B1 label dimension 14→15mm
- [x] Switched .niim files from pickle to JSON
- [x] Scoped D110 UUID filter to D110 variants only
- [x] Synced requirements.txt with pyproject.toml

### Round 2 — Deep dive (29 fixes)
- [x] Fixed pyproject.toml packages config + entry points + extras
- [x] Fixed all Tkinter threading violations (TabbedIconGrid, PrintOption, PrinterOperation)
- [x] Added asyncio.Lock + finally to send_command
- [x] Replaced CacheManager pickle with JSON, deleted module-level demo
- [x] Replaced assert with raise ValueError in packet.py and printer.py
- [x] Added BLE bounds checking to get_rfid
- [x] Moved log path to user_log_dir
- [x] Fixed StatusBar oval leak, default_bg, spinbox validation, resize_text order
- [x] Fixed negative offset crash, find_device None guard, CLI connect handling
- [x] Updated AppStream metainfo to v0.2.0

### Round 4 — Deep dive (13 critical fixes, 20 parallel review agents, 95 findings total)
- [x] Fixed send_command notification race (clear event before wait, not after)
- [x] Catch ValueError from from_bytes, wrap as PrinterException
- [x] Added _print_lock to prevent heartbeat interleaving with image data
- [x] Fixed BleakClient.connect() return value (returns None not bool in bleak >= 0.14)
- [x] Fixed BLETransport.connect() already-connected returning False
- [x] Added packet length field validation in from_bytes
- [x] Fixed heartbeat case 10 rfid_read_state duplication (still present despite Round 3)
- [x] Renamed set_dimension(w,h) → set_dimension(height, width) to match call sites
- [x] Stop asyncio loop in on_close before destroy()
- [x] Guard _print_handler against destroyed widgets (TclError)
- [x] Fix lambda captures in schedule_heartbeat (bind by value)
- [x] Fix text DPI — set resolution on Image not Drawing (was no-op at 72 DPI)
- [x] Fix WandImage memory leak (context-manage metrics probe)
- [x] Fix os.environ not updated in load_libraries (local dict copy never written back)
- [x] Handle both tk.PhotoImage and ImageTk.PhotoImage in save_to_file
- [x] Fix icon grid anchor n → nw (left half was clipped)
- [x] Force img.load() in background thread (PIL lazy loading defeated threading)
- [x] Move NotebookTabChanged bind outside loop (was registered N times)
- [x] Added 9 new tests (22 total, all passing)

### Round 3 — Final pass (29 fixes)
- [x] Fixed heartbeat case 10 copy-paste bug (rfid_read_state index)
- [x] Added 60s timeout to print_image status polling
- [x] Guarded against zero-width image in _encode_image
- [x] Replaced CLI assert with print_error for image width check
- [x] Added finally block to _info() for BLE disconnect
- [x] Fixed logger_enable(0) nuking all handlers
- [x] Fixed heartbeat() returning None on race condition
- [x] Moved ImageTk.PhotoImage to main thread in TabbedIconGrid
- [x] Wrapped FontList subprocess in try/except for missing ImageMagick
- [x] Validated TOML config values in UserConfig
- [x] Clear stale canvas items on device/size change
- [x] write_raw/write_no_notify now raise instead of swallowing errors
- [x] File load validates keys, clears stale state before rebuild
- [x] Reset printer_connected on device change
- [x] update_text_properties now re-renders canvas image
- [x] Removed dead code: scan_devices, CacheManager, __del__, commented blocks
- [x] Removed pickle fallback entirely from FileMenu
- [x] Updated pillow pin for CVE-2024-35655

## Completed (2026-04-11, first session)

### Upstream PRs Merged (8)
- [x] #28 — Encoding fix (Korean Windows crash)
- [x] #30 — Device selection propagation
- [x] #36 — D11_H 300dpi support + per-device DPI
- [x] #33 — D110 BLE connection heuristic
- [x] #6 — B1 V2 protocol (with 3 bug fixes)
- [x] #39 — Multi-line text labels
- [x] #16 — Linux desktop/metainfo files
- [x] #41 — Python 3.13 support + bleak bump

### Quick Wins (Tier 1)
- [x] Added d101, B21, D110-M device configs
- [x] Removed devtools imports from 11 files
- [x] Fixed print_label lambda capture bug
- [x] Added None guard to update_canvas_size()

### Feature Work (Tier 2-3)
- [x] Hardened send_command() — raises PrinterException instead of returning None
- [x] Per-device rotation configuration
- [x] Open .niim files from command-line
- [x] User config file (TOML at ~/.config/NiimPrintX/)
- [x] Modern Linux theming (sv-ttk Sun Valley)
- [x] Test suite foundation (13 tests, all passing)

## Burn Session 2 — Additional Improvements (2026-04-11)

- [x] **Rotation UI control** (#38) — Rotation dropdown added to print preview popup
- [x] **Screenshot for metainfo** — Extracted from NiimPrintX.gif
- [x] **TextOperation cleanup** — Removed remaining commented-out code
- [x] **Test expansion** — 75+ tests (image encoding verification, CLI exit codes, utility modules, get_rfid, integration)
- [x] **Upstream issue triage** — Items documented as needing manual upstream access
