# NiimPrintX Deep-Dive Code Review — 2026-04-11

> 20 parallel review agents, full codebase coverage. Findings deduplicated and prioritized.

## CRITICAL (Fix before next release)

### 1. BLE Lock Design — No Cross-Method Exclusion
**Files:** `printer.py:50-51,88,122-140`
- `write_raw` uses `_print_lock`, `send_command` uses `_command_lock` — separate locks on the same BLE connection
- `write_no_notify` has **zero** locking
- During `print_image`, heartbeat coroutines can inject BLE traffic between image rows
- **Fix:** Unify to a single lock, or have `_print_lock` block all other BLE operations

### 2. `print_imageV2()` Never Calls `end_print()`
**File:** `printer.py:208-209`
- B1/B-series print path ends with `asyncio.sleep(2)` instead of status polling + `end_print()`
- Printer session left open; subsequent prints may fail
- **Fix:** Add status poll loop + `end_print()` matching `print_image()`

### 3. `set_dimension()` Called with Pre-Offset Image Size
**File:** `printer.py:155-156`
- `set_dimension(image.height, image.width)` uses original dimensions before offsets are applied
- `_encode_image` then produces more/fewer rows than declared
- Zero-size post-offset image silently yields nothing, leaving printer in mid-session
- **Fix:** Compute post-offset dimensions before sending protocol commands

### 4. Packet `from_bytes` Uses Negative Indices — Wrong Bytes on Oversized Packets
**File:** `packet.py:20-28`
- `pkt[-3]` and `pkt[-2:]` anchor to buffer end, not declared payload end
- Firmware that appends extra bytes (documented in upstream issues #1, #8, #32) causes checksum to read wrong position
- **Fix:** Anchor footer/checksum to `4 + len_ + 3` instead of buffer tail

### 5. `on_close()` Destroys Window Before Async Tasks Cancel
**File:** `main.py:96-97`
- `call_soon_threadsafe(loop.stop)` is non-blocking; `destroy()` runs immediately after
- `schedule_heartbeat` has no TclError guard — crashes on dead widget
- `FileMenu.on_close` uses `quit()` not `on_close()` — bypasses async shutdown entirely
- **Fix:** Cancel tasks, wait for loop thread, then destroy; unify close handlers

### 6. `_encode_image` Fill Value Creates Black Borders, Not Blank
**File:** `printer.py:220,226`
- `ImageOps.expand(..., fill=1)` on mode "1" — `fill=1` means "print dot" after inversion
- Positive offsets produce solid black margins instead of blank spacing
- **Fix:** Change `fill=1` to `fill=0`

### 7. Text DPI: `img.resolution` Set After Pixel Allocation (No-Op)
**File:** `TextOperation.py:33`
- `WandImage(width=..., height=...)` allocates pixels at default 72 DPI
- `img.resolution = (300, 300)` on line 33 is metadata-only after allocation
- All text renders at 72 DPI regardless of printer DPI (203/300)
- **Fix:** Set resolution before pixel allocation via `WandImage()` then `img.blank()`

### 8. `BLETransport.connect()` Silently Ignores Address After First Call
**File:** `bluetooth.py:48-54`
- `BleakClient` only created when `self.client is None` — subsequent `connect(new_address)` reuses old client
- `char_uuid` never cleared in `disconnect()` — stale handle on reconnect
- `connect()` return value not checked in `send_command` — silent continuation on failure
- **Fix:** Reset client/char_uuid in disconnect; check connect() return value

### 9. Multiple Print Popups Overwrite Instance State
**File:** `PrintOption.py:171-266`
- No modal grab — user can open multiple preview popups
- `self.print_image`, `self.print_button`, etc. overwritten by second popup
- Cross-contamination between popups
- **Fix:** Add `popup.grab_set()` to make modal

### 10. UserConfig `int()` Crashes App on Malformed TOML
**File:** `UserConfig.py:57-59`
- `int(device_conf.get("density", 3))` crashes on strings/lists
- Called from `AppConfig.__init__()` — crashes entire app at startup
- Zero/negative dimensions also pass `_validate_dims` validation
- **Fix:** Wrap in try/except with fallback; reject non-positive dimensions

## HIGH (Fix soon)

### 11. `resource_path()` Uses CWD in Dev Mode
**File:** `ui/__main__.py:33` — should use `os.path.dirname(__file__)`, not `os.path.realpath(".")`

### 12. `original_image` Stores Resized Copy, Not Source
**File:** `ImageOperation.py:29` — resize quality degrades; each save/load cycle compounds

### 13. `load_image` Has No Error Handling
**File:** `ImageOperation.py:10` — `Image.open()` crash on corrupt files with no messagebox

### 14. CLI `--quantity` Unbounded
**File:** `command.py:48-52` — no `IntRange`; negative wraps to 65535, zero starts empty job

### 15. `set_quantity()` Has No Validation
**File:** `printer.py:375-377` — `struct.pack(">H", -1)` raises raw `struct.error`

### 16. `end_page_print` Loop Has No Iteration Limit
**File:** `printer.py:169-170` — infinite loop if printer returns False continuously

### 17. No Decompression Bomb Protection on .niim Files
**File:** `FileMenu.py:129-153` — base64-decoded images from untrusted files have no pixel size cap

### 18. Heartbeat Returns All-None for Unknown Packet Lengths (Silent)
**File:** `printer.py:296-320` — no `case _:` logging; new firmware variants silently produce empty state

### 19. FontList `split(':')[1]` Truncates Windows Paths
**File:** `FontList.py:47,57` — **Fix:** `split(':', 1)[1]`

### 20. FontList Blocks Main Thread at Startup
**File:** `FontList.py:28` via `TextTab:15` — subprocess.run on main thread freezes UI

### 21. MouseWheel Non-Functional on Linux
**File:** `TabbedIconGrid.py:138-142` — `<MouseWheel>` never fires on X11; need `<Button-4>`/`<Button-5>` bindings

### 22. Logger Switches stderr→stdout in Verbose Mode
**File:** `logger_config.py:47` — `sys.stdout` should be `sys.stderr`

### 23. GitHub Actions No `permissions:` Block
**File:** `tag.yaml` — release job needs `contents: write`; will fail on restricted token policies

## MEDIUM (Should fix)

| # | Issue | File |
|---|-------|------|
| 24 | Unpinned third-party action (softprops/action-gh-release@v2) | tag.yaml |
| 25 | Windows ImageMagick download — no checksum verification | _build-windows.yaml |
| 26 | macOS/Windows tag extraction no guard for non-tag refs | _build-macos.yaml, _build-windows.yaml |
| 27 | CI lint job is only syntax check — no ruff/flake8/mypy | ci.yaml |
| 28 | Silent density truncation for D-series (no user warning) | command.py:94 |
| 29 | `setup_logger()` called twice per CLI invocation | command.py:10,26 |
| 30 | `logger._core.handlers` private API usage | logger_config.py:44-45 |
| 31 | Splash timer decoupled from actual resource loading | ui/__main__.py:46-48 |
| 32 | `default_bg` OS detection copy-pasted (TextTab + IconTab) | TextTab.py, IconTab.py |
| 33 | `mm_to_pixels` duplicated (CanvasSelector + PrintOption) | CanvasSelector.py, PrintOption.py |
| 34 | `_make_client()` copy-pasted across test files | test_printer.py, test_print_integration.py |
| 35 | `screen_dpi` captured but never used | AppConfig.py:64, CanvasSelector.py |
| 36 | BLE connection not disconnected on device change | CanvasSelector.py:39-40 |
| 37 | Canvas cleared without user confirmation | CanvasSelector.py:75-79 |
| 38 | `move_image` passes None to `canvas.move` before first select | ImageOperation.py:82-83 |
| 39 | MouseWheel double-bound per tab visit — scroll speed escalates | TabbedIconGrid.py:41-52 |
| 40 | Case-folding tab name corrupts mixed-case folder names | TabbedIconGrid.py:35 |
| 41 | Dead import: `messagebox` in IconTab.py, `ttk` in StatusBar.py | IconTab.py:4, StatusBar.py:2 |
| 42 | Dead code: `__aenter__`/`__aexit__` in BLETransport | bluetooth.py:36-46 |
| 43 | Dead code: commented-out grid layout in TabbedIconGrid | TabbedIconGrid.py:76-78,84-85 |
| 44 | `V2` method naming violates snake_case convention | printer.py |
| 45 | PrinterOperation silently swallows all exceptions as `False` | PrinterOperation.py:36-48 |
| 46 | Resize drag fires Wand render on every mouse-move (UI freeze) | TextOperation.py:151-161 |
| 47 | Old tk.PhotoImage not released from Tk image table (memory leak) | TextOperation.py:113-115 |
| 48 | IM7 deprecates `convert`; Linux path ignores bundled binary | FontList.py:18,23 |
| 49 | Variant regex too narrow — common weights misclassified | FontList.py:64 |
| 50 | Windows tempfile: PIL lazy-loads after os.remove → PermissionError | PrintOption.py:83-89 |

## Architecture Notes

- **AppConfig god-object** — holds UI state, device config, and runtime state in one mutable bag passed everywhere; cross-thread reads (`print_job` from asyncio thread) are data races under GIL
- **PrinterOperation layer** — legitimate lazy-reconnect value but exception-swallowing hides user-actionable errors
- **nimmy/ boundary is clean** — no imports from ui/; good separation
- **Module placement** — PrinterOperation and UserConfig are in `ui/` but contain no UI code
- **Test coverage** — 95 tests, strong on protocol/encoding, zero tests for UI widgets (TextOperation, ImageOperation, FileMenu, FontList parsing)

## Stats

- **20 review agents** dispatched
- **~120 findings** raw, deduplicated to **50 actionable items**
- **10 CRITICAL**, **13 HIGH**, **27 MEDIUM**
- **Runtime:** 6m 13s
