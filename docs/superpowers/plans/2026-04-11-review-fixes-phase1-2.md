# NiimPrintX Review Fixes — Phase 1 & 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 13 critical-protocol and high-impact bugs from the Round 4 code review (findings #1-#4, #6-#9, #17-#18, #25-#27, #29, #47-#48, #53).

**Architecture:** Surgical fixes to existing files — no new modules. Protocol fixes in `nimmy/` layer are tested with pytest. UI fixes in `ui/` layer verified by inspection (Tkinter mocking is fragile and not worth the coupling). Each task produces one focused commit.

**Tech Stack:** Python 3.12+, asyncio, bleak (BLE), Tkinter, Pillow, Wand/ImageMagick, pytest

---

## File Map

| Task | Files Modified | Files Tested |
|------|---------------|-------------|
| 1 | `NiimPrintX/nimmy/printer.py` | `tests/test_packet.py`, `tests/test_printer.py` (new) |
| 2 | `NiimPrintX/nimmy/printer.py` | `tests/test_printer.py` |
| 3 | `NiimPrintX/nimmy/printer.py` | `tests/test_printer.py` |
| 4 | `NiimPrintX/nimmy/bluetooth.py` | — |
| 5 | `NiimPrintX/nimmy/packet.py` | `tests/test_packet.py` |
| 6 | `NiimPrintX/ui/main.py` | — |
| 7 | `NiimPrintX/ui/widget/PrintOption.py` | — |
| 8 | `NiimPrintX/ui/widget/TextOperation.py` | — |
| 9 | `NiimPrintX/ui/__main__.py` | — |
| 10 | `NiimPrintX/ui/widget/FileMenu.py` | — |
| 11 | `NiimPrintX/ui/widget/TabbedIconGrid.py` | — |

---

### Task 1: Fix send_command notification race + ValueError catch

**Findings:** #1 (stale notification event), #3 (ValueError uncaught)

**Files:**
- Modify: `NiimPrintX/nimmy/printer.py:86-113`
- Create: `tests/test_printer.py`

- [ ] **Step 1: Write tests for send_command error handling**

Create `tests/test_printer.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from NiimPrintX.nimmy.printer import PrinterClient, RequestCodeEnum
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.exception import PrinterException, BLEException


def _make_client():
    """Create a PrinterClient with a mocked device, bypassing BLE."""
    device = MagicMock()
    device.name = "test-printer"
    device.address = "AA:BB:CC:DD:EE:FF"
    client = PrinterClient.__new__(PrinterClient)
    client.device = device
    client.transport = MagicMock()
    client.transport.client = MagicMock()
    client.transport.client.is_connected = True
    client.transport.start_notification = AsyncMock()
    client.transport.stop_notification = AsyncMock()
    client.transport.write = AsyncMock()
    client.char_uuid = "test-uuid"
    client.notification_event = asyncio.Event()
    client.notification_data = None
    client._command_lock = asyncio.Lock()
    client._print_lock = asyncio.Lock()
    return client


@pytest.mark.asyncio
async def test_send_command_clears_event_before_wait():
    """notification_event must be cleared before waiting, not just after."""
    client = _make_client()
    # Pre-set the event to simulate a stale notification
    client.notification_event.set()
    client.notification_data = b"\x55\x55\x40\x01\xFF\xBE\xAA\xAA"  # stale data

    # Build a valid response packet for GET_INFO
    response_pkt = NiimbotPacket(0x40, b"\x01")
    fresh_bytes = response_pkt.to_bytes()

    async def fake_write(data, char_uuid):
        # Simulate printer responding after write
        client.notification_data = fresh_bytes
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")
    assert result.data == b"\x01"


@pytest.mark.asyncio
async def test_send_command_catches_valueerror_from_malformed_packet():
    """ValueError from from_bytes must be wrapped as PrinterException."""
    client = _make_client()

    async def fake_write(data, char_uuid):
        # Simulate a corrupted response (bad header)
        client.notification_data = b"\xDE\xAD\x40\x01\x01\x40\xAA\xAA"
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    with pytest.raises(PrinterException, match="Malformed"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")


@pytest.mark.asyncio
async def test_send_command_timeout_raises_printer_exception():
    """Timeout must be wrapped as PrinterException."""
    client = _make_client()
    # Never set the event — will timeout
    with pytest.raises(PrinterException, match="timed out"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01", timeout=0.1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/test_printer.py -v`
Expected: `test_send_command_clears_event_before_wait` FAILS (stale event returns immediately with wrong data), `test_send_command_catches_valueerror_from_malformed_packet` FAILS (ValueError not caught)

- [ ] **Step 3: Fix send_command in printer.py**

In `NiimPrintX/nimmy/printer.py`, modify `send_command`:

```python
    async def send_command(self, request_code, data, timeout=10):
        async with self._command_lock:
            notifying = False
            try:
                if not self.transport.client or not self.transport.client.is_connected:
                    await self.connect()
                # Clear stale state BEFORE arming notifications
                self.notification_event.clear()
                self.notification_data = None
                packet = NiimbotPacket(request_code, data)
                await self.transport.start_notification(self.char_uuid, self.notification_handler)
                notifying = True
                await self.transport.write(packet.to_bytes(), self.char_uuid)
                logger.debug(f"Printer command sent - {RequestCodeEnum(request_code).name}:{request_code} - {[b for b in data]}")
                await asyncio.wait_for(self.notification_event.wait(), timeout)
                response = NiimbotPacket.from_bytes(self.notification_data)
                logger.debug(f"Printer response received - {[b for b in response.data]} - {len(response.data)} bytes")
                return response
            except asyncio.TimeoutError:
                logger.error(f"Timeout occurred for request {RequestCodeEnum(request_code).name}")
                raise PrinterException(f"Printer timed out on {RequestCodeEnum(request_code).name}")
            except BLEException as e:
                logger.error(f"An error occurred: {e}")
                raise PrinterException(f"BLE error during {RequestCodeEnum(request_code).name}: {e}")
            except ValueError as e:
                logger.error(f"Malformed response for {RequestCodeEnum(request_code).name}: {e}")
                raise PrinterException(f"Malformed printer response: {e}")
            finally:
                if notifying:
                    try:
                        await self.transport.stop_notification(self.char_uuid)
                    except Exception as e:
                        logger.warning(f"stop_notify failed: {e}")
                self.notification_event.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/test_printer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/nimmy/printer.py tests/test_printer.py && git commit -m "$(cat <<'EOF'
fix: clear notification event before wait + catch ValueError in send_command

Fixes two critical BLE protocol bugs:
1. Stale notification from previous command could cause send_command to
   return wrong data immediately. Now clears event+data before arming.
2. ValueError from malformed packets (bad header/checksum) was uncaught,
   propagating raw through the call stack. Now wrapped as PrinterException.
Also logs stop_notify failures instead of silently swallowing them.
EOF
)"
```

---

### Task 2: Protect write_raw with print-level lock

**Finding:** #4 (heartbeat interleaves with image data)

**Files:**
- Modify: `NiimPrintX/nimmy/printer.py:43-51,115-122,140-191`

- [ ] **Step 1: Write test for print lock preventing heartbeat interleave**

Add to `tests/test_printer.py`:

```python
@pytest.mark.asyncio
async def test_print_lock_prevents_concurrent_access():
    """_print_lock must prevent heartbeat during print job."""
    client = _make_client()
    # Acquire the print lock
    await client._print_lock.acquire()
    # Verify the lock is held (heartbeat would block)
    assert client._print_lock.locked()
    client._print_lock.release()
    assert not client._print_lock.locked()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/test_printer.py::test_print_lock_prevents_concurrent_access -v`
Expected: FAIL — `_print_lock` attribute doesn't exist

- [ ] **Step 3: Add _print_lock and protect print methods + write_raw**

In `NiimPrintX/nimmy/printer.py`, modify `__init__`:

```python
    def __init__(self, device):
        self.char_uuid = None
        self.device = device
        self.transport = BLETransport()
        self.notification_event = asyncio.Event()
        self.notification_data = None
        self._command_lock = asyncio.Lock()
        self._print_lock = asyncio.Lock()
```

Modify `write_raw` to acquire the print lock:

```python
    async def write_raw(self, data):
        async with self._print_lock:
            try:
                if not self.transport.client or not self.transport.client.is_connected:
                    await self.connect()
                await self.transport.write(data.to_bytes(), self.char_uuid)
            except BLEException as e:
                logger.error(f"Write error: {e}")
                raise PrinterException(f"BLE write failed: {e}")
```

Modify `print_image` to hold the print lock for the entire print sequence:

```python
    async def print_image(self, image: Image, density: int = 3, quantity: int = 1, vertical_offset=0,
                          horizontal_offset=0):
        async with self._print_lock:
            try:
                await self.set_label_density(density)
                await self.set_label_type(1)
                await self.start_print()
                await self.start_page_print()
                await self.set_dimension(image.height, image.width)
                await self.set_quantity(quantity)

                for pkt in self._encode_image(image, vertical_offset, horizontal_offset):
                    try:
                        if not self.transport.client or not self.transport.client.is_connected:
                            await self.connect()
                        await self.transport.write(pkt.to_bytes(), self.char_uuid)
                    except BLEException as e:
                        logger.error(f"Write error: {e}")
                        raise PrinterException(f"BLE write failed: {e}")
                    await asyncio.sleep(0.01)

                while not await self.end_page_print():
                    await asyncio.sleep(0.05)

                max_status_checks = 600
                status = {"page": 0, "progress1": 0, "progress2": 0}
                for _ in range(max_status_checks):
                    status = await self.get_print_status()
                    if status['page'] == quantity:
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise PrinterException(f"Print status timeout: page {status['page']}/{quantity}")

                await self.end_print()
            except PrinterException:
                logger.error("Print job failed")
                raise
```

Note: `print_image` now writes packets inline instead of calling `write_raw`, because both would try to acquire `_print_lock`. The `write_raw` method keeps the lock for external callers (like standalone raw writes) but `print_image` owns the lock for the full sequence. Same pattern for `print_imageV2`:

```python
    async def print_imageV2(self, image: Image, density: int = 3, quantity: int = 1, vertical_offset=0,
                            horizontal_offset=0):
        async with self._print_lock:
            try:
                await self.set_label_density(density)
                await self.set_label_type(1)
                await self.start_printV2(quantity=quantity)
                await self.start_page_print()
                await self.set_dimensionV2(image.height, image.width, quantity)

                for pkt in self._encode_image(image, vertical_offset, horizontal_offset):
                    logger.debug(f"Sending packet: {pkt}")
                    try:
                        if not self.transport.client or not self.transport.client.is_connected:
                            await self.connect()
                        await self.transport.write(pkt.to_bytes(), self.char_uuid)
                    except BLEException as e:
                        logger.error(f"Write error: {e}")
                        raise PrinterException(f"BLE write failed: {e}")
                    await asyncio.sleep(0.01)

                await self.end_page_print()
                await asyncio.sleep(2)
            except PrinterException:
                logger.error("B1 print job failed")
                raise
```

Also initialize `status` before the for-loop in `print_image` (finding #14 fix included above).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/test_printer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/nimmy/printer.py tests/test_printer.py && git commit -m "$(cat <<'EOF'
fix: add print-level lock to prevent heartbeat interleaving with image data

Adds _print_lock that is held for the entire print sequence (setup →
encode → status poll → end). write_raw also acquires this lock for
standalone use. print_image/V2 write packets inline to avoid double-
locking. Prevents heartbeat BLE commands from corrupting the protocol
stream mid-print. Also initializes status before the for-else loop
to prevent UnboundLocalError on timeout.
EOF
)"
```

---

### Task 3: Fix heartbeat case 10 + set_dimension naming

**Findings:** #7 (rfid_read_state duplicates power_level), #6 (parameter naming)

**Files:**
- Modify: `NiimPrintX/nimmy/printer.py:267-300,341-352`

- [ ] **Step 1: Write test for heartbeat case 10**

Add to `tests/test_printer.py`:

```python
@pytest.mark.asyncio
async def test_heartbeat_case_10_no_rfid():
    """10-byte heartbeat should not set rfid_read_state (only 2 useful fields)."""
    client = _make_client()
    # Build a 10-byte heartbeat response
    hb_data = bytes(10)  # 10 zero bytes
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, hb_data)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result["closing_state"] == hb_data[8]
    assert result["power_level"] == hb_data[9]
    # rfid_read_state should NOT be set for 10-byte packets
    assert result["rfid_read_state"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/test_printer.py::test_heartbeat_case_10_no_rfid -v`
Expected: FAIL — `rfid_read_state` is `0` (wrongly assigned from `packet.data[9]`) instead of `None`

- [ ] **Step 3: Fix heartbeat case 10 and rename set_dimension params**

In `NiimPrintX/nimmy/printer.py`, fix the `case 10` block:

```python
            case 10:
                closing_state = packet.data[8]
                power_level = packet.data[9]
```

(Remove the `rfid_read_state = packet.data[9]` line — it was a copy-paste bug.)

Rename `set_dimension` and `set_dimensionV2` parameters for clarity:

```python
    async def set_dimension(self, height, width):
        packet = await self.send_command(
            RequestCodeEnum.SET_DIMENSION, struct.pack(">HH", height, width)
        )
        return bool(packet.data[0])

    async def set_dimensionV2(self, height, width, copies):
        logger.debug(f"Setting dimension: {height}x{width}")
        packet = await self.send_command(
            RequestCodeEnum.SET_DIMENSION, struct.pack(">HHH", height, width, copies)
        )
        return bool(packet.data[0])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/test_printer.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/nimmy/printer.py tests/test_printer.py && git commit -m "$(cat <<'EOF'
fix: heartbeat case 10 rfid_read_state bug + set_dimension param naming

1. Removed erroneous rfid_read_state = packet.data[9] in heartbeat
   case 10 — it duplicated power_level. rfid_read_state stays None
   for 10-byte packets (no RFID field at that length).
2. Renamed set_dimension(w, h) → set_dimension(height, width) to
   match call site semantics (called with image.height, image.width).
EOF
)"
```

---

### Task 4: Fix BLETransport connect() return values

**Findings:** #2 (context manager always raises), #8 (already-connected returns False)

**Files:**
- Modify: `NiimPrintX/nimmy/bluetooth.py:37-58`

- [ ] **Step 1: Fix __aenter__ and connect()**

In `NiimPrintX/nimmy/bluetooth.py`:

Replace `__aenter__`:

```python
    async def __aenter__(self):
        if self.address:
            self.client = BleakClient(self.address)
            await self.client.connect()  # raises BleakError on failure
            logger.info(f"Connected to {self.address}")
        return self
```

Replace `connect`:

```python
    async def connect(self, address):
        if self.client is None:
            self.client = BleakClient(address)
        if not self.client.is_connected:
            await self.client.connect()  # raises BleakError on failure
            return True
        return True  # already connected
```

Also remove the dead `import asyncio` on line 1.

- [ ] **Step 2: Run full test suite**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/nimmy/bluetooth.py && git commit -m "$(cat <<'EOF'
fix: BLETransport.connect() return values + remove dead asyncio import

1. __aenter__: BleakClient.connect() returns None in bleak >= 0.14,
   not bool. Removed the if-check — connect() raises on failure.
2. connect(): Return True when already connected (was False, which
   callers interpreted as failure).
3. Removed unused import asyncio.
EOF
)"
```

---

### Task 5: Add packet.py length validation in from_bytes

**Finding:** #9 (trusts device-reported length field)

**Files:**
- Modify: `NiimPrintX/nimmy/packet.py:10-20`
- Modify: `tests/test_packet.py`

- [ ] **Step 1: Write tests for packet error paths**

Add to `tests/test_packet.py`:

```python
def test_packet_from_bytes_too_short():
    """Packets shorter than 7 bytes must raise ValueError."""
    with pytest.raises(ValueError, match="too short"):
        NiimbotPacket.from_bytes(b"\x55\x55\x40")


def test_packet_from_bytes_bad_header():
    """Packets with wrong header must raise ValueError."""
    with pytest.raises(ValueError, match="Invalid packet header"):
        NiimbotPacket.from_bytes(b"\xDE\xAD\x40\x01\x01\x40\xAA\xAA")


def test_packet_from_bytes_bad_checksum():
    """Packets with wrong checksum must raise ValueError."""
    pkt = NiimbotPacket(0x01, b"\x02\x03")
    raw = bytearray(pkt.to_bytes())
    raw[-3] ^= 0xFF  # corrupt checksum
    with pytest.raises(ValueError, match="Checksum mismatch"):
        NiimbotPacket.from_bytes(bytes(raw))


def test_packet_from_bytes_length_exceeds_buffer():
    """Length field claiming more data than buffer holds must raise ValueError."""
    # Craft a packet where length field says 100 but only 1 byte of data follows
    # header(2) + type(1) + len(1) + data(1) + checksum(1) + footer(2) = 8 bytes
    raw = b"\x55\x55\x40\x64\x01\x25\xAA\xAA"  # len=0x64=100, but only 1 data byte
    with pytest.raises(ValueError, match="exceeds"):
        NiimbotPacket.from_bytes(raw)


def test_packet_to_bytes_too_long():
    """Data longer than 255 bytes must raise ValueError."""
    with pytest.raises(ValueError, match="too long"):
        NiimbotPacket(0x01, bytes(256)).to_bytes()
```

Add `import pytest` at the top of the file if not already present.

- [ ] **Step 2: Run tests to verify new ones fail**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/test_packet.py -v`
Expected: `test_packet_from_bytes_length_exceeds_buffer` FAILS (no length check). Others should PASS (guards already exist).

- [ ] **Step 3: Add length validation to from_bytes**

In `NiimPrintX/nimmy/packet.py`, after extracting `len_`, add:

```python
    @classmethod
    def from_bytes(cls, pkt):
        if pkt is None or len(pkt) < 7:
            raise ValueError(f"Packet too short: {len(pkt) if pkt else 0} bytes")
        if pkt[:2] != b"\x55\x55":
            raise ValueError(f"Invalid packet header: {pkt[:2].hex()}")
        if pkt[-2:] != b"\xaa\xaa":
            raise ValueError(f"Invalid packet footer: {pkt[-2:].hex()}")
        type_ = pkt[2]
        len_ = pkt[3]
        if 4 + len_ + 3 > len(pkt):
            raise ValueError(f"Packet length field {len_} exceeds actual data: buffer is {len(pkt)} bytes")
        data = pkt[4 : 4 + len_]

        checksum = type_ ^ len_
        for i in data:
            checksum ^= i
        if checksum != pkt[-3]:
            raise ValueError(f"Checksum mismatch: expected {checksum:#x}, got {pkt[-3]:#x}")

        return cls(type_, data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/test_packet.py -v`
Expected: All tests PASS (9 total — 4 existing + 5 new)

- [ ] **Step 5: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/nimmy/packet.py tests/test_packet.py && git commit -m "$(cat <<'EOF'
fix: validate packet length field against actual buffer in from_bytes

Adds a bounds check after extracting the length field to reject packets
where len_ claims more data than the buffer contains. Previously a
truncated payload could silently pass checksum validation by coincidence.
Also adds tests for all from_bytes error paths (short, bad header, bad
checksum, length overflow) and to_bytes overflow.
EOF
)"
```

---

### Task 6: Stop asyncio loop on window close

**Finding:** #17 (heartbeat continues after destroy)

**Files:**
- Modify: `NiimPrintX/ui/main.py:100-102`
- Modify: `NiimPrintX/ui/main.py:53` (remove duplicate deiconify — finding #30)

- [ ] **Step 1: Fix on_close to stop asyncio loop**

In `NiimPrintX/ui/main.py`, replace `on_close`:

```python
    def on_close(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            # Stop the asyncio event loop so heartbeat and pending tasks end cleanly
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            self.destroy()
```

Remove the duplicate `show_main_window` scheduling from `load_resources` — `__main__.py` already handles this at line 50:

```python
    def load_resources(self):
        self.async_loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_asyncio_loop, daemon=True).start()

        self.app_config = AppConfig()
        if self.app_config.os_system == "Darwin":
            style = ttk.Style(self)
            style.theme_use('aqua')
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

        self.create_widgets()
        self.create_menu()
        self.printer = None
```

Remove the `show_main_window` method entirely (lines 55-57).

Also remove the dead code at the bottom:

```python
if __name__ == "__main__":
    try:
        app = LabelPrinterApp()
        app.load_resources()
        app.mainloop()
    except Exception as e:
        raise e
```

Replace with just:

```python
if __name__ == "__main__":
    app = LabelPrinterApp()
    app.load_resources()
    app.mainloop()
```

- [ ] **Step 2: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/ui/main.py && git commit -m "$(cat <<'EOF'
fix: stop asyncio loop on window close + remove duplicate deiconify

on_close now calls async_loop.stop() before destroy() so the heartbeat
coroutine and any pending BLE operations end cleanly instead of firing
root.after() on a destroyed Tk interpreter. Also removes duplicate
show_main_window scheduling (already done in __main__.py) and the
dead if __name__ block with its pointless except-reraise.
EOF
)"
```

---

### Task 7: Guard _print_handler against destroyed widgets + fix lambda captures

**Findings:** #18 (_print_handler TclError), #19 (lambda captures)

**Files:**
- Modify: `NiimPrintX/ui/widget/PrintOption.py:27-34,283-293`

- [ ] **Step 1: Fix lambda captures in schedule_heartbeat**

In `NiimPrintX/ui/widget/PrintOption.py`, fix the lambda captures:

```python
    async def schedule_heartbeat(self):
        while True:
            if self.print_op.printer and not self.config.print_job:
                state, hb = await self.print_op.heartbeat()
                self.root.after(0, lambda s=state, h=hb: self.update_status(s, h))
            elif not self.config.print_job:
                self.root.after(0, lambda: self.update_status(False))
            await asyncio.sleep(5)
```

- [ ] **Step 2: Guard _print_handler against destroyed widgets**

Replace `_print_handler`:

```python
    def _print_handler(self, future):
        try:
            result = future.result()
        except Exception:
            result = False
        def _update():
            self.config.print_job = False
            if result:
                try:
                    self.root.status_bar.update_status(result)
                except tk.TclError:
                    pass
            try:
                self.print_button.config(state=tk.NORMAL)
            except tk.TclError:
                pass  # popup was closed before print finished
        self.root.after(0, _update)
```

Key change: `print_job = False` is first (unconditional), and widget access is guarded with `try/except TclError`.

- [ ] **Step 3: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/ui/widget/PrintOption.py && git commit -m "$(cat <<'EOF'
fix: guard _print_handler against destroyed widgets + fix lambda captures

1. _print_handler: print_job=False is now unconditional (before widget
   access). Widget updates wrapped in try/except TclError so closing
   the popup before print finishes doesn't permanently disable heartbeats.
2. schedule_heartbeat: lambda captures state/hb by value (s=state, h=hb)
   instead of by reference, preventing stale data delivery.
EOF
)"
```

---

### Task 8: Fix text rendering DPI + WandImage leak

**Findings:** #47 (draw.resolution no-op), #48 (WandImage leak)

**Files:**
- Modify: `NiimPrintX/ui/widget/TextOperation.py:13-43`

- [ ] **Step 1: Fix create_text_image**

Replace the `create_text_image` method:

```python
    def create_text_image(self, font_props, text):
        with WandDrawing() as draw:
            draw.font_family = font_props["family"]
            draw.font_size = font_props["size"]
            if font_props["slant"] == 'italic':
                draw.font_style = 'italic'
            if font_props["weight"] == 'bold':
                draw.font_weight = 700
            if font_props["underline"]:
                draw.text_decoration = 'underline'
            draw.text_kerning = font_props["kerning"]
            draw.fill_color = Color('black')
            # Get font metrics using a temporary probe image (context-managed)
            with WandImage(width=1, height=1) as probe:
                metrics = draw.get_font_metrics(probe, text, multiline=True)
            text_width = int(metrics.text_width) + 5
            text_height = int(metrics.text_height) + int(abs(metrics.descender)) + 2

            with WandImage(width=text_width, height=text_height, background=Color('transparent')) as img:
                # Set resolution on the IMAGE, not the Drawing (Drawing.resolution is a no-op)
                img.resolution = (300, 300)
                draw.text(x=2, y=int(metrics.ascender), body=text)
                draw(img)

                img.format = 'png'
                img.alpha_channel = 'activate'
                img_blob = img.make_blob('png32')
                tk_image = tk.PhotoImage(data=img_blob)
                return tk_image
```

Changes:
1. `WandImage(width=1, height=1)` is now context-managed (`with ... as probe`) — no more native handle leak
2. `draw.resolution` removed — `img.resolution` set on the image instead
3. `text_height` now accounts for descender depth to prevent multiline clipping

- [ ] **Step 2: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/ui/widget/TextOperation.py && git commit -m "$(cat <<'EOF'
fix: text renders at correct DPI + fix WandImage memory leak

1. Moved resolution setting from Drawing object (no-op) to Image object
   so text actually renders at 300 DPI instead of defaulting to 72 DPI.
2. Wrapped metrics probe WandImage in context manager to prevent native
   ImageMagick handle leak on every text render/resize.
3. Added descender depth to text_height calculation to prevent clipping
   on multiline text with deep descenders.
EOF
)"
```

---

### Task 9: Fix env dict not applied to os.environ

**Finding:** #53 (ImageMagick env setup broken in PyInstaller builds)

**Files:**
- Modify: `NiimPrintX/ui/__main__.py:9-25`

- [ ] **Step 1: Fix load_libraries to write directly to os.environ**

Replace `load_libraries`:

```python
def load_libraries():
    if hasattr(sys, '_MEIPASS'):
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
        magick_path = os.path.join(base_path, 'imagemagick')

        if platform.system() == "Linux" or platform.system() == "Darwin":
            os.environ['MAGICK_HOME'] = magick_path
            os.environ['PATH'] = os.path.join(magick_path, 'bin') + os.pathsep + os.environ.get('PATH', '')
            os.environ['LD_LIBRARY_PATH'] = os.path.join(magick_path, 'lib') + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
            os.environ['MAGICK_CONFIGURE_PATH'] = os.path.join(magick_path, 'etc', 'ImageMagick-7')
            os.environ['DYLD_LIBRARY_PATH'] = magick_path + ':' + os.environ.get('DYLD_LIBRARY_PATH', '')
        elif platform.system() == "Windows":
            os.environ['MAGICK_HOME'] = magick_path
            os.environ['PATH'] = magick_path + os.pathsep + os.environ.get('PATH', '')
```

The intermediate `env = os.environ.copy()` dict is removed — all mutations go directly to `os.environ`.

- [ ] **Step 2: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/ui/__main__.py && git commit -m "$(cat <<'EOF'
fix: write ImageMagick env vars directly to os.environ

load_libraries() was mutating a local copy of os.environ that was
never written back. MAGICK_HOME, PATH, LD_LIBRARY_PATH, and
MAGICK_CONFIGURE_PATH were silently lost, breaking ImageMagick
discovery in PyInstaller builds on Linux and Windows. Only
DYLD_LIBRARY_PATH worked because it was written directly.
EOF
)"
```

---

### Task 10: Fix tk.PhotoImage vs ImageTk.PhotoImage save crash

**Finding:** #29 (ImageTk.getimage() crashes for UI-created text)

**Files:**
- Modify: `NiimPrintX/ui/widget/FileMenu.py:36-50`

- [ ] **Step 1: Fix save_to_file to handle both PhotoImage types**

In `NiimPrintX/ui/widget/FileMenu.py`, replace the text serialization block in `save_to_file` (lines 36-50):

```python
        if self.config.text_items:
            for text_id, properties in self.config.text_items.items():
                font_image = properties["font_image"]
                # Handle both tk.PhotoImage (from Wand) and ImageTk.PhotoImage (from load)
                if isinstance(font_image, ImageTk.PhotoImage):
                    pil_image = ImageTk.getimage(font_image)
                else:
                    # tk.PhotoImage — convert via PPM data
                    ppm_data = font_image.data()
                    if isinstance(ppm_data, str):
                        ppm_data = ppm_data.encode('latin-1')
                    pil_image = Image.open(io.BytesIO(ppm_data))
                with io.BytesIO() as buffer:
                    pil_image.save(buffer, format="PNG")
                    buffer.seek(0)
                    font_img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

                item_data = {
                    "content": properties["content"],
                    "coords": self.config.canvas.coords(text_id),
                    "font_props": properties['font_props'],
                    "font_image": font_img_str
                }
                data['text'][str(text_id)] = item_data
```

Also wrap the entire `save_to_file` file write in error handling (finding #73):

Replace lines 72-76:

```python
        file_path = filedialog.asksaveasfilename(defaultextension=".niim",
                                                 filetypes=[("NIIM files", "*.niim")])
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except OSError as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")
```

- [ ] **Step 2: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/ui/widget/FileMenu.py && git commit -m "$(cat <<'EOF'
fix: handle both tk.PhotoImage and ImageTk.PhotoImage in save_to_file

TextOperation.create_text_image() produces tk.PhotoImage (from Wand
blob), but load_text() produces ImageTk.PhotoImage (from PIL).
ImageTk.getimage() only works on ImageTk.PhotoImage, so saving after
adding text via the UI crashed. Now detects the type and converts
tk.PhotoImage via its PPM data export. Also adds error handling for
file write failures (PermissionError, disk full).
EOF
)"
```

---

### Task 11: Fix TabbedIconGrid — anchor, lazy loading, bind loop

**Findings:** #25 (anchor clips icons), #26 (PIL lazy loading), #27 (bind inside loop)

**Files:**
- Modify: `NiimPrintX/ui/widget/TabbedIconGrid.py:24-100`

- [ ] **Step 1: Fix all three issues**

In `NiimPrintX/ui/widget/TabbedIconGrid.py`:

Fix `create_tabs` — move bind outside loop:

```python
    def create_tabs(self):
        """Create a tab for each subfolder."""
        for subfolder in sorted(os.listdir(self.base_folder)):
            subfolder_path = os.path.join(self.base_folder, subfolder)
            if os.path.isdir(subfolder_path):
                tab_frame = tk.Frame(self.notebook)
                self.notebook.add(tab_frame, text=subfolder.capitalize())
        self.notebook.bind("<<NotebookTabChanged>>", self.load_tab_icons)
```

Fix `create_icon_grid` — change anchor to `"nw"`:

```python
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
```

Fix `load_icons` — force `img.load()` in background thread + add error handling:

```python
    def load_icons(self, frame, folder, subfolder_name):
        """Load PIL images in background thread, then create PhotoImages + widgets on main thread."""
        icon_folder = os.path.join(folder, "50x50")
        pil_images = []
        try:
            filenames = os.listdir(icon_folder)
        except OSError:
            return  # silently skip if 50x50/ doesn't exist
        for filename in filenames:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(icon_folder, filename)
                try:
                    img = Image.open(image_path)
                    img.load()  # force decode here, not lazily on main thread
                    pil_images.append((filename, img, subfolder_name))
                except Exception:
                    pass  # skip corrupt files
        try:
            frame.after(0, lambda: self._create_icon_widgets(frame, pil_images, subfolder_name))
        except Exception:
            pass  # widget destroyed before thread completed
```

Also make threads daemon (finding #36):

```python
        threading.Thread(target=self.load_icons, args=(scrollable_frame, folder, subfolder_name), daemon=True).start()
```

- [ ] **Step 2: Commit**

```bash
cd ~/github/NiimPrintX && git add NiimPrintX/ui/widget/TabbedIconGrid.py && git commit -m "$(cat <<'EOF'
fix: icon grid anchor, PIL lazy loading, and tab-changed bind loop

1. Changed canvas anchor from 'n' to 'nw' — left half of icon grid
   was clipped off-screen because 'n' centers horizontally at x=0.
2. Added img.load() in background thread so PIL actually decodes images
   off the main thread (Image.open is lazy — decode was happening on
   the main thread during PhotoImage creation, causing UI freezes).
3. Moved NotebookTabChanged bind outside the for loop — was being
   registered N times (once per tab), causing load_tab_icons to fire
   N times per tab switch.
4. Added error handling in load_icons for missing 50x50/ dirs and
   corrupt image files. Set threads as daemon to not block app exit.
5. Sorted os.listdir for deterministic tab ordering.
EOF
)"
```

---

### Task 12: Run full test suite and verify

- [ ] **Step 1: Run all tests**

Run: `cd ~/github/NiimPrintX && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify no import errors**

Run: `cd ~/github/NiimPrintX && python -c "from NiimPrintX.nimmy.printer import PrinterClient; from NiimPrintX.nimmy.bluetooth import BLETransport; from NiimPrintX.nimmy.packet import NiimbotPacket; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 3: Bump version**

In `pyproject.toml`, bump version to `0.2.2`.

- [ ] **Step 4: Commit version bump**

```bash
cd ~/github/NiimPrintX && git add pyproject.toml && git commit -m "chore: bump version to 0.2.2"
```
