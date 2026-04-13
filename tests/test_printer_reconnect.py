"""Tests covering printer reconnect, BLE error wrapping, and transport idempotency."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from NiimPrintX.nimmy.bluetooth import BLETransport
from NiimPrintX.nimmy.exception import PrinterException
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import RequestCodeEnum

# ---------------------------------------------------------------------------
# 1. send_command reconnects when disconnected, then succeeds
# ---------------------------------------------------------------------------


async def test_send_command_reconnect_success(make_client):
    """When the BLE client reports disconnected, send_command should attempt
    reconnection via client.connect().  If connect succeeds the command
    should complete normally."""
    client = make_client()
    client.transport.client.is_connected = False

    # Build a valid GET_INFO response
    response_pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, b"\x42")
    response_bytes = response_pkt.to_bytes()

    async def fake_write(data, char_uuid):
        client.notification_data = response_bytes
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    # Mock connect() on the PrinterClient (not the transport) to restore
    # the connected state, matching the code path in send_command line 107.
    async def fake_connect():
        client.transport.client.is_connected = True
        client.char_uuid = "test-char-uuid"
        return True

    client.connect = AsyncMock(side_effect=fake_connect)

    result = await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")

    client.connect.assert_awaited_once()
    assert result.data == b"\x42"


# ---------------------------------------------------------------------------
# 2. send_command reconnect failure raises PrinterException
# ---------------------------------------------------------------------------


async def test_send_command_reconnect_failure(make_client):
    """When the BLE client is disconnected and reconnection leaves char_uuid unset,
    send_command must raise PrinterException about missing characteristic UUID."""
    client = make_client()
    client.transport.client.is_connected = False
    client.char_uuid = None  # connect() won't restore it

    async def fake_connect():
        client.transport.client.is_connected = True

    client.connect = AsyncMock(side_effect=fake_connect)

    with pytest.raises(PrinterException, match="No characteristic UUID available"):
        await client.send_command(RequestCodeEnum.GET_INFO, b"\x01")


# ---------------------------------------------------------------------------
# 3. _print_job calls end_print on failure during end_page_print
# ---------------------------------------------------------------------------


async def test_print_job_calls_end_print_on_failure(make_client):
    """When end_page_print raises PrinterException mid-job, the cleanup
    block in _print_job must still call end_print."""
    client = make_client()

    call_log = []

    async def fake_write(data, char_uuid):
        pkt = NiimbotPacket.from_bytes(data)
        call_log.append(pkt.type)

        if pkt.type == 0x85:
            return

        if pkt.type == RequestCodeEnum.END_PAGE_PRINT:
            raise PrinterException("end_page_print hardware error")

        # Generic success for all other commands
        response_pkt = NiimbotPacket(pkt.type, b"\x01")
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("1", (16, 2), color=0)

    with (
        pytest.raises(PrinterException, match="end_page_print hardware error"),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await client.print_image(img, density=3, quantity=1)

    # end_print (0xF3) must appear in the call log after the failure,
    # proving the cleanup block executed.
    assert RequestCodeEnum.END_PRINT in call_log


# ---------------------------------------------------------------------------
# 5. start_notification is idempotent (same UUID only notifies once)
# ---------------------------------------------------------------------------


async def test_start_notification_idempotent():
    """Calling start_notification twice with the same UUID should only call
    client.start_notify once (the second call is a no-op)."""
    transport = BLETransport()

    mock_client = MagicMock()
    mock_client.is_connected = True
    mock_client.start_notify = AsyncMock()
    transport.client = mock_client

    uuid = "0000ae01-0000-1000-8000-00805f9b34fb"
    handler = MagicMock()

    await transport.start_notification(uuid, handler)
    await transport.start_notification(uuid, handler)

    mock_client.start_notify.assert_awaited_once_with(uuid, handler)
    assert uuid in transport._notifying_uuids


# ---------------------------------------------------------------------------
# 6. transport.connect() returns True without creating new client when
#    already connected to the same address
# ---------------------------------------------------------------------------


async def test_transport_already_connected_skips_new_client():
    """When the transport already has a connected client at the same address,
    connect() should complete without instantiating a new BleakClient."""
    transport = BLETransport()

    mock_client = MagicMock()
    mock_client.is_connected = True
    transport.client = mock_client
    transport.address = "AA:BB:CC:DD:EE:FF"

    with patch("NiimPrintX.nimmy.bluetooth.BleakClient") as MockBleakClient:
        await transport.connect("AA:BB:CC:DD:EE:FF")  # should not raise

    # BleakClient constructor should never have been called
    MockBleakClient.assert_not_called()
    # Original client should still be in place
    assert transport.client is mock_client
