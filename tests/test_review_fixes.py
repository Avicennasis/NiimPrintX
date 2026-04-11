"""Tests verifying critical fixes identified in the code review."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from NiimPrintX.nimmy.bluetooth import BLETransport
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import RequestCodeEnum

# --- 1. Packet from_bytes with trailing bytes ---


def test_packet_from_bytes_oversized_packet():
    """Packets with trailing bytes after footer should still parse correctly."""
    pkt = NiimbotPacket(0x01, b"\x02\x03")
    raw = bytearray(pkt.to_bytes())
    raw.extend(b"\xaa\xaa\xff\xff")  # extra trailing bytes
    # Strict length check: trailing bytes are now rejected (Round 9 fix)
    with pytest.raises(ValueError, match="mismatch"):
        NiimbotPacket.from_bytes(bytes(raw))


# --- 2. set_quantity validation ---


async def test_set_quantity_negative_raises(make_client):
    client = make_client()
    with pytest.raises(ValueError, match="Quantity must be"):
        await client.set_quantity(-1)


async def test_set_quantity_overflow_raises(make_client):
    client = make_client()
    with pytest.raises(ValueError, match="Quantity must be"):
        await client.set_quantity(70000)


# --- 3. _encode_image fill=0 produces blank borders ---


def test_encode_image_positive_offset_blank_border(make_client):
    """Positive vertical offset should produce blank (non-printing) rows at top."""
    client = make_client()
    img = Image.new("L", (8, 2), color=0)  # all black
    packets = list(client._encode_image(img, vertical_offset=2))
    assert len(packets) == 4  # 2 original + 2 offset
    # First 2 rows are offset padding -- should be all zeros (blank)
    for pkt in packets[:2]:
        line_data = pkt.data[6:]
        assert line_data == b"\x00", f"Expected blank border, got {line_data.hex()}"


# --- 4. heartbeat unknown length logs warning (no crash) ---


async def test_heartbeat_unknown_length_returns_all_none(make_client):
    """Unknown heartbeat length should return all-None dict without crashing."""
    client = make_client()
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


async def test_transport_disconnect_clears_client():
    transport = BLETransport(address="AA:BB:CC:DD:EE:FF")
    transport.client = MagicMock()
    transport.client.is_connected = True
    transport.client.disconnect = AsyncMock()
    mock_client = transport.client  # save reference before disconnect nulls it
    await transport.disconnect()
    assert transport.client is None
    mock_client.disconnect.assert_awaited_once()
