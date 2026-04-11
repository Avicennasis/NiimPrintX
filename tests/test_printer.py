import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from NiimPrintX.nimmy.printer import PrinterClient, RequestCodeEnum
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.exception import PrinterException


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
async def test_heartbeat_case_10_no_rfid():
    """10-byte heartbeat should not set rfid_read_state (only 2 useful fields)."""
    client = _make_client()
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
async def test_send_command_timeout_raises_printer_exception():
    """Timeout must be wrapped as PrinterException."""
    client = _make_client()
    # Never set the event — will timeout
    with pytest.raises(PrinterException, match="timed out"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01", timeout=0.1)
