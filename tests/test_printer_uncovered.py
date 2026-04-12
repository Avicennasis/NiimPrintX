"""Tests targeting uncovered paths in NiimPrintX/nimmy/printer.py.

Covers:
- PrinterClient.__init__ via normal constructor
- connect() — find_characteristics raises PrinterException (disconnect + re-raise)
- disconnect() — basic path
- send_command() — reconnect when client is not connected
- write_raw() — basic success path
- write_raw() — BLEException wrapping
- _print_job() — effective_width == 0 after positive horizontal_offset (impossible, but code path)
- _print_job() — effective_height == 0 after negative vertical_offset
- _encode_image() — horizontal_offset < 0
- _encode_image() — zero-size image after negative offsets that crop everything
- get_info() — SOFTVERSION, HARDVERSION, and default (BATTERY) cases
- Various command methods — empty response raises PrinterException
"""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from NiimPrintX.nimmy.exception import BLEException, PrinterException
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import InfoEnum, PrinterClient, RequestCodeEnum

# ---------------------------------------------------------------------------
# Helper: build a fake_write that auto-responds to send_command
# ---------------------------------------------------------------------------


def _make_fake_write(client, response_pkt):
    """Return an async side_effect that sets notification_data from response_pkt."""

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    return fake_write


# ---------------------------------------------------------------------------
# PrinterClient.__init__ via normal constructor
# ---------------------------------------------------------------------------


async def test_init_via_constructor():
    """PrinterClient.__init__ should initialise all attributes from a device."""
    device = MagicMock()
    device.name = "test-printer"
    device.address = "AA:BB:CC:DD:EE:FF"

    client = PrinterClient(device)

    assert client.device is device
    assert client.char_uuid is None
    assert client.notification_data is None
    assert not client.notification_event.is_set()
    assert client._loop is None


# ---------------------------------------------------------------------------
# connect() — find_characteristics raises → disconnect + re-raise
# ---------------------------------------------------------------------------


async def test_connect_find_chars_raises_disconnects_and_reraises():
    """When find_characteristics raises PrinterException during connect(),
    the transport must be disconnected and the exception re-raised."""
    device = MagicMock()
    device.name = "test-printer"
    device.address = "AA:BB:CC:DD:EE:FF"

    client = PrinterClient(device)
    client.transport = MagicMock()
    client.transport.connect = AsyncMock(return_value=True)
    client.transport.disconnect = AsyncMock()

    # Mock client.services so find_characteristics finds nothing
    mock_ble_client = MagicMock()
    char = MagicMock()
    char.uuid = "some-uuid"
    char.handle = 1
    char.properties = ["read"]  # missing write-without-response and notify
    service = MagicMock()
    service.uuid = "service-uuid"
    service.characteristics = [char]
    mock_ble_client.services = [service]
    client.transport.client = mock_ble_client

    with pytest.raises(PrinterException, match="Cannot find bluetooth characteristics"):
        await client.connect()

    client.transport.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# connect() — transport.connect raises exception
# ---------------------------------------------------------------------------


async def test_connect_transport_raises_propagates():
    """When transport.connect() raises, connect() must propagate the exception."""
    device = MagicMock()
    device.name = "test-printer"
    device.address = "AA:BB:CC:DD:EE:FF"

    client = PrinterClient(device)
    client.transport = MagicMock()
    client.transport.connect = AsyncMock(side_effect=BLEException("Connection failed"))
    client.transport.disconnect = AsyncMock()

    with pytest.raises(BLEException, match="Connection failed"):
        await client.connect()


# ---------------------------------------------------------------------------
# disconnect() — basic path
# ---------------------------------------------------------------------------


async def test_disconnect_basic(make_client):
    """disconnect() should clear char_uuid and call transport.disconnect()."""
    client = make_client()
    client.char_uuid = "some-uuid"
    client.transport.disconnect = AsyncMock()

    await client.disconnect()

    assert client.char_uuid is None
    client.transport.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# send_command() — reconnect path when client is None
# ---------------------------------------------------------------------------


async def test_send_command_reconnect_when_client_is_none(make_client):
    """When transport.client is None, send_command should call connect()."""
    client = make_client()
    client.transport.client = None  # simulate no BLE client

    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, b"\x42")

    async def fake_connect():
        # Restore a mock client so the command can proceed
        client.transport.client = MagicMock()
        client.transport.client.is_connected = True
        client.transport.write = AsyncMock(side_effect=_make_fake_write(client, response_pkt))
        return True

    client.connect = AsyncMock(side_effect=fake_connect)

    result = await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")

    client.connect.assert_awaited_once()
    assert result.data == b"\x42"


# ---------------------------------------------------------------------------
# send_command() — reconnect fails raises PrinterException
# ---------------------------------------------------------------------------


async def test_send_command_reconnect_fails_when_client_is_none(make_client):
    """When transport.client is None and reconnect fails, raise PrinterException."""
    client = make_client()
    client.transport.client = None
    client.connect = AsyncMock(return_value=False)

    with pytest.raises(PrinterException, match="Failed to reconnect"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")


# ---------------------------------------------------------------------------
# disconnect() — stop_notification failure is suppressed
# ---------------------------------------------------------------------------


async def test_disconnect_stop_notification_failure_suppressed(make_client):
    """When stop_notification raises during disconnect, it should be suppressed."""
    client = make_client()
    client.char_uuid = "test-uuid"
    client.transport.stop_notification = AsyncMock(side_effect=RuntimeError("stop failed"))
    client.transport.disconnect = AsyncMock()
    # Should not raise despite stop_notification failure
    await client.disconnect()
    client.transport.stop_notification.assert_awaited_once_with("test-uuid")


# ---------------------------------------------------------------------------
# write_raw() — basic success path
# ---------------------------------------------------------------------------


async def test_write_raw_success(make_client):
    """write_raw() should call transport.write with packet bytes."""
    client = make_client()
    client.transport.write = AsyncMock()

    packet = NiimbotPacket(0x85, b"\x00\x01\x02")
    await client.write_raw(packet)

    client.transport.write.assert_awaited_once_with(packet.to_bytes(), client.char_uuid)


# ---------------------------------------------------------------------------
# write_raw() — BLEException wrapping
# ---------------------------------------------------------------------------


async def test_write_raw_ble_exception(make_client):
    """write_raw() should wrap BLEException as PrinterException."""
    client = make_client()
    client.transport.write = AsyncMock(side_effect=BLEException("write failed"))

    packet = NiimbotPacket(0x85, b"\x00")
    with pytest.raises(PrinterException, match=r"BLE write failed.*write failed"):
        await client.write_raw(packet)


# ---------------------------------------------------------------------------
# write_raw() — ValueError wrapping
# ---------------------------------------------------------------------------


async def test_write_raw_value_error(make_client):
    """write_raw() should wrap ValueError as PrinterException."""
    client = make_client()
    client.transport.write = AsyncMock(side_effect=ValueError("bad data"))

    packet = NiimbotPacket(0x85, b"\x00")
    with pytest.raises(PrinterException, match=r"BLE write failed.*bad data"):
        await client.write_raw(packet)


# ---------------------------------------------------------------------------
# write_raw() — reconnect when client not connected
# ---------------------------------------------------------------------------


async def test_write_raw_reconnect_when_disconnected(make_client):
    """write_raw() should attempt reconnect when transport is disconnected."""
    client = make_client()
    client.transport.client.is_connected = False

    async def fake_connect():
        client.transport.client.is_connected = True
        client.transport.write = AsyncMock()
        return True

    client.connect = AsyncMock(side_effect=fake_connect)

    packet = NiimbotPacket(0x85, b"\x00")
    await client.write_raw(packet)

    client.connect.assert_awaited_once()


# ---------------------------------------------------------------------------
# write_raw() — reconnect failure
# ---------------------------------------------------------------------------


async def test_write_raw_reconnect_failure(make_client):
    """write_raw() should raise PrinterException when reconnect fails."""
    client = make_client()
    client.transport.client.is_connected = False
    client.connect = AsyncMock(return_value=False)

    packet = NiimbotPacket(0x85, b"\x00")
    with pytest.raises(PrinterException, match="Failed to reconnect"):
        await client.write_raw(packet)


# ---------------------------------------------------------------------------
# _print_job() — effective_height == 0 after negative vertical_offset
# ---------------------------------------------------------------------------


@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_print_job_zero_height_after_negative_vertical_offset(mock_sleep, make_client):
    """When negative vertical_offset cancels image height, raise PrinterException."""
    client = make_client()

    ok_pkt = NiimbotPacket(RequestCodeEnum.SET_LABEL_DENSITY, b"\x01")

    async def fake_write(data, char_uuid):
        client.notification_data = ok_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (100, 50), color=0)
    with pytest.raises(PrinterException, match="no data after applying offsets"):
        await client.print_image(img, vertical_offset=-50)


# ---------------------------------------------------------------------------
# _print_job() — positive horizontal_offset increases effective_width
# ---------------------------------------------------------------------------


@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_print_job_positive_horizontal_offset(mock_sleep, make_client):
    """positive horizontal_offset should increase effective_width, not fail."""
    client = make_client()

    commands_sent = []

    async def fake_write(data, char_uuid):
        pkt = NiimbotPacket.from_bytes(data)
        commands_sent.append((pkt.type, pkt.data))
        if pkt.type == 0x85:
            return
        response_type = pkt.type
        response_data = struct.pack(">HBB", 1, 100, 100) if pkt.type == RequestCodeEnum.GET_PRINT_STATUS else b"\x01"
        resp = NiimbotPacket(response_type, response_data)
        client.notification_data = resp.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (16, 4), color=0)
    await client.print_image(img, horizontal_offset=8)

    # Verify SET_DIMENSION was called with effective_width = 16 + 8 = 24
    dim_cmds = [(t, d) for t, d in commands_sent if t == RequestCodeEnum.SET_DIMENSION]
    assert len(dim_cmds) == 1
    height, width = struct.unpack(">HH", dim_cmds[0][1])
    assert width == 24  # 16 + 8
    assert height == 4


# ---------------------------------------------------------------------------
# _encode_image() — negative horizontal_offset crops image
# ---------------------------------------------------------------------------


def test_encode_image_negative_horizontal_offset(make_client):
    """Negative horizontal_offset should crop from the left, reducing row width."""
    client = make_client()
    img = Image.new("1", (24, 2), color=0)

    packets_normal = list(client._encode_image(img, horizontal_offset=0))
    packets_cropped = list(client._encode_image(img, horizontal_offset=-8))

    # Normal: 24px -> 3 bytes per row
    assert len(packets_normal[0].data) - 6 == 3
    # Cropped: 24-8=16px -> 2 bytes per row
    assert len(packets_cropped[0].data) - 6 == 2


# ---------------------------------------------------------------------------
# _encode_image() — negative vertical_offset crops rows
# ---------------------------------------------------------------------------


def test_encode_image_negative_vertical_offset(make_client):
    """Negative vertical_offset should crop rows from the top."""
    client = make_client()
    img = Image.new("1", (8, 10), color=0)

    packets_full = list(client._encode_image(img, vertical_offset=0))
    packets_cropped = list(client._encode_image(img, vertical_offset=-4))

    assert len(packets_full) == 10
    assert len(packets_cropped) == 6  # 10 - 4


# ---------------------------------------------------------------------------
# _encode_image() — negative offset crops everything -> raises
# ---------------------------------------------------------------------------


def test_encode_image_negative_offset_zero_size_raises(make_client):
    """When negative offsets reduce the image to zero, raise PrinterException."""
    client = make_client()
    img = Image.new("1", (8, 4), color=0)

    with pytest.raises(PrinterException, match="no data after applying offsets"):
        list(client._encode_image(img, horizontal_offset=-8))


def test_encode_image_negative_vertical_offset_zero_height_raises(make_client):
    """When negative vertical offset reduces height to zero, raise PrinterException."""
    client = make_client()
    img = Image.new("1", (8, 4), color=0)

    with pytest.raises(PrinterException, match="no data after applying offsets"):
        list(client._encode_image(img, vertical_offset=-4))


# ---------------------------------------------------------------------------
# get_info() — SOFTVERSION returns int/100
# ---------------------------------------------------------------------------


async def test_get_info_softversion(make_client):
    """get_info(SOFTVERSION) should return big-endian int / 100."""
    client = make_client()
    # 0x0190 = 400 -> 400/100 = 4.0
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, bytes([0x01, 0x90]))
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, response_pkt))

    result = await client.get_info(InfoEnum.SOFTVERSION)
    assert result == 4.0


# ---------------------------------------------------------------------------
# get_info() — HARDVERSION returns int/100
# ---------------------------------------------------------------------------


async def test_get_info_hardversion(make_client):
    """get_info(HARDVERSION) should return big-endian int / 100."""
    client = make_client()
    # 0x012C = 300 -> 300/100 = 3.0
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, bytes([0x01, 0x2C]))
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, response_pkt))

    result = await client.get_info(InfoEnum.HARDVERSION)
    assert result == 3.0


# ---------------------------------------------------------------------------
# get_info() — default case (BATTERY) returns raw int
# ---------------------------------------------------------------------------


async def test_get_info_battery_default_case(make_client):
    """get_info(BATTERY) should return the raw big-endian int (default case)."""
    client = make_client()
    # 0x50 = 80
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, bytes([0x50]))
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, response_pkt))

    result = await client.get_info(InfoEnum.BATTERY)
    assert result == 0x50


# ---------------------------------------------------------------------------
# get_info() — DEVICESERIAL returns hex string
# ---------------------------------------------------------------------------


async def test_get_info_device_serial(make_client):
    """get_info(DEVICESERIAL) should return data as hex string."""
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, bytes([0xCA, 0xFE]))
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, response_pkt))

    result = await client.get_info(InfoEnum.DEVICESERIAL)
    assert result == "cafe"


# ---------------------------------------------------------------------------
# get_info() — empty response raises
# ---------------------------------------------------------------------------


async def test_get_info_empty_response(make_client):
    """get_info must raise PrinterException when response has empty data."""
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, response_pkt))

    with pytest.raises(PrinterException, match=r"Empty response from printer for GET_INFO"):
        await client.get_info(InfoEnum.BATTERY)


# ---------------------------------------------------------------------------
# Empty response paths for each command method
# ---------------------------------------------------------------------------


async def test_start_print_empty_response(make_client):
    """start_print must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.START_PRINT, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*START_PRINT"):
        await client.start_print()


async def test_start_print_v2_empty_response(make_client):
    """start_print_v2 must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.START_PRINT, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*START_PRINT"):
        await client.start_print_v2(quantity=1)


async def test_end_print_empty_response(make_client):
    """end_print must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.END_PRINT, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*END_PRINT"):
        await client.end_print()


async def test_start_page_print_empty_response(make_client):
    """start_page_print must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.START_PAGE_PRINT, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*START_PAGE_PRINT"):
        await client.start_page_print()


async def test_end_page_print_empty_response(make_client):
    """end_page_print must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.END_PAGE_PRINT, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*END_PAGE_PRINT"):
        await client.end_page_print()


async def test_set_dimension_empty_response(make_client):
    """set_dimension must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.SET_DIMENSION, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*SET_DIMENSION"):
        await client.set_dimension(100, 50)


async def test_set_dimension_v2_empty_response(make_client):
    """set_dimension_v2 must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.SET_DIMENSION, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*SET_DIMENSION"):
        await client.set_dimension_v2(100, 50, 1)


async def test_set_quantity_empty_response(make_client):
    """set_quantity must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.SET_QUANTITY, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*SET_QUANTITY"):
        await client.set_quantity(1)


async def test_set_label_density_empty_response(make_client):
    """set_label_density must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.SET_LABEL_DENSITY, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*SET_LABEL_DENSITY"):
        await client.set_label_density(3)


async def test_set_label_type_empty_response(make_client):
    """set_label_type must raise PrinterException on empty response."""
    client = make_client()
    empty_pkt = NiimbotPacket(RequestCodeEnum.SET_LABEL_TYPE, b"")
    client.transport.write = AsyncMock(side_effect=_make_fake_write(client, empty_pkt))
    with pytest.raises(PrinterException, match=r"Empty response.*SET_LABEL_TYPE"):
        await client.set_label_type(1)
