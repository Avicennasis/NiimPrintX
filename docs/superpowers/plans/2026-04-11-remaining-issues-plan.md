# NiimPrintX Remaining Issues & Tech Debt Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address all remaining fixable issues and tech debt from the NiimPrintX fork takeover — hardening the printer communication, adding missing features, and establishing a test suite.

**Architecture:** Fixes are ordered by impact and dependency. Error handling in printer.py goes first since many issues stem from unguarded None returns. Feature work builds on the hardened base. Test suite uses pytest with mocked BLE transport for unit tests.

**Tech Stack:** Python 3.12+, bleak (BLE), Tkinter, Click, Pillow, pycairo, wand, pytest

---

## Issue/Debt Tracker

| ID | Source | Description | Task |
|----|--------|-------------|------|
| TD1 | Code review | `send_command()` returns None on timeout — callers crash | Task 1 |
| TD9 | Code review | No error recovery in print paths | Task 1 |
| #3 | Upstream | NoneType error on D110 print | Task 1 |
| #24 | Upstream | Wrong orientation D11 on Flatpak | Task 2 |
| #38 | Upstream | Rotate text/image feature request | Task 2 |
| #17 | Upstream | Open .niim files from command-line | Task 3 |
| #7 | Upstream | Config file for label sizes | Task 4 |
| #14 | Upstream | Better look on Linux | Task 5 |
| TD6 | Code review | No test suite | Task 6 |
| #18 | Upstream | macOS Event loop crash | Task 7 (research) |

---

### Task 1: Harden send_command() and print error handling

**Fixes:** TD1, TD9, #3
**Impact:** Critical — most printing bugs trace back to unguarded None returns
**Files:**
- Modify: `NiimPrintX/nimmy/printer.py`

- [ ] **Step 1: Make send_command() raise on failure instead of returning None**

The current `send_command()` (line 85-102) catches `TimeoutError` and `BLEException` and silently returns None. Every caller then crashes with `AttributeError: 'NoneType' object has no attribute 'data'`.

Fix: raise `PrinterException` in the except blocks instead of silently returning:

```python
async def send_command(self, request_code, data, timeout=10):
    try:
        if not self.transport.client or not self.transport.client.is_connected:
            await self.connect()
        packet = NiimbotPacket(request_code, data)
        await self.transport.start_notification(self.char_uuid, self.notification_handler)
        await self.transport.write(packet.to_bytes(), self.char_uuid)
        logger.debug(f"Printer command sent - {RequestCodeEnum(request_code).name}:{request_code} - {[b for b in data]}")
        await asyncio.wait_for(self.notification_event.wait(), timeout)
        response = NiimbotPacket.from_bytes(self.notification_data)
        logger.debug(f"Printer response received - {[b for b in response.data]} - {len(response.data)} bytes")
        await self.transport.stop_notification(self.char_uuid)
        self.notification_event.clear()
        return response
    except asyncio.TimeoutError:
        logger.error(f"Timeout occurred for request {RequestCodeEnum(request_code).name}")
        raise PrinterException(f"Printer timed out on {RequestCodeEnum(request_code).name}")
    except BLEException as e:
        logger.error(f"An error occurred: {e}")
        raise PrinterException(f"BLE error during {RequestCodeEnum(request_code).name}: {e}")
```

- [ ] **Step 2: Add try/except to print_image() for graceful failure**

Wrap the print loop in `print_image()` so that a mid-print failure disconnects cleanly:

```python
async def print_image(self, image, density=3, quantity=1, vertical_offset=0, horizontal_offset=0):
    try:
        await self.set_label_density(density)
        await self.set_label_type(1)
        await self.start_print()
        await self.start_page_print()
        await self.set_dimension(image.height, image.width)

        for pkt in self._encode_image(image, vertical_offset, horizontal_offset):
            await self.write_raw(pkt)

        while not await self.end_page_print():
            await asyncio.sleep(0.1)

        while True:
            status = await self.get_print_status()
            if status["page"] == quantity:
                break
            await asyncio.sleep(0.1)

        await self.end_print()
    except PrinterException:
        logger.error("Print job failed")
        raise
```

- [ ] **Step 3: Same pattern for print_imageV2()**

```python
async def print_imageV2(self, image, density=3, quantity=1, vertical_offset=0, horizontal_offset=0):
    try:
        await self.set_label_density(density)
        await self.set_label_type(1)
        await self.start_printV2(quantity=quantity)
        await self.start_page_print()
        await self.set_dimensionV2(image.height, image.width, quantity)

        for pkt in self._encode_image(image, vertical_offset, horizontal_offset):
            logger.debug(f"Sending packet: {pkt}")
            await self.write_raw(pkt)
            await asyncio.sleep(0.01)

        await self.end_page_print()
        await asyncio.sleep(2)
    except PrinterException:
        logger.error("B1 print job failed")
        raise
```

- [ ] **Step 4: Update GUI error handling in PrinterOperation.py**

The `print()` method in `PrinterOperation.py` already catches `Exception` and shows a messagebox — verify `PrinterException` propagates correctly through this path.

- [ ] **Step 5: Update CLI error handling in command.py**

The `_print()` function already catches `Exception` — verify `PrinterException` propagates to the `print_error()` call.

- [ ] **Step 6: Commit**

```bash
git add NiimPrintX/nimmy/printer.py
git commit -m "fix: harden send_command to raise on failure instead of returning None

Previously, send_command() silently returned None on timeout or BLE
errors. Every caller assumed a valid response, causing NoneType crashes.
Now raises PrinterException, caught by existing error handlers in
CLI and GUI.

Fixes #3"
```

---

### Task 2: Configurable rotation per model

**Fixes:** #24, partially #38
**Impact:** Important — wrong orientation makes labels unusable
**Files:**
- Modify: `NiimPrintX/ui/AppConfig.py` (add rotation config per device)
- Modify: `NiimPrintX/ui/widget/PrintOption.py` (use per-device rotation)
- Modify: `NiimPrintX/cli/command.py` (apply rotation in CLI path too)

- [ ] **Step 1: Add rotation_angle to each device in AppConfig.py**

Add `"rotation": -90` to all D-series devices and `"rotation": 0` to B-series:

```python
# In each device dict, add:
"d110": { ..., "rotation": -90 },
"d11": { ..., "rotation": -90 },
"d11_h": { ..., "rotation": -90 },
"d110_m": { ..., "rotation": -90 },
"d101": { ..., "rotation": -90 },
"b18": { ..., "rotation": 0 },
"b21": { ..., "rotation": 0 },
"b1": { ..., "rotation": 0 },
```

- [ ] **Step 2: Use per-device rotation in PrintOption.py**

Replace the hardcoded B1 conditional in `print_label()`:

```python
rotation = self.config.label_sizes[self.config.device].get("rotation", -90)
image = image.rotate(rotation, PIL.Image.NEAREST, expand=True)
```

- [ ] **Step 3: Apply rotation in CLI print path**

In `command.py`, in `print_command()`, after the image is opened and resized, apply rotation based on model. Read the rotation from AppConfig or hardcode the D/B split:

```python
if model in ("b1", "b18", "b21"):
    rotation = 0
else:
    rotation = -90
image = image.rotate(rotation, Image.NEAREST, expand=True)
```

Note: The CLI doesn't use AppConfig, so either duplicate the rotation map or import it.

- [ ] **Step 4: Commit**

```bash
git add NiimPrintX/ui/AppConfig.py NiimPrintX/ui/widget/PrintOption.py NiimPrintX/cli/command.py
git commit -m "feat: per-device rotation configuration

Moves rotation from hardcoded B1 conditional to per-device config.
D-series: -90 degrees, B-series: 0 degrees.
Users with orientation issues can adjust per-device.

Fixes #24, partially addresses #38"
```

---

### Task 3: Open .niim files from command-line

**Fixes:** #17
**Impact:** Medium — convenience feature for power users
**Files:**
- Modify: `NiimPrintX/ui/__main__.py` (accept argv)
- Modify: `NiimPrintX/ui/widget/FileMenu.py` (extract open logic)

- [ ] **Step 1: Accept file argument in ui/__main__.py**

Modify the `if __name__ == "__main__"` block to check `sys.argv` for a file path:

```python
if __name__ == "__main__":
    try:
        app = LabelPrinterApp()
        image_path = resource_path('NiimPrintX/ui/assets/Niimprintx.png')
        splash = SplashScreen(image_path, app)
        app.load_resources()

        # Open file from command-line if provided
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            app.after(100, lambda: app.file_menu.open_file(sys.argv[1]))

        app.after(5000, splash.destroy)
        app.after(5000, app.deiconify)
        app.mainloop()
    except Exception as e:
        print(f"Error {e}")
        raise e
```

- [ ] **Step 2: Extract open logic in FileMenu.py**

Read `FileMenu.py` to understand the current `open_file` method. It may use `filedialog.askopenfilename()` — extract the actual file loading into a method that accepts a path:

```python
def open_file(self, file_path=None):
    if file_path is None:
        file_path = filedialog.askopenfilename(filetypes=[("Niim Files", "*.niim"), ("PNG Files", "*.png")])
    if file_path:
        # ... existing loading logic ...
```

- [ ] **Step 3: Verify the .desktop file's Exec line supports %f**

Check `assets/linux/io.github.labbots.NiimPrintX.desktop` — it already has `Exec=niimprintx %f` which passes the file path. Good.

- [ ] **Step 4: Commit**

```bash
git add NiimPrintX/ui/__main__.py NiimPrintX/ui/widget/FileMenu.py
git commit -m "feat: open .niim files from command-line

python -m NiimPrintX.ui /path/to/label.niim now opens the file.
Works with the .desktop file's %f argument for file association.

Fixes #17"
```

---

### Task 4: User config file for label sizes

**Fixes:** #7
**Impact:** Medium — enables custom labels without code changes
**Files:**
- Create: `NiimPrintX/ui/UserConfig.py`
- Modify: `NiimPrintX/ui/AppConfig.py` (merge user config on init)

- [ ] **Step 1: Design config format**

Use TOML (Python 3.11+ has `tomllib` built-in). Config lives at `~/.config/NiimPrintX/config.toml`:

```toml
# Custom label sizes — merged with built-in defaults
[devices.b1.size]
"70mm x 50mm" = [70, 50]
"30mm x 20mm" = [30, 20]

[devices.custom_printer]
density = 3
print_dpi = 203
rotation = -90

[devices.custom_printer.size]
"50mm x 30mm" = [50, 30]
```

- [ ] **Step 2: Create UserConfig.py**

```python
import os
import tomllib
from appdirs import user_config_dir
from loguru import logger

CONFIG_DIR = user_config_dir("NiimPrintX")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.toml")

def load_user_config():
    """Load user config, return empty dict if not found."""
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        logger.warning(f"Failed to load user config: {e}")
        return {}

def merge_label_sizes(builtin_sizes, user_config):
    """Merge user device configs into built-in label sizes."""
    user_devices = user_config.get("devices", {})
    for device_name, device_conf in user_devices.items():
        if device_name in builtin_sizes:
            # Merge sizes into existing device
            if "size" in device_conf:
                for label, dims in device_conf["size"].items():
                    builtin_sizes[device_name]["size"][label] = tuple(dims)
        else:
            # Add entirely new device
            builtin_sizes[device_name] = {
                "size": {k: tuple(v) for k, v in device_conf.get("size", {}).items()},
                "density": device_conf.get("density", 3),
                "print_dpi": device_conf.get("print_dpi", 203),
                "rotation": device_conf.get("rotation", -90),
            }
    return builtin_sizes
```

- [ ] **Step 3: Integrate into AppConfig.__init__()**

At the end of `__init__()` in AppConfig.py, after the built-in `label_sizes` dict is defined:

```python
from NiimPrintX.ui.UserConfig import load_user_config, merge_label_sizes
user_config = load_user_config()
self.label_sizes = merge_label_sizes(self.label_sizes, user_config)
```

- [ ] **Step 4: Commit**

```bash
git add NiimPrintX/ui/UserConfig.py NiimPrintX/ui/AppConfig.py
git commit -m "feat: user config file for custom label sizes

Reads ~/.config/NiimPrintX/config.toml to add or override label sizes.
Users can define custom devices or add sizes to existing ones.

Fixes #7"
```

---

### Task 5: Modern Linux theming

**Fixes:** #14
**Impact:** Medium — visual polish for Linux users
**Files:**
- Modify: `NiimPrintX/ui/main.py` (theme initialization)
- Modify: `pyproject.toml` (optional dependency)

- [ ] **Step 1: Research theme options**

Best options for Tkinter on Linux:
- **sv-ttk** (Sun Valley theme) — modern Windows 11 look, pure Python, pip installable
- **ttkthemes** — multiple themes but mixed results (as #14 reporter noted)
- **customtkinter** — complete Tkinter replacement, too invasive

sv-ttk is the best fit: small, modern, drop-in.

- [ ] **Step 2: Add sv-ttk as optional dependency**

In pyproject.toml:
```toml
sv-ttk = {version = "^2.6", optional = true}
```

- [ ] **Step 3: Apply theme in main.py**

In `LabelPrinterApp.load_resources()`, after the existing theme logic:

```python
if self.app_config.os_system == "Darwin":
    style = ttk.Style(self)
    style.theme_use('clam')
elif self.app_config.os_system == "Windows":
    style = ttk.Style(self)
    style.theme_use('xpnative')
else:
    try:
        import sv_ttk
        sv_ttk.set_theme("light")
    except ImportError:
        style = ttk.Style(self)
        style.theme_use('clam')
```

- [ ] **Step 4: Commit**

```bash
git add NiimPrintX/ui/main.py pyproject.toml
git commit -m "feat: modern Linux theme with sv-ttk

Uses Sun Valley theme on Linux for a modern look. Falls back to
clam theme if sv-ttk is not installed. Optional dependency.

Addresses #14"
```

---

### Task 6: Test suite foundation

**Fixes:** TD6
**Impact:** Important — enables safe refactoring and CI
**Files:**
- Create: `tests/conftest.py` (fixtures)
- Create: `tests/test_packet.py` (packet encode/decode)
- Create: `tests/test_appconfig.py` (device config validation)
- Create: `tests/test_image_encoding.py` (image encoding)
- Modify: `pyproject.toml` (add pytest)

- [ ] **Step 1: Add pytest to dev dependencies**

```toml
[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
```

- [ ] **Step 2: Create conftest.py with fixtures**

```python
import pytest
from PIL import Image

@pytest.fixture
def small_image():
    """Create a small test image for printing tests."""
    return Image.new("1", (240, 100), color=0)

@pytest.fixture
def wide_image():
    """Create a wider test image for B-series printers."""
    return Image.new("1", (384, 200), color=0)
```

- [ ] **Step 3: Test NiimbotPacket encode/decode roundtrip**

```python
from NiimPrintX.nimmy.packet import NiimbotPacket

def test_packet_roundtrip():
    packet = NiimbotPacket(0x01, b"\x02\x03")
    raw = packet.to_bytes()
    parsed = NiimbotPacket.from_bytes(raw)
    assert parsed.type == 0x01
    assert parsed.data == b"\x02\x03"

def test_packet_header_footer():
    packet = NiimbotPacket(0x40, b"\x01")
    raw = packet.to_bytes()
    assert raw[:2] == b"\x55\x55"
    assert raw[-2:] == b"\xaa\xaa"

def test_packet_checksum():
    packet = NiimbotPacket(0x01, b"\x00")
    raw = packet.to_bytes()
    # XOR of type, length, data bytes
    expected_check = 0x01 ^ 0x01 ^ 0x00
    assert raw[-3] == expected_check
```

- [ ] **Step 4: Test AppConfig device consistency**

```python
from NiimPrintX.ui.AppConfig import AppConfig

def test_all_devices_have_required_keys():
    config = AppConfig()
    required = {"size", "density", "print_dpi"}
    for device, conf in config.label_sizes.items():
        missing = required - set(conf.keys())
        assert not missing, f"{device} missing keys: {missing}"

def test_all_devices_have_at_least_one_size():
    config = AppConfig()
    for device, conf in config.label_sizes.items():
        assert len(conf["size"]) > 0, f"{device} has no label sizes"

def test_density_in_valid_range():
    config = AppConfig()
    for device, conf in config.label_sizes.items():
        assert 1 <= conf["density"] <= 5, f"{device} density out of range"

def test_print_dpi_is_known_value():
    config = AppConfig()
    for device, conf in config.label_sizes.items():
        assert conf["print_dpi"] in (203, 300), f"{device} has unexpected DPI {conf['print_dpi']}"
```

- [ ] **Step 5: Test image encoding**

```python
import pytest
from PIL import Image
from NiimPrintX.nimmy.printer import PrinterClient

def test_encode_image_produces_packets(small_image):
    """Image encoding should produce one packet per row."""
    client = PrinterClient.__new__(PrinterClient)
    packets = list(client._encode_image(small_image))
    assert len(packets) == small_image.height

def test_encode_image_with_offset(small_image):
    """Vertical offset should produce additional blank packets."""
    client = PrinterClient.__new__(PrinterClient)
    packets_no_offset = list(client._encode_image(small_image, vertical_offset=0))
    packets_with_offset = list(client._encode_image(small_image, vertical_offset=10))
    assert len(packets_with_offset) == len(packets_no_offset) + 10
```

- [ ] **Step 6: Commit**

```bash
git add tests/ pyproject.toml
git commit -m "test: add pytest foundation with packet, config, and encoding tests

Establishes test suite with pytest + pytest-asyncio.
Tests cover: packet encode/decode roundtrip, AppConfig device
consistency, and image encoding output.

Addresses TD6"
```

---

### Task 7: Research — macOS CoreBluetooth event loop (no implementation)

**Issue:** #18 — CLI throws "Event loop is closed" on macOS Big Sur
**Status:** Research only — needs macOS hardware to reproduce

- [ ] **Step 1: Document the root cause**

The crash is in bleak's CoreBluetooth backend. When the event loop closes, a pending `centralManager_didDisconnectPeripheral_error_` callback fires after the loop is gone. This is a known bleak lifecycle issue.

Possible fixes:
1. Upgrade bleak (we're now on 0.22.3 — check if this is fixed)
2. Use `atexit` to cleanly disconnect before loop closes
3. Suppress the ObjectiveC exception (fragile)

- [ ] **Step 2: Add to KNOWN_ISSUES.md**

Document as a known issue with the bleak upgrade note. If the user has macOS, they can test whether 0.22.3 resolves it.

---

## Upstream Issues to Close (no code needed)

| # | Action |
|---|--------|
| #44 | Comment: "Fork is actively maintained at Avicennasis/NiimPrintX" |
| #27 | Comment: "The CLI supports printing from any tool that can invoke a command. See README for CLI usage." |
| #35 | Comment: "See updated README for Bluetooth setup instructions" (after we update docs) |
| #25 | Comment: "D101 is now supported in CLI and GUI. Please try the latest release." |
| #10 | Close: "Phomemo uses a different protocol — out of scope for this project" |

---

## Summary

| Task | Fixes | Effort | Priority |
|------|-------|--------|----------|
| 1. Harden send_command | #3, TD1, TD9 | 1-2 hrs | Critical |
| 2. Configurable rotation | #24, #38 | 1 hr | Important |
| 3. Open .niim from CLI | #17 | 1 hr | Medium |
| 4. User config file | #7 | 2 hrs | Medium |
| 5. Linux theming | #14 | 1 hr | Low |
| 6. Test suite | TD6 | 3-4 hrs | Important |
| 7. macOS research | #18 | Research | Low |

**After all tasks: 24 of 31 upstream issues addressed or closeable.**
