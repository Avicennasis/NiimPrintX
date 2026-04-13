"""Tests covering critical coverage gaps across printer, bluetooth, UserConfig, and logger."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from NiimPrintX.nimmy.bluetooth import BLETransport
from NiimPrintX.nimmy.exception import BLEException, PrinterException
from NiimPrintX.nimmy.logger_config import logger_enable
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import RequestCodeEnum
from NiimPrintX.nimmy.userconfig import _safe_int

# ---------------------------------------------------------------------------
# 1. find_characteristics — no matching characteristic raises PrinterException
# ---------------------------------------------------------------------------


async def test_find_characteristics_no_match_raises(make_client):
    """When no characteristic has read+write-without-response+notify,
    find_characteristics must raise PrinterException."""
    client = make_client()

    # Build a mock service whose single characteristic lacks 'notify'
    char = MagicMock()
    char.uuid = "0000ae01-0000-1000-8000-00805f9b34fb"
    char.handle = 1
    char.properties = ["read", "write-without-response"]  # missing 'notify'

    service = MagicMock()
    service.uuid = "0000ae00-0000-1000-8000-00805f9b34fb"
    service.characteristics = [char]

    client.transport.client.services = [service]

    with pytest.raises(PrinterException, match="Cannot find bluetooth characteristics"):
        await client.find_characteristics()


async def test_find_characteristics_multi_char_service(make_client):
    """A matching characteristic in a service with multiple characteristics
    should still be found (not skipped)."""
    client = make_client()

    # Build a service with two characteristics — only the second matches
    battery_char = MagicMock()
    battery_char.uuid = "00002a19-0000-1000-8000-00805f9b34fb"
    battery_char.handle = 1
    battery_char.properties = ["read", "notify"]

    printer_char = MagicMock()
    printer_char.uuid = "0000ae01-0000-1000-8000-00805f9b34fb"
    printer_char.handle = 2
    printer_char.properties = ["read", "write-without-response", "notify"]

    service = MagicMock()
    service.uuid = "0000ae00-0000-1000-8000-00805f9b34fb"
    service.characteristics = [battery_char, printer_char]

    client.transport.client.services = [service]

    await client.find_characteristics()
    assert client.char_uuid == "0000ae01-0000-1000-8000-00805f9b34fb"


# ---------------------------------------------------------------------------
# 2. BLETransport.connect — address change disconnects old client
# ---------------------------------------------------------------------------


async def test_transport_connect_address_change_disconnects_old():
    """Connecting to a new address should disconnect the old client first."""
    transport = BLETransport(address="OLD:AD:DR:ES:S0:00")

    # Set up an existing mock client that is "connected"
    old_client = AsyncMock()
    old_client.is_connected = True
    old_client.disconnect = AsyncMock()
    transport.client = old_client

    new_address = "NE:WA:DD:RE:SS:11"

    with patch("NiimPrintX.nimmy.bluetooth.BleakClient") as MockBleakClient:
        new_mock_client = AsyncMock()
        new_mock_client.is_connected = False
        new_mock_client.connect = AsyncMock()
        MockBleakClient.return_value = new_mock_client

        await transport.connect(new_address)  # should not raise

    # Old client should have been disconnected
    old_client.disconnect.assert_awaited_once()
    # Transport should now point at the new address and the new client
    assert transport.address == new_address
    assert transport.client is new_mock_client


# ---------------------------------------------------------------------------
# 3. print_image — zero effective dimension raises PrinterException
# ---------------------------------------------------------------------------


async def test_print_image_zero_dimension_raises(make_client):
    """When negative horizontal_offset equals the image width, effective_width
    becomes 0 and print_image must raise PrinterException."""
    client = make_client()

    # Mock the commands that execute before the dimension check
    ok_pkt = NiimbotPacket(RequestCodeEnum.SET_LABEL_DENSITY, b"\x01")
    ok_bytes = ok_pkt.to_bytes()

    async def fake_write(data, char_uuid):
        client.notification_data = ok_bytes
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (100, 50), color=0)

    with pytest.raises(PrinterException, match="no data after applying offsets"):
        await client.print_image(img, horizontal_offset=-100)


# ---------------------------------------------------------------------------
# 4. send_command — start_notification failure raises PrinterException
# ---------------------------------------------------------------------------


async def test_send_command_start_notification_failure_raises(make_client):
    """If start_notification raises, PrinterException must propagate."""
    client = make_client()
    client.transport.start_notification = AsyncMock(side_effect=BLEException("start failed"))

    with pytest.raises(PrinterException, match="BLE error"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")


# ---------------------------------------------------------------------------
# 6. _safe_int — invalid inputs return default
# ---------------------------------------------------------------------------


def test_safe_int_invalid_returns_default():
    """_safe_int should return the default for non-numeric inputs."""
    assert _safe_int("fast", 42) == 42
    assert _safe_int(None, 7) == 7
    assert _safe_int([], 0) == 0


# ---------------------------------------------------------------------------
# 7. _safe_int — float input gets rounded
# ---------------------------------------------------------------------------


def test_safe_int_float_rounds():
    """_safe_int should reject non-whole floats and return default."""
    assert _safe_int(3.7, 0) == 0  # non-whole float → default
    assert _safe_int(3.2, 0) == 0  # non-whole float → default
    assert _safe_int(3.0, 0) == 3  # whole float → accepted
    assert _safe_int(2.0, 5) == 2  # whole float → accepted


# ---------------------------------------------------------------------------
# 8. logger_enable — TRACE level (verbose=3) should not raise
# ---------------------------------------------------------------------------


def test_logger_enable_trace_level():
    """logger_enable(3) should configure TRACE level without error."""
    logger_enable(3)  # must not raise


# ---------------------------------------------------------------------------
# 9. logger_enable — very high verbosity should not raise
# ---------------------------------------------------------------------------


def test_logger_enable_high_verbose():
    """logger_enable(99) should clamp to TRACE and not raise."""
    logger_enable(99)  # must not raise


# ---------------------------------------------------------------------------
# 10. _safe_int — boolean input returns default
# ---------------------------------------------------------------------------


def test_safe_int_bool_returns_default():
    """Boolean values should be rejected (TOML true/false)."""
    assert _safe_int(True, 3) == 3
    assert _safe_int(False, 3) == 3
