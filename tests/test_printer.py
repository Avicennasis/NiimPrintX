import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from NiimPrintX.nimmy.exception import PrinterException
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import InfoEnum, RequestCodeEnum


async def test_send_command_clears_event_before_wait(make_client):
    """notification_event must be cleared before waiting, not just after."""
    client = make_client()
    # Pre-set the event to simulate a stale notification
    client.notification_event.set()
    client.notification_data = b"\x55\x55\x40\x01\xff\xbe\xaa\xaa"  # stale data

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


async def test_send_command_catches_valueerror_from_malformed_packet(make_client):
    """ValueError from from_bytes must be wrapped as PrinterException."""
    client = make_client()

    async def fake_write(data, char_uuid):
        # Simulate a corrupted response (bad header)
        client.notification_data = b"\xde\xad\x40\x01\x01\x40\xaa\xaa"
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    with pytest.raises(PrinterException, match="Malformed"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")


async def test_heartbeat_case_10_no_rfid(make_client):
    """10-byte heartbeat should not set rfid_read_state (only 2 useful fields)."""
    client = make_client()
    hb_data = bytearray(10)
    hb_data[8] = 0x05  # closing_state
    hb_data[9] = 0x64  # power_level
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, bytes(hb_data))

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result["closing_state"] == 0x05
    assert result["power_level"] == 0x64
    assert result["rfid_read_state"] is None


async def test_send_command_timeout_raises_printer_exception(make_client):
    """Timeout must be wrapped as PrinterException."""
    client = make_client()
    # Never set the event — will timeout
    with pytest.raises(PrinterException, match="timed out"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01", timeout=0.1)


async def test_heartbeat_case_20(make_client):
    """20-byte heartbeat sets paper_state and rfid_read_state from tail bytes."""
    client = make_client()
    hb_data = bytearray(20)
    hb_data[18] = 0x02  # paper_state
    hb_data[19] = 0x03  # rfid_read_state
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, bytes(hb_data))

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result["closing_state"] is None
    assert result["power_level"] is None
    assert result["paper_state"] == 0x02
    assert result["rfid_read_state"] == 0x03


async def test_heartbeat_case_13(make_client):
    """13-byte heartbeat extracts closing_state, power, paper, and rfid."""
    client = make_client()
    hb_data = bytearray(13)
    hb_data[9] = 0x01  # closing_state
    hb_data[10] = 0x64  # power_level
    hb_data[11] = 0x0A  # paper_state
    hb_data[12] = 0x0B  # rfid_read_state
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, bytes(hb_data))

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result["closing_state"] == 0x01
    assert result["power_level"] == 0x64
    assert result["paper_state"] == 0x0A
    assert result["rfid_read_state"] == 0x0B


async def test_heartbeat_case_19(make_client):
    """19-byte heartbeat reads state fields from higher offsets."""
    client = make_client()
    hb_data = bytearray(19)
    hb_data[15] = 0x01  # closing_state
    hb_data[16] = 0x50  # power_level
    hb_data[17] = 0x0C  # paper_state
    hb_data[18] = 0x0D  # rfid_read_state
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, bytes(hb_data))

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result["closing_state"] == 0x01
    assert result["power_level"] == 0x50
    assert result["paper_state"] == 0x0C
    assert result["rfid_read_state"] == 0x0D


async def test_heartbeat_case_9(make_client):
    """9-byte heartbeat only sets closing_state; paper and rfid are None."""
    client = make_client()
    hb_data = bytearray(9)
    hb_data[8] = 0x01  # closing_state
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, bytes(hb_data))

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result["closing_state"] == 0x01
    assert result["power_level"] is None
    assert result["paper_state"] is None
    assert result["rfid_read_state"] is None


async def test_set_label_type_invalid_raises(make_client):
    """set_label_type(0) must raise ValueError (valid range is 1-3)."""
    client = make_client()
    with pytest.raises(ValueError, match="Label type must be 1-3"):
        await client.set_label_type(0)


async def test_set_label_density_invalid_raises(make_client):
    """set_label_density(6) must raise ValueError (valid range is 1-5)."""
    client = make_client()
    with pytest.raises(ValueError, match="Label density must be 1-5"):
        await client.set_label_density(6)


async def test_start_printV2_quantity_validation(make_client):
    """start_printV2(quantity=-1) must raise ValueError."""
    client = make_client()
    with pytest.raises(ValueError, match="Quantity must be 1-65535"):
        await client.start_printV2(quantity=-1)


async def test_get_info_device_serial(make_client):
    """get_info(DEVICESERIAL) should return the response data as a hex string."""
    client = make_client()
    serial_bytes = bytes([0xDE, 0xAD, 0xBE, 0xEF])
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, serial_bytes)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_info(InfoEnum.DEVICESERIAL)
    assert result == "deadbeef"


async def test_get_info_soft_version(make_client):
    """get_info(SOFTVERSION) should return big-endian int / 100."""
    client = make_client()
    # 0x01F4 = 500 → 500/100 = 5.0
    version_bytes = bytes([0x01, 0xF4])
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, version_bytes)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_info(InfoEnum.SOFTVERSION)
    assert result == 5.0


async def test_get_rfid_empty_data_returns_none(make_client):
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, b"\x00")

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_rfid()
    assert result is None


async def test_get_rfid_valid_data(make_client):
    client = make_client()
    uuid = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    barcode = b"BC123"
    serial = b"SN456"
    rfid_data = uuid + bytes([len(barcode)]) + barcode + bytes([len(serial)]) + serial
    rfid_data += struct.pack(">HHB", 100, 50, 2)  # total, used, type
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, rfid_data)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_rfid()
    assert result is not None
    assert result["uuid"] == uuid.hex()
    assert result["barcode"] == "BC123"
    assert result["serial"] == "SN456"
    assert result["total_len"] == 100
    assert result["used_len"] == 50
    assert result["type"] == 2


async def test_get_rfid_malformed_returns_none(make_client):
    """Truncated RFID data should return None, not crash."""
    client = make_client()
    # Valid start but truncated — will cause IndexError in parsing
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, b"\x01\x02\x03")

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_rfid()
    assert result is None


async def test_get_rfid_empty_barcode_and_serial(make_client):
    """RFID with barcode_len=0 and serial_len=0 should return empty strings
    and correctly parse the 5-byte tail (total_len, used_len, type)."""
    client = make_client()
    uuid = b"\x10\x20\x30\x40\x50\x60\x70\x80"
    barcode_len = bytes([0])  # 0-length barcode
    serial_len = bytes([0])  # 0-length serial
    tail = struct.pack(">HHB", 200, 75, 3)  # total, used, type
    rfid_data = uuid + barcode_len + serial_len + tail
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, rfid_data)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_rfid()
    assert result is not None
    assert result["uuid"] == uuid.hex()
    assert result["barcode"] == ""
    assert result["serial"] == ""
    assert result["total_len"] == 200
    assert result["used_len"] == 75
    assert result["type"] == 3


async def test_get_rfid_truncated_data(make_client):
    """RFID data where barcode_len claims more bytes than available should
    return None (IndexError or struct.error caught internally)."""
    client = make_client()
    uuid = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    # barcode_len=50 but only 2 bytes follow — will overflow when parsing
    rfid_data = uuid + bytes([50]) + b"\xab\xcd"
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, rfid_data)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_rfid()
    assert result is None


async def test_get_rfid_no_data(make_client):
    """When send_command returns a packet with empty data, get_rfid should
    return None (the `not data` guard)."""
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, b"")

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_rfid()
    assert result is None


async def test_set_quantity(make_client):
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.SET_QUANTITY, b"\x01")

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.set_quantity(5)
    assert result is True


async def test_end_print(make_client):
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.END_PRINT, b"\x01")

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.end_print()
    assert result is True


async def test_get_print_status(make_client):
    client = make_client()
    status_data = struct.pack(">HBB", 3, 50, 75)
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_PRINT_STATUS, status_data)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_print_status()
    assert result["page"] == 3
    assert result["progress1"] == 50
    assert result["progress2"] == 75


# ---------------------------------------------------------------------------
# Coverage gap: connect() success path
# ---------------------------------------------------------------------------


async def test_connect_success(make_client):
    """When BLETransport.connect() returns True and find_characteristics sets
    char_uuid, connect() should return True and _loop should be set."""
    client = make_client()
    client.char_uuid = None  # Force the find_characteristics path

    client.transport.connect = AsyncMock(return_value=True)

    # Build a mock service with a single characteristic that has the right props
    char = MagicMock()
    char.uuid = "0000ae01-0000-1000-8000-00805f9b34fb"
    char.handle = 1
    char.properties = ["read", "write-without-response", "notify"]

    service = MagicMock()
    service.uuid = "0000ae00-0000-1000-8000-00805f9b34fb"
    service.characteristics = [char]

    client.transport.client.services = [service]

    result = await client.connect()

    assert result is True
    assert client.char_uuid == char.uuid
    assert client._loop is not None


# ---------------------------------------------------------------------------
# Coverage gap: connect() failure cleans up
# ---------------------------------------------------------------------------


async def test_connect_failure_cleans_up(make_client):
    """When find_characteristics raises PrinterException, connect() must call
    disconnect() and re-raise the exception."""
    client = make_client()
    client.char_uuid = None  # Force the find_characteristics path

    client.transport.connect = AsyncMock(return_value=True)
    client.transport.disconnect = AsyncMock()

    # Mock services to produce no matching characteristics -> raises
    char = MagicMock()
    char.uuid = "0000ae01-0000-1000-8000-00805f9b34fb"
    char.handle = 1
    char.properties = ["read"]  # Missing write-without-response and notify

    service = MagicMock()
    service.uuid = "0000ae00-0000-1000-8000-00805f9b34fb"
    service.characteristics = [char]

    client.transport.client.services = [service]

    with pytest.raises(PrinterException, match="Cannot find bluetooth characteristics"):
        await client.connect()

    client.transport.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Coverage gap: disconnect() clears state
# ---------------------------------------------------------------------------


async def test_disconnect_clears_state(make_client):
    """disconnect() should set char_uuid to None and call transport.disconnect()."""
    client = make_client()
    assert client.char_uuid == "test-uuid"

    client.transport.disconnect = AsyncMock()

    await client.disconnect()

    assert client.char_uuid is None
    client.transport.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Coverage gap: notification_handler sets data via call_soon_threadsafe
# ---------------------------------------------------------------------------


async def test_notification_handler_sets_data(make_client):
    """notification_handler should schedule _set via call_soon_threadsafe,
    which sets notification_data and fires the event."""
    client = make_client()

    mock_loop = MagicMock()
    # Capture the callback passed to call_soon_threadsafe and execute it
    callbacks = []
    mock_loop.call_soon_threadsafe = MagicMock(side_effect=callbacks.append)
    client._loop = mock_loop

    sender = MagicMock()
    client.notification_handler(sender, b"\x01\x02")

    mock_loop.call_soon_threadsafe.assert_called_once()
    # Execute the captured callback to verify it sets the data
    assert len(callbacks) == 1
    callbacks[0]()
    assert client.notification_data == b"\x01\x02"
    assert client.notification_event.is_set()


# ---------------------------------------------------------------------------
# Coverage gap: notification_handler with _loop = None returns early
# ---------------------------------------------------------------------------


async def test_notification_handler_none_loop(make_client):
    """When _loop is None, notification_handler should return early without
    setting notification_data or crashing."""
    client = make_client()
    client._loop = None

    sender = MagicMock()
    client.notification_handler(sender, b"\x01\x02")

    assert client.notification_data is None
    assert not client.notification_event.is_set()


# ---------------------------------------------------------------------------
# Coverage gap: set_label_type / set_label_density with empty response data
# ---------------------------------------------------------------------------


async def test_response_parser_empty_data(make_client):
    """set_label_type and set_label_density must raise PrinterException when
    send_command returns a packet with empty data."""
    client = make_client()

    # Build a valid packet with zero-length data
    empty_pkt = NiimbotPacket(RequestCodeEnum.SET_LABEL_TYPE, b"")

    async def fake_write(data, char_uuid):
        client.notification_data = empty_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    with pytest.raises(PrinterException, match="Empty response"):
        await client.set_label_type(1)

    # Also verify set_label_density with the same empty-response scenario
    empty_pkt2 = NiimbotPacket(RequestCodeEnum.SET_LABEL_DENSITY, b"")

    async def fake_write2(data, char_uuid):
        client.notification_data = empty_pkt2.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write2)

    with pytest.raises(PrinterException, match="Empty response"):
        await client.set_label_density(2)


# ---------------------------------------------------------------------------
# Coverage gap: print_imageV2 with zero-dimension offset
# ---------------------------------------------------------------------------


async def test_print_imageV2_zero_dimension(make_client):
    """When negative horizontal_offset equals the image width, effective_width
    becomes 0 and print_imageV2 must raise PrinterException (mirroring the
    print_image test in test_coverage_gaps.py)."""
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
        await client.print_imageV2(img, horizontal_offset=-100)


# ---------------------------------------------------------------------------
# Coverage gap: get_print_status with short response
# ---------------------------------------------------------------------------


async def test_get_print_status_short_response(make_client):
    """get_print_status must raise PrinterException when the response packet
    contains fewer than 4 bytes of data."""
    client = make_client()

    # Build a packet with only 2 bytes of data (need 4 for HBB unpack)
    short_pkt = NiimbotPacket(RequestCodeEnum.GET_PRINT_STATUS, b"\x00\x01")

    async def fake_write(data, char_uuid):
        client.notification_data = short_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    with pytest.raises(PrinterException, match="short response"):
        await client.get_print_status()


# ---------------------------------------------------------------------------
# Coverage gap: get_info with empty response data raises PrinterException
# ---------------------------------------------------------------------------


async def test_get_info_empty_response_raises(make_client):
    """get_info must raise PrinterException when the printer returns a packet
    with zero-length data (tests the len(response.data) < 1 guard)."""
    client = make_client()

    empty_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, b"")

    async def fake_write(data, char_uuid):
        client.notification_data = empty_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    with pytest.raises(PrinterException, match="Empty response from printer for GET_INFO"):
        await client.get_info(InfoEnum.SOFTVERSION)


# ---------------------------------------------------------------------------
# Coverage gap: _encode_image rejects images wider than 1992px
# ---------------------------------------------------------------------------


async def test_encode_image_width_exceeds_limit(make_client):
    """_encode_image must raise PrinterException when the image width exceeds
    the protocol limit of (255-6)*8 = 1992 pixels."""
    client = make_client()

    # 1993px is one pixel over the 1992px limit
    oversized = Image.new("1", (1993, 50), color=0)

    with pytest.raises(PrinterException, match="exceeds protocol limit"):
        # _encode_image is a generator; must consume it to trigger the check
        list(client._encode_image(oversized))


# ---------------------------------------------------------------------------
# Coverage gap: print status poll exits when page > quantity (>= fix)
# ---------------------------------------------------------------------------


async def test_print_job_status_poll_greater_than(make_client):
    """When get_print_status returns page=2 but quantity=1, the >= comparison
    must still cause the poll to exit (tests the >= fix vs. == bug)."""
    client = make_client()

    call_count = 0

    # Track which command is being sent to return the right mock response
    async def fake_write(data, char_uuid):
        nonlocal call_count
        # Parse the outgoing packet to determine what command this is
        pkt = NiimbotPacket.from_bytes(data)

        if pkt.type == RequestCodeEnum.GET_PRINT_STATUS:
            call_count += 1
            # Return page=2 on the very first status check (overshoots qty=1)
            status_data = struct.pack(">HBB", 2, 100, 100)
            resp = NiimbotPacket(RequestCodeEnum.GET_PRINT_STATUS, status_data)
        elif pkt.type == RequestCodeEnum.END_PAGE_PRINT:
            resp = NiimbotPacket(RequestCodeEnum.END_PAGE_PRINT, b"\x01")
        else:
            # Generic success for all other commands (density, type, start, etc.)
            resp = NiimbotPacket(pkt.type, b"\x01")

        client.notification_data = resp.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (100, 50), color=0)
    await client.print_image(img, quantity=1)

    # The poll should have exited after a single status check (page 2 >= 1)
    assert call_count == 1


# ---------------------------------------------------------------------------
# Coverage gap: end_page_print timeout after 200 retries
# ---------------------------------------------------------------------------


@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_end_page_print_timeout(mock_sleep, make_client):
    """When end_page_print always returns False (data[0]==0), the 200-iteration
    retry loop must exhaust and raise PrinterException('end_page_print timed out')."""
    client = make_client()

    async def fake_write(data, char_uuid):
        pkt = NiimbotPacket.from_bytes(data)

        if pkt.type == RequestCodeEnum.END_PAGE_PRINT:
            # Return False (data[0] == 0) every time
            resp = NiimbotPacket(RequestCodeEnum.END_PAGE_PRINT, b"\x00")
        elif pkt.type == 0x85:
            # Image data — write_raw doesn't use notifications
            return
        else:
            # Generic success for setup commands
            resp = NiimbotPacket(pkt.type, b"\x01")

        client.notification_data = resp.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (100, 50), color=0)
    with pytest.raises(PrinterException, match="end_page_print timed out"):
        await client.print_image(img, quantity=1)


# ---------------------------------------------------------------------------
# Coverage gap: status poll timeout after max_status_checks retries
# ---------------------------------------------------------------------------


@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_status_poll_timeout(mock_sleep, make_client):
    """When get_print_status always returns page=0 while quantity=1, the 600-
    iteration poll loop must exhaust and raise PrinterException about status
    timeout."""
    client = make_client()

    async def fake_write(data, char_uuid):
        pkt = NiimbotPacket.from_bytes(data)

        if pkt.type == RequestCodeEnum.END_PAGE_PRINT:
            # Return True so the end_page_print loop succeeds
            resp = NiimbotPacket(RequestCodeEnum.END_PAGE_PRINT, b"\x01")
        elif pkt.type == RequestCodeEnum.GET_PRINT_STATUS:
            # Always return page=0 — never reaches quantity
            status_data = struct.pack(">HBB", 0, 0, 0)
            resp = NiimbotPacket(RequestCodeEnum.GET_PRINT_STATUS, status_data)
        elif pkt.type == 0x85:
            return
        else:
            resp = NiimbotPacket(pkt.type, b"\x01")

        client.notification_data = resp.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (100, 50), color=0)
    with pytest.raises(PrinterException, match="Print status timeout: page 0/1"):
        await client.print_image(img, quantity=1)


# ---------------------------------------------------------------------------
# Coverage gap: cleanup skips end_print when transport is disconnected
# ---------------------------------------------------------------------------


@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_print_job_cleanup_skips_reconnect_when_disconnected(mock_sleep, make_client):
    """When the transport is disconnected during cleanup (after a print failure),
    the except handler must skip the end_print call instead of attempting
    reconnection."""
    client = make_client()

    end_print_called = False
    end_page_count = 0

    async def fake_write(data, char_uuid):
        nonlocal end_print_called, end_page_count
        pkt = NiimbotPacket.from_bytes(data)

        if pkt.type == RequestCodeEnum.END_PAGE_PRINT:
            end_page_count += 1
            # Return False (data[0]==0) every time to exhaust the retry loop.
            # On the last iteration, mark transport as disconnected so the
            # cleanup guard (except BaseException) sees is_connected=False.
            if end_page_count >= 200:
                client.transport.client.is_connected = False
            resp = NiimbotPacket(RequestCodeEnum.END_PAGE_PRINT, b"\x00")
        elif pkt.type == RequestCodeEnum.END_PRINT:
            end_print_called = True
            resp = NiimbotPacket(RequestCodeEnum.END_PRINT, b"\x01")
        elif pkt.type == 0x85:
            # Image data — write_raw doesn't use notifications
            return
        else:
            # Generic success for setup commands
            resp = NiimbotPacket(pkt.type, b"\x01")

        client.notification_data = resp.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (100, 50), color=0)
    with pytest.raises(PrinterException, match="end_page_print timed out"):
        await client.print_image(img, quantity=1)

    # end_print should NOT have been called because is_connected was False
    assert not end_print_called
