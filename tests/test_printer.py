import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from NiimPrintX.cli.command import niimbot_cli
from NiimPrintX.nimmy.exception import PrinterException
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import RequestCodeEnum


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


def _build_heartbeat_data(size, offsets):
    """Build a bytearray of the given size with specific byte offsets set."""
    hb_data = bytearray(size)
    for idx, val in offsets.items():
        hb_data[idx] = val
    return bytes(hb_data)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(
            _build_heartbeat_data(9, {8: 0x01}),
            {"closing_state": 0x01, "power_level": None, "paper_state": None, "rfid_read_state": None},
            id="case_9",
        ),
        pytest.param(
            _build_heartbeat_data(10, {8: 0x05, 9: 0x64}),
            {"closing_state": 0x05, "power_level": 0x64, "paper_state": None, "rfid_read_state": None},
            id="case_10",
        ),
        pytest.param(
            _build_heartbeat_data(13, {9: 0x01, 10: 0x64, 11: 0x0A, 12: 0x0B}),
            {"closing_state": 0x01, "power_level": 0x64, "paper_state": 0x0A, "rfid_read_state": 0x0B},
            id="case_13",
        ),
        pytest.param(
            _build_heartbeat_data(19, {15: 0x01, 16: 0x50, 17: 0x0C, 18: 0x0D}),
            {"closing_state": 0x01, "power_level": 0x50, "paper_state": 0x0C, "rfid_read_state": 0x0D},
            id="case_19",
        ),
        pytest.param(
            _build_heartbeat_data(20, {18: 0x02, 19: 0x03}),
            {"closing_state": None, "power_level": None, "paper_state": 0x02, "rfid_read_state": 0x03},
            id="case_20",
        ),
    ],
)
async def test_heartbeat_parsing(data, expected, make_client):
    """Heartbeat responses of different lengths parse into the correct state fields."""
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, data)

    async def fake_write(raw, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result == expected


async def test_send_command_timeout_raises_printer_exception(make_client):
    """Timeout must be wrapped as PrinterException."""
    client = make_client()
    # Never set the event — will timeout
    with pytest.raises(PrinterException, match="timed out"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01", timeout=0.1)


async def test_set_label_type_invalid_raises(make_client):
    """set_label_type(0) must raise PrinterException (valid range is 1-3)."""
    client = make_client()
    with pytest.raises(PrinterException, match="Label type must be 1-3"):
        await client.set_label_type(0)


async def test_set_label_density_invalid_raises(make_client):
    """set_label_density(6) must raise PrinterException (valid range is 1-5)."""
    client = make_client()
    with pytest.raises(PrinterException, match="Label density must be 1-5"):
        await client.set_label_density(6)


async def test_start_print_v2_quantity_validation(make_client):
    """start_print_v2(quantity=-1) must raise PrinterException."""
    client = make_client()
    with pytest.raises(PrinterException, match="Quantity must be 1-65535"):
        await client.start_print_v2(quantity=-1)


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
    """When BLETransport.connect() succeeds and find_characteristics sets
    char_uuid, connect() should complete without error and _loop should be set."""
    client = make_client()
    client.char_uuid = None  # Force the find_characteristics path

    client.transport.connect = AsyncMock(return_value=None)

    # Build a mock service with a single characteristic that has the right props
    char = MagicMock()
    char.uuid = "0000ae01-0000-1000-8000-00805f9b34fb"
    char.handle = 1
    char.properties = ["read", "write-without-response", "notify"]

    service = MagicMock()
    service.uuid = "0000ae00-0000-1000-8000-00805f9b34fb"
    service.characteristics = [char]

    client.transport.client.services = [service]

    await client.connect()  # should not raise

    assert client.char_uuid == char.uuid
    assert client._loop is not None


# ---------------------------------------------------------------------------
# Coverage gap: connect() failure cleans up
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Coverage gap: notification_handler sets data via call_soon_threadsafe
# ---------------------------------------------------------------------------


async def test_notification_handler_sets_data(make_client):
    """notification_handler should schedule _set via call_soon_threadsafe,
    which sets notification_data and fires the event when expecting a response."""
    client = make_client()
    client._expecting_response = True  # simulate command in flight

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


async def test_notification_handler_drops_unsolicited(make_client):
    """Unsolicited notifications (no command in flight) should be dropped."""
    client = make_client()
    client._expecting_response = False  # no command waiting

    mock_loop = MagicMock()
    callbacks = []
    mock_loop.call_soon_threadsafe = MagicMock(side_effect=callbacks.append)
    client._loop = mock_loop

    sender = MagicMock()
    client.notification_handler(sender, b"\xff\xee")

    mock_loop.call_soon_threadsafe.assert_called_once()
    callbacks[0]()
    # Data should NOT be set
    assert client.notification_data is None
    assert not client.notification_event.is_set()


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
# Coverage gap: print_image_v2 with zero-dimension offset
# ---------------------------------------------------------------------------


async def test_print_image_v2_zero_dimension(make_client):
    """When negative horizontal_offset equals the image width, effective_width
    becomes 0 and print_image_v2 must raise PrinterException (mirroring the
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
        await client.print_image_v2(img, horizontal_offset=-100)


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
# Boundary validation: set_dimension height/width and set_quantity
# ---------------------------------------------------------------------------


async def test_set_dimension_height_zero_raises(make_client):
    """set_dimension(0, 100) must raise PrinterException before sending."""
    client = make_client()
    with pytest.raises(PrinterException, match="Height must be 1-65535"):
        await client.set_dimension(0, 100)


async def test_set_dimension_height_overflow_raises(make_client):
    """set_dimension(65536, 100) must raise PrinterException before sending."""
    client = make_client()
    with pytest.raises(PrinterException, match="Height must be 1-65535"):
        await client.set_dimension(65536, 100)


async def test_set_dimension_width_zero_raises(make_client):
    """set_dimension(100, 0) must raise PrinterException before sending."""
    client = make_client()
    with pytest.raises(PrinterException, match="Width must be 1-65535"):
        await client.set_dimension(100, 0)


async def test_set_dimension_width_overflow_raises(make_client):
    """set_dimension(100, 65536) must raise PrinterException before sending."""
    client = make_client()
    with pytest.raises(PrinterException, match="Width must be 1-65535"):
        await client.set_dimension(100, 65536)


async def test_set_quantity_zero_raises(make_client):
    """set_quantity(0) must raise PrinterException before sending."""
    client = make_client()
    with pytest.raises(PrinterException, match="Quantity must be 1-65535"):
        await client.set_quantity(0)


async def test_set_quantity_overflow_raises(make_client):
    """set_quantity(65536) must raise PrinterException before sending."""
    client = make_client()
    with pytest.raises(PrinterException, match="Quantity must be 1-65535"):
        await client.set_quantity(65536)


# ---------------------------------------------------------------------------
# CLI width validation: d11_h model (354px max)
# ---------------------------------------------------------------------------


def test_cli_rejects_354px_width_for_d11_h(runner):
    """An image wider than 354px should be rejected for d11_h."""
    with runner.isolated_filesystem():
        Image.new("RGB", (355, 100)).save("too_wide.png")
        result = runner.invoke(
            niimbot_cli,
            ["print", "-m", "d11_h", "-i", "too_wide.png"],
        )
        assert result.exit_code != 0
        assert "exceeds" in result.output.lower() or "width" in result.output.lower()


def test_cli_accepts_354px_width_for_d11_h(runner):
    """An image exactly 354px wide should be accepted for d11_h."""
    device = MagicMock()
    device.name = "TestPrinter"
    printer = AsyncMock()
    printer.connect.return_value = True
    printer.disconnect.return_value = None
    printer.print_image.return_value = None

    with runner.isolated_filesystem():
        Image.new("RGB", (354, 100)).save("exact.png")
        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
        ):
            result = runner.invoke(
                niimbot_cli,
                ["print", "-m", "d11_h", "-i", "exact.png"],
            )
            assert result.exit_code == 0


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


# ---------------------------------------------------------------------------
# P1 gap: _encode_image effective-width overflow after positive horizontal_offset
# ---------------------------------------------------------------------------


def test_encode_image_positive_offset_exceeds_width_limit(make_client):
    """Positive horizontal_offset pushing effective width past 1992px must raise."""
    client = make_client()
    img = Image.new("L", (1984, 4), color=0)  # 1984 alone is fine
    with pytest.raises(PrinterException, match="exceeds protocol limit"):
        list(client._encode_image(img, horizontal_offset=16))  # 1984+16=2000 > 1992


# ---------------------------------------------------------------------------
# P1 gap: _encode_image effective-height overflow (height + offset > 65535)
# ---------------------------------------------------------------------------


def test_encode_image_height_plus_offset_exceeds_limit(make_client):
    """Vertical offset pushing effective height past 65535 must raise."""
    client = make_client()
    img = Image.new("1", (8, 65530), color=0)
    with pytest.raises(PrinterException, match="exceeds protocol limit"):
        list(client._encode_image(img, vertical_offset=10))


# ---------------------------------------------------------------------------
# P1 gap: send_command when char_uuid is None
# ---------------------------------------------------------------------------


async def test_send_command_no_char_uuid_raises(make_client):
    """send_command with char_uuid=None must raise PrinterException."""
    client = make_client()
    client.char_uuid = None
    client.transport.client = MagicMock()
    client.transport.client.is_connected = True
    with pytest.raises(PrinterException, match="No characteristic UUID available"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")


# ---------------------------------------------------------------------------
# P1 gap: _print_job cleanup when page_started=False (skips end_page_print)
# ---------------------------------------------------------------------------


@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_print_job_cleanup_skips_end_page_when_not_started(mock_sleep, make_client):
    """When start_page_print fails, the except handler must NOT call
    end_page_print (page_started is still False)."""
    client = make_client()

    end_page_called = False
    end_print_called = False

    async def fake_write(data, char_uuid):
        nonlocal end_page_called, end_print_called
        pkt = NiimbotPacket.from_bytes(data)

        if pkt.type == RequestCodeEnum.START_PAGE_PRINT:
            raise PrinterException("Simulated START_PAGE_PRINT failure")
        if pkt.type == RequestCodeEnum.END_PAGE_PRINT:
            end_page_called = True
            resp = NiimbotPacket(RequestCodeEnum.END_PAGE_PRINT, b"\x01")
        elif pkt.type == RequestCodeEnum.END_PRINT:
            end_print_called = True
            resp = NiimbotPacket(RequestCodeEnum.END_PRINT, b"\x01")
        else:
            resp = NiimbotPacket(pkt.type, b"\x01")

        client.notification_data = resp.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (100, 50), color=0)
    with pytest.raises(PrinterException, match="Simulated START_PAGE_PRINT failure"):
        await client.print_image(img, quantity=1)

    # end_page_print should NOT have been called because page_started was False
    assert not end_page_called
    # end_print SHOULD have been called because print_started was True
    assert end_print_called


# ---------------------------------------------------------------------------
# P2 gap: notification_handler idempotency (second call ignored)
# ---------------------------------------------------------------------------


async def test_notification_handler_second_call_is_noop(make_client):
    """Second notification while first is pending should be discarded."""
    client = make_client()
    client._expecting_response = True  # simulate command in flight

    mock_loop = MagicMock()
    callbacks = []
    mock_loop.call_soon_threadsafe = MagicMock(side_effect=callbacks.append)
    client._loop = mock_loop

    # Simulate first notification
    client.notification_handler(MagicMock(), bytearray(b"\x01\x02"))
    # Execute the first callback — sets data and event
    assert len(callbacks) == 1
    callbacks[0]()
    first_data = client.notification_data

    # Simulate second notification (event is already set, so _set is a noop)
    client.notification_handler(MagicMock(), bytearray(b"\x03\x04"))
    assert len(callbacks) == 2
    callbacks[1]()
    assert client.notification_data == first_data


# ---------------------------------------------------------------------------
# P2 gap: set_label_type upper bound / set_label_density lower bound
# ---------------------------------------------------------------------------


async def test_set_label_type_upper_bound_invalid(make_client):
    """set_label_type(4) must raise PrinterException (valid range is 1-3)."""
    client = make_client()
    with pytest.raises(PrinterException, match="Label type must be 1-3"):
        await client.set_label_type(4)


async def test_set_label_density_lower_bound_invalid(make_client):
    """set_label_density(0) must raise PrinterException (valid range is 1-5)."""
    client = make_client()
    with pytest.raises(PrinterException, match="Label density must be 1-5"):
        await client.set_label_density(0)


# ---------------------------------------------------------------------------
# Final hardening: find_characteristics multiple matches
# ---------------------------------------------------------------------------


async def test_find_characteristics_multiple_matches_uses_first(make_client):
    """When multiple characteristics match, the first UUID should be used and
    a warning should be logged about the extra matches."""
    client = make_client()
    char1 = MagicMock(uuid="uuid-1", handle=1, properties=["read", "write-without-response", "notify"])
    char2 = MagicMock(uuid="uuid-2", handle=2, properties=["read", "write-without-response", "notify"])
    service = MagicMock(characteristics=[char1, char2])
    service.uuid = "svc-uuid"
    client.transport.client.services = [service]
    with patch("NiimPrintX.nimmy.printer.logger") as mock_logger:
        await client.find_characteristics()
    assert client.char_uuid == "uuid-1"
    mock_logger.warning.assert_called_once()
    assert "Multiple matching characteristics" in mock_logger.warning.call_args[0][0]


# ---------------------------------------------------------------------------
# Final hardening: disconnect calls stop_notification with correct char_uuid
# ---------------------------------------------------------------------------


async def test_disconnect_uses_char_uuid_for_stop_notification(make_client):
    """disconnect() must pass the current char_uuid to stop_notification before clearing it."""
    client = make_client()
    client.char_uuid = "original-uuid"

    stop_uuids = []

    async def tracking_stop(uuid):
        stop_uuids.append(uuid)

    client.transport.stop_notification = tracking_stop
    client.transport.disconnect = AsyncMock()

    await client.disconnect()

    assert len(stop_uuids) == 1
    assert stop_uuids[0] == "original-uuid"
    # char_uuid should be cleared after disconnect
    assert client.char_uuid is None


# ---------------------------------------------------------------------------
# Final hardening: disconnect clears char_uuid (regression prevention)
# ---------------------------------------------------------------------------


async def test_disconnect_behavior(make_client):
    """disconnect must clear char_uuid."""
    client = make_client()
    client.char_uuid = "test-uuid"
    client.transport.disconnect = AsyncMock()
    await client.disconnect()
    assert client.char_uuid is None


# ---------------------------------------------------------------------------
# disconnect() notification lifecycle
# ---------------------------------------------------------------------------


async def test_disconnect_calls_stop_notification(make_client):
    """disconnect() should call stop_notification before transport.disconnect."""
    client = make_client()
    client.char_uuid = "test-uuid"
    client.transport.disconnect = AsyncMock()
    await client.disconnect()
    client.transport.stop_notification.assert_awaited_once_with("test-uuid")
    client.transport.disconnect.assert_awaited_once()


async def test_disconnect_skips_stop_when_no_char_uuid(make_client):
    """disconnect() with no char_uuid should skip stop_notification."""
    client = make_client()
    client.char_uuid = None
    client.transport.disconnect = AsyncMock()
    await client.disconnect()
    client.transport.stop_notification.assert_not_awaited()
