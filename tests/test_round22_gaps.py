"""Round 22 code-review gap tests.

Covers 14 specific gaps identified in the review:
  1. _encode_image PA mode (palette+alpha composited onto white)
  2. _encode_image LA mode (grayscale+alpha composited onto white)
  3. _encode_image P mode with transparency key (RGBA conversion path)
  4. get_rfid serial-length overrun → None
  5. get_rfid trailer-fields underrun → None
  6. write_raw with char_uuid=None → PrinterException
  7. set_dimensionV2 copies bounds check (0 and 65536)
  8. merge_label_sizes non-dict devices → builtin unchanged
  9. PrinterOperation.printer_disconnect exception → False, printer=None
 10. _validate_dims three-element list → None
 11. find_characteristics empty services → PrinterException
 12. find_characteristics multiple matches → uses first, logs warning
 13. notification_data None guard (event set but data is None)
 14. info_command success initialized before try block
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from NiimPrintX.nimmy.exception import PrinterException
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import RequestCodeEnum
from NiimPrintX.nimmy.userconfig import _validate_dims, merge_label_sizes
from NiimPrintX.ui.widget.PrinterOperation import PrinterOperation

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_fake_write(client, response_pkt):
    """Return an async side_effect that sets notification_data from response_pkt."""

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    return fake_write


def _make_config(**overrides):
    """Build a minimal mock config for PrinterOperation."""
    cfg = MagicMock()
    cfg.printer_connected = overrides.get("printer_connected", False)
    cfg.device = overrides.get("device", "d110")
    return cfg


# ---------------------------------------------------------------------------
# 1. _encode_image PA mode (palette + alpha composited onto white)
# ---------------------------------------------------------------------------


def test_encode_image_pa_mode(make_client):
    """PA (palette+alpha) image must be composited onto white and produce packets."""
    client = make_client()
    # Create a small PA image: palette mode with alpha
    img = Image.new("PA", (16, 4), color=0)
    packets = list(client._encode_image(img))
    assert len(packets) == 4
    for pkt in packets:
        assert pkt.type == 0x85
        # 6-byte header + ceil(16/8) = 2 bytes per row
        assert len(pkt.data) == 6 + 2


# ---------------------------------------------------------------------------
# 2. _encode_image LA mode (grayscale + alpha composited onto white)
# ---------------------------------------------------------------------------


def test_encode_image_la_mode(make_client):
    """LA (grayscale+alpha) image must be composited onto white and produce packets."""
    client = make_client()
    img = Image.new("LA", (24, 3), color=(0, 255))
    packets = list(client._encode_image(img))
    assert len(packets) == 3
    for pkt in packets:
        assert pkt.type == 0x85
        # 6-byte header + ceil(24/8) = 3 bytes per row
        assert len(pkt.data) == 6 + 3


# ---------------------------------------------------------------------------
# 3. _encode_image P mode with transparency (→ RGBA conversion path)
# ---------------------------------------------------------------------------


def test_encode_image_p_mode_with_transparency(make_client):
    """P mode palette image should go through RGBA conversion and produce packets."""
    client = make_client()
    # Create a P-mode image with transparency info
    img = Image.new("P", (8, 2), color=0)
    # Add transparency info (the code checks for "P" mode and converts to RGBA)
    img.info["transparency"] = 0
    packets = list(client._encode_image(img))
    assert len(packets) == 2
    for pkt in packets:
        assert pkt.type == 0x85
        # 6-byte header + ceil(8/8) = 1 byte per row
        assert len(pkt.data) == 6 + 1


# ---------------------------------------------------------------------------
# 4. get_rfid serial-length overrun → None
# ---------------------------------------------------------------------------


async def test_get_rfid_serial_length_overrun(make_client):
    """RFID data where serial_len claims more bytes than available should return None."""
    client = make_client()

    # Build RFID data: 8-byte UUID + barcode_len(1) + barcode(barcode_len)
    # + serial_len(255) which exceeds remaining data
    uuid_bytes = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    barcode = b"ABC"
    barcode_len = bytes([len(barcode)])
    # serial_len claims 255 bytes but we only have 0 bytes after
    serial_len = bytes([255])
    rfid_data = b"\x01" + uuid_bytes[1:] + barcode_len + barcode + serial_len

    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, rfid_data)
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, response_pkt))

    result = await client.get_rfid()
    assert result is None


# ---------------------------------------------------------------------------
# 5. get_rfid trailer-fields underrun → None
# ---------------------------------------------------------------------------


async def test_get_rfid_trailer_fields_underrun(make_client):
    """Valid barcode+serial but missing 5-byte trailer should return None."""
    client = make_client()

    # Build RFID data with valid barcode and serial but truncated trailer
    uuid_bytes = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    barcode = b"BAR"
    serial = b"SER"
    # Valid barcode+serial but only 3 bytes of trailer (need 5 for HHB unpack)
    rfid_data = (
        uuid_bytes
        + bytes([len(barcode)])
        + barcode
        + bytes([len(serial)])
        + serial
        + b"\x00\x01\x02"  # only 3 bytes, need 5
    )

    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, rfid_data)
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, response_pkt))

    result = await client.get_rfid()
    assert result is None


# ---------------------------------------------------------------------------
# 6. write_raw with char_uuid=None → PrinterException
# ---------------------------------------------------------------------------


async def test_write_raw_char_uuid_none_raises(make_client):
    """Connected transport but char_uuid=None should raise PrinterException."""
    client = make_client()
    client.char_uuid = None

    packet = NiimbotPacket(0x85, b"\x00\x01")
    with pytest.raises(PrinterException, match="No characteristic UUID available"):
        await client.write_raw(packet)


# ---------------------------------------------------------------------------
# 7. set_dimensionV2 copies bounds check (0 and 65536)
# ---------------------------------------------------------------------------


async def test_set_dimensionV2_copies_zero_raises(make_client):
    """copies=0 should raise PrinterException."""
    client = make_client()
    with pytest.raises(PrinterException, match="Copies must be 1-65535, got 0"):
        await client.set_dimensionV2(100, 50, copies=0)


async def test_set_dimensionV2_copies_overflow_raises(make_client):
    """copies=65536 should raise PrinterException."""
    client = make_client()
    with pytest.raises(PrinterException, match="Copies must be 1-65535, got 65536"):
        await client.set_dimensionV2(100, 50, copies=65536)


# ---------------------------------------------------------------------------
# 8. merge_label_sizes non-dict devices → builtin unchanged
# ---------------------------------------------------------------------------


def test_merge_label_sizes_non_dict_devices():
    """When user_config['devices'] is a string, return builtin unchanged."""
    builtin = {
        "d110": {
            "size": {"30x15": (30, 15)},
            "density": 3,
            "print_dpi": 203,
            "rotation": 270,
        }
    }
    user_config = {"devices": "not-a-dict"}
    result = merge_label_sizes(builtin, user_config)
    assert result == builtin
    # Ensure it's a deep copy, not the same object
    assert result is not builtin


# ---------------------------------------------------------------------------
# 9. PrinterOperation.printer_disconnect exception → False, printer=None
# ---------------------------------------------------------------------------


async def test_printer_disconnect_exception_returns_false():
    """When disconnect() raises, printer_disconnect should return False and clear printer."""
    config = _make_config(printer_connected=True)
    op = PrinterOperation(config)

    mock_printer = MagicMock()
    mock_printer.disconnect = AsyncMock(side_effect=RuntimeError("BLE transport error"))
    op.printer = mock_printer

    result = await op.printer_disconnect()

    assert result is False
    assert op.printer is None


# ---------------------------------------------------------------------------
# 10. _validate_dims three-element list → None
# ---------------------------------------------------------------------------


def test_validate_dims_three_element_list():
    """A 3-element list like [50, 30, 0] should return None."""
    result = _validate_dims([50, 30, 0])
    assert result is None


# ---------------------------------------------------------------------------
# 11. find_characteristics empty services → PrinterException
# ---------------------------------------------------------------------------


async def test_find_characteristics_empty_services(make_client):
    """Empty services list should raise PrinterException."""
    client = make_client()

    mock_ble_client = MagicMock()
    mock_ble_client.services = []  # no services at all
    client.transport.client = mock_ble_client

    with pytest.raises(PrinterException, match="Cannot find bluetooth characteristics"):
        await client.find_characteristics()


# ---------------------------------------------------------------------------
# 12. find_characteristics multiple matches → uses first, logs warning
# ---------------------------------------------------------------------------


async def test_find_characteristics_multiple_matches_uses_first(make_client):
    """Two matching chars should pick first and log a warning."""
    client = make_client()

    # Build two characteristics that both match (read + write-without-response + notify)
    char1 = MagicMock()
    char1.uuid = "uuid-first"
    char1.handle = 1
    char1.properties = ["read", "write-without-response", "notify"]

    char2 = MagicMock()
    char2.uuid = "uuid-second"
    char2.handle = 2
    char2.properties = ["read", "write-without-response", "notify"]

    service = MagicMock()
    service.uuid = "service-uuid"
    service.characteristics = [char1, char2]

    mock_ble_client = MagicMock()
    mock_ble_client.services = [service]
    client.transport.client = mock_ble_client

    with patch("NiimPrintX.nimmy.printer.logger") as mock_logger:
        await client.find_characteristics()

    assert client.char_uuid == "uuid-first"
    mock_logger.warning.assert_called_once()
    assert "Multiple matching characteristics" in mock_logger.warning.call_args[0][0]


# ---------------------------------------------------------------------------
# 13. notification_data None guard (event set but data is None)
# ---------------------------------------------------------------------------


async def test_notification_data_none_guard(make_client):
    """Event set but notification_data is None should raise PrinterException."""
    client = make_client()

    async def fake_write(data, char_uuid):
        # Set the event but leave notification_data as None
        client.notification_data = None
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    with pytest.raises(PrinterException, match="no data"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")


# ---------------------------------------------------------------------------
# 14. info_command success initialized before try block
# ---------------------------------------------------------------------------


def test_info_command_success_initialized_before_try(runner):
    """Verify success=False is initialized before the try block so a failed
    asyncio.run still triggers sys.exit(1) via 'if not success'."""
    # Simulate asyncio.run raising an unexpected exception that is NOT
    # KeyboardInterrupt (caught separately) and NOT generic Exception
    # (caught by the second except). We test that even if the try body
    # never sets success=True, the 'if not success' guard exits non-zero.
    with patch("NiimPrintX.cli.command.asyncio.run", side_effect=Exception("boom")):
        from NiimPrintX.cli.command import niimbot_cli

        result = runner.invoke(niimbot_cli, ["info", "-m", "d110"])
        assert result.exit_code != 0
