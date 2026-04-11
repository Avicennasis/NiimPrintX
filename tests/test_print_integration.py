import asyncio
import struct
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
from NiimPrintX.nimmy.printer import PrinterClient, RequestCodeEnum
from NiimPrintX.nimmy.packet import NiimbotPacket


def _make_client():
    """Create a PrinterClient with a mocked transport for integration testing."""
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
    client.char_uuid = "test-uuid"
    client.notification_event = asyncio.Event()
    client.notification_data = None
    client._command_lock = asyncio.Lock()
    client._print_lock = asyncio.Lock()
    return client


def _auto_respond(client):
    """Set up transport.write to auto-respond with success packets.

    Commands sent through send_command() get a notification response so the
    notification_event is set and send_command can proceed.  Image-data
    packets (type 0x85) are written directly by print_image and do NOT go
    through send_command, so they need no notification response.
    """
    commands_sent = []

    async def fake_write(data, char_uuid):
        # Parse the outgoing packet to determine its type
        pkt = NiimbotPacket.from_bytes(data)
        commands_sent.append(pkt.type)

        # Image data rows are written directly (not via send_command),
        # so no notification response is needed.
        if pkt.type == 0x85:
            return

        # For command packets, generate an appropriate response so that
        # send_command's notification_event wait completes.
        response_type = pkt.type
        if pkt.type == RequestCodeEnum.GET_PRINT_STATUS:
            # Return "done" status: page=1, progress1=100, progress2=100
            response_data = struct.pack(">HBB", 1, 100, 100)
        else:
            # Generic success byte
            response_data = b"\x01"

        response_pkt = NiimbotPacket(response_type, response_data)
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    return commands_sent


@pytest.mark.asyncio
async def test_print_image_sends_correct_command_sequence():
    """print_image should send commands in the correct order."""
    client = _make_client()
    commands = _auto_respond(client)

    img = Image.new("L", (16, 4), color=128)
    await client.print_image(img, density=3, quantity=1)

    # Verify command sequence:
    #   density, label_type, start, start_page, dimension, quantity,
    #   [image data rows], end_page, status, end
    assert RequestCodeEnum.SET_LABEL_DENSITY in commands
    assert RequestCodeEnum.SET_LABEL_TYPE in commands
    assert RequestCodeEnum.START_PRINT in commands
    assert RequestCodeEnum.START_PAGE_PRINT in commands
    assert RequestCodeEnum.SET_DIMENSION in commands
    assert RequestCodeEnum.SET_QUANTITY in commands
    assert RequestCodeEnum.END_PAGE_PRINT in commands
    assert RequestCodeEnum.GET_PRINT_STATUS in commands
    assert RequestCodeEnum.END_PRINT in commands
    # Image data packets (0x85) should be present -- one per row
    assert commands.count(0x85) == 4  # 4 rows


@pytest.mark.asyncio
async def test_print_image_command_ordering():
    """Commands must appear in the protocol-required order."""
    client = _make_client()
    commands = _auto_respond(client)

    img = Image.new("L", (16, 4), color=128)
    await client.print_image(img, density=3, quantity=1)

    density_idx = commands.index(RequestCodeEnum.SET_LABEL_DENSITY)
    label_type_idx = commands.index(RequestCodeEnum.SET_LABEL_TYPE)
    start_idx = commands.index(RequestCodeEnum.START_PRINT)
    start_page_idx = commands.index(RequestCodeEnum.START_PAGE_PRINT)
    dimension_idx = commands.index(RequestCodeEnum.SET_DIMENSION)
    quantity_idx = commands.index(RequestCodeEnum.SET_QUANTITY)
    first_image_idx = commands.index(0x85)
    end_page_idx = commands.index(RequestCodeEnum.END_PAGE_PRINT)
    status_idx = commands.index(RequestCodeEnum.GET_PRINT_STATUS)
    end_idx = commands.index(RequestCodeEnum.END_PRINT)

    assert density_idx < start_idx
    assert label_type_idx < start_idx
    assert start_idx < start_page_idx
    assert start_page_idx < dimension_idx
    assert dimension_idx < quantity_idx
    assert quantity_idx < first_image_idx
    assert first_image_idx < end_page_idx
    assert end_page_idx < status_idx
    assert status_idx < end_idx


@pytest.mark.asyncio
async def test_print_image_v2_sends_correct_commands():
    """print_imageV2 should use V2 start/dimension commands and end with status polling + end_print."""
    client = _make_client()

    # Custom auto-respond that returns page=2 for status (matching quantity=2)
    commands_sent = []

    async def fake_write(data, char_uuid):
        pkt = NiimbotPacket.from_bytes(data)
        commands_sent.append(pkt.type)
        if pkt.type == 0x85:
            return
        response_type = pkt.type
        if pkt.type == RequestCodeEnum.GET_PRINT_STATUS:
            response_data = struct.pack(">HBB", 2, 100, 100)
        else:
            response_data = b"\x01"
        response_pkt = NiimbotPacket(response_type, response_data)
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("L", (16, 4), color=128)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_imageV2(img, density=3, quantity=2)

    assert RequestCodeEnum.SET_LABEL_DENSITY in commands_sent
    assert RequestCodeEnum.SET_LABEL_TYPE in commands_sent
    assert RequestCodeEnum.START_PRINT in commands_sent  # start_printV2 uses same code
    assert RequestCodeEnum.START_PAGE_PRINT in commands_sent
    assert RequestCodeEnum.SET_DIMENSION in commands_sent  # set_dimensionV2 uses same code
    assert 0x85 in commands_sent  # image data
    assert RequestCodeEnum.END_PAGE_PRINT in commands_sent
    # V2 now calls status polling and end_print (matching print_image behavior)
    assert RequestCodeEnum.GET_PRINT_STATUS in commands_sent
    assert RequestCodeEnum.END_PRINT in commands_sent
    # V2 does NOT call set_quantity (quantity is passed via start_printV2 and set_dimensionV2)
    assert RequestCodeEnum.SET_QUANTITY not in commands_sent


@pytest.mark.asyncio
async def test_print_image_small_image():
    """Printing a 1x1 image should work without errors."""
    client = _make_client()
    commands = _auto_respond(client)

    img = Image.new("L", (8, 1), color=0)
    await client.print_image(img, density=1, quantity=1)

    # Should have exactly 1 image data row
    assert commands.count(0x85) == 1


@pytest.mark.asyncio
async def test_print_image_with_offsets():
    """Printing with offsets should not crash."""
    client = _make_client()
    _auto_respond(client)

    img = Image.new("L", (16, 8), color=128)
    await client.print_image(img, density=2, quantity=1, vertical_offset=5, horizontal_offset=3)
    # No exception means success
