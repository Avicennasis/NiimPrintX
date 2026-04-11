"""Tests verifying critical fixes identified in the code review."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from PIL import Image

from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import PrinterClient, RequestCodeEnum
from NiimPrintX.nimmy.bluetooth import BLETransport


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


# --- 1. Packet from_bytes with trailing bytes ---


def test_packet_from_bytes_oversized_packet():
    """Packets with trailing bytes after footer should still parse correctly."""
    pkt = NiimbotPacket(0x01, b"\x02\x03")
    raw = bytearray(pkt.to_bytes())
    raw.extend(b"\xAA\xAA\xFF\xFF")  # extra trailing bytes
    # Should parse the valid portion and ignore trailing data
    parsed = NiimbotPacket.from_bytes(bytes(raw))
    assert parsed.type == 0x01
    assert parsed.data == b"\x02\x03"


# --- 2. set_quantity validation ---


@pytest.mark.asyncio
async def test_set_quantity_negative_raises():
    client = _make_client()
    with pytest.raises(ValueError, match="Quantity must be"):
        await client.set_quantity(-1)


@pytest.mark.asyncio
async def test_set_quantity_overflow_raises():
    client = _make_client()
    with pytest.raises(ValueError, match="Quantity must be"):
        await client.set_quantity(70000)


# --- 3. _encode_image fill=0 produces blank borders ---


def test_encode_image_positive_offset_blank_border():
    """Positive vertical offset should produce blank (non-printing) rows at top."""
    client = _make_client()
    img = Image.new("L", (8, 2), color=0)  # all black
    packets = list(client._encode_image(img, vertical_offset=2))
    assert len(packets) == 4  # 2 original + 2 offset
    # First 2 rows are offset padding -- should be all zeros (blank)
    for pkt in packets[:2]:
        line_data = pkt.data[6:]
        assert line_data == b'\x00', f"Expected blank border, got {line_data.hex()}"


# --- 4. heartbeat unknown length logs warning (no crash) ---


@pytest.mark.asyncio
async def test_heartbeat_unknown_length_returns_all_none():
    """Unknown heartbeat length should return all-None dict without crashing."""
    client = _make_client()
    hb_data = bytes(15)  # 15 bytes -- not in any match case
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, hb_data)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result["closing_state"] is None
    assert result["power_level"] is None
    assert result["paper_state"] is None
    assert result["rfid_read_state"] is None


# --- 5. UserConfig _validate_dims rejects zero/negative ---


def test_validate_dims_zero_rejected():
    from NiimPrintX.ui.UserConfig import _validate_dims
    assert _validate_dims([0, 15]) is None


def test_validate_dims_negative_rejected():
    from NiimPrintX.ui.UserConfig import _validate_dims
    assert _validate_dims([-5, 15]) is None


# --- 6. BLETransport disconnect clears client ---


@pytest.mark.asyncio
async def test_transport_disconnect_clears_client():
    transport = BLETransport()
    transport.client = MagicMock()
    transport.client.is_connected = True
    transport.client.disconnect = AsyncMock()
    await transport.disconnect()
    assert transport.client is None
