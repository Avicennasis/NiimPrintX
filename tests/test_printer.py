import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from NiimPrintX.nimmy.exception import PrinterException
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import InfoEnum, RequestCodeEnum


@pytest.mark.asyncio
async def test_send_command_clears_event_before_wait(make_client):
    """notification_event must be cleared before waiting, not just after."""
    client = make_client()
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
async def test_send_command_catches_valueerror_from_malformed_packet(make_client):
    """ValueError from from_bytes must be wrapped as PrinterException."""
    client = make_client()

    async def fake_write(data, char_uuid):
        # Simulate a corrupted response (bad header)
        client.notification_data = b"\xDE\xAD\x40\x01\x01\x40\xAA\xAA"
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    with pytest.raises(PrinterException, match="Malformed"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")


@pytest.mark.asyncio
async def test_heartbeat_case_10_no_rfid(make_client):
    """10-byte heartbeat should not set rfid_read_state (only 2 useful fields)."""
    client = make_client()
    hb_data = bytes(10)
    response_pkt = NiimbotPacket(RequestCodeEnum.HEARTBEAT, hb_data)

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.heartbeat()
    assert result["closing_state"] == hb_data[8]
    assert result["power_level"] == hb_data[9]
    assert result["rfid_read_state"] is None


@pytest.mark.asyncio
async def test_send_command_timeout_raises_printer_exception(make_client):
    """Timeout must be wrapped as PrinterException."""
    client = make_client()
    # Never set the event — will timeout
    with pytest.raises(PrinterException, match="timed out"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01", timeout=0.1)


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_heartbeat_case_13(make_client):
    """13-byte heartbeat extracts closing_state, power, paper, and rfid."""
    client = make_client()
    hb_data = bytearray(13)
    hb_data[9] = 0x01   # closing_state
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_set_label_type_invalid_raises(make_client):
    """set_label_type(0) must raise ValueError (valid range is 1-3)."""
    client = make_client()
    with pytest.raises(ValueError, match="Label type must be 1-3"):
        await client.set_label_type(0)


@pytest.mark.asyncio
async def test_set_label_density_invalid_raises(make_client):
    """set_label_density(6) must raise ValueError (valid range is 1-5)."""
    client = make_client()
    with pytest.raises(ValueError, match="Label density must be 1-5"):
        await client.set_label_density(6)


@pytest.mark.asyncio
async def test_start_printV2_quantity_validation(make_client):
    """start_printV2(quantity=-1) must raise ValueError."""
    client = make_client()
    with pytest.raises(ValueError, match="Quantity must be 1-65535"):
        await client.start_printV2(quantity=-1)


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_get_rfid_empty_data_returns_none(make_client):
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, b'\x00')

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_rfid()
    assert result is None


@pytest.mark.asyncio
async def test_get_rfid_valid_data(make_client):
    client = make_client()
    uuid = b'\x01\x02\x03\x04\x05\x06\x07\x08'
    barcode = b'BC123'
    serial = b'SN456'
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


@pytest.mark.asyncio
async def test_get_rfid_malformed_returns_none(make_client):
    """Truncated RFID data should return None, not crash."""
    client = make_client()
    # Valid start but truncated — will cause IndexError in parsing
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_RFID, b'\x01\x02\x03')

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.get_rfid()
    assert result is None


@pytest.mark.asyncio
async def test_set_quantity(make_client):
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.SET_QUANTITY, b'\x01')

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.set_quantity(5)
    assert result is True


@pytest.mark.asyncio
async def test_end_print(make_client):
    client = make_client()
    response_pkt = NiimbotPacket(RequestCodeEnum.END_PRINT, b'\x01')

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    result = await client.end_print()
    assert result is True


@pytest.mark.asyncio
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
