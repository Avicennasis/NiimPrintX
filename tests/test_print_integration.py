import struct
from unittest.mock import AsyncMock, patch

from PIL import Image

from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import RequestCodeEnum


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
        response_data = struct.pack(">HBB", 1, 100, 100) if pkt.type == RequestCodeEnum.GET_PRINT_STATUS else b"\x01"

        response_pkt = NiimbotPacket(response_type, response_data)
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    return commands_sent


async def test_print_image_sends_correct_command_sequence(make_client):
    """print_image should send commands in the correct order."""
    client = make_client()
    commands = _auto_respond(client)

    img = Image.new("L", (16, 4), color=128)
    with patch("asyncio.sleep", new_callable=AsyncMock):
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


async def test_print_image_command_ordering(make_client):
    """Commands must appear in the protocol-required order."""
    client = make_client()
    commands = _auto_respond(client)

    img = Image.new("L", (16, 4), color=128)
    with patch("asyncio.sleep", new_callable=AsyncMock):
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


async def test_print_image_v2_sends_correct_commands(make_client):
    """print_imageV2 should use V2 start/dimension commands and end with status polling + end_print."""
    client = make_client()

    # Custom auto-respond that returns page=2 for status (matching quantity=2)
    commands_sent = []

    async def fake_write(data, char_uuid):
        pkt = NiimbotPacket.from_bytes(data)
        commands_sent.append(pkt.type)
        if pkt.type == 0x85:
            return
        response_type = pkt.type
        response_data = struct.pack(">HBB", 2, 100, 100) if pkt.type == RequestCodeEnum.GET_PRINT_STATUS else b"\x01"
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


async def test_print_image_small_image(make_client):
    """Printing a 1x1 image should work without errors."""
    client = make_client()
    commands = _auto_respond(client)

    img = Image.new("L", (8, 1), color=0)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_image(img, density=1, quantity=1)

    # Should have exactly 1 image data row
    assert commands.count(0x85) == 1


async def test_print_image_with_offsets(make_client):
    """Printing with offsets should send the correct number of 0x85 row packets."""
    client = make_client()
    commands = _auto_respond(client)

    img = Image.new("L", (16, 8), color=128)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_image(img, density=2, quantity=1, vertical_offset=5, horizontal_offset=3)

    # 8 image rows + 5 blank rows from vertical_offset = 13 total 0x85 packets
    assert commands.count(0x85) == 13


def _auto_respond_with_data(client, *, status_page=1):
    """Like _auto_respond but also tracks (type, data) tuples for payload inspection."""
    commands_sent = []  # list of (type, data) tuples

    async def fake_write(data, char_uuid):
        pkt = NiimbotPacket.from_bytes(data)
        commands_sent.append((pkt.type, pkt.data))

        if pkt.type == 0x85:
            return

        response_type = pkt.type
        response_data = (
            struct.pack(">HBB", status_page, 100, 100) if pkt.type == RequestCodeEnum.GET_PRINT_STATUS else b"\x01"
        )

        response_pkt = NiimbotPacket(response_type, response_data)
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    return commands_sent


async def test_print_imageV2_uses_v2_commands(make_client):
    """print_imageV2 should use V2 start/dimension format with quantity embedded in the payload."""
    client = make_client()
    commands = _auto_respond_with_data(client, status_page=2)

    img = Image.new("L", (16, 4), color=128)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_imageV2(img, density=3, quantity=2)

    types = [t for t, _ in commands]

    # V2 uses START_PRINT but with a different payload format
    assert RequestCodeEnum.START_PRINT in types

    # Find the START_PRINT payload -- V2 sends 7 bytes (0x00 + uint16 quantity + 4 zero bytes)
    start_cmds = [(t, d) for t, d in commands if t == RequestCodeEnum.START_PRINT]
    assert len(start_cmds) == 1
    start_data = start_cmds[0][1]
    assert len(start_data) == 7, f"V2 START_PRINT should send 7-byte payload, got {len(start_data)}"
    assert start_data[0] == 0x00, "V2 START_PRINT first byte should be 0x00"
    quantity_in_start = struct.unpack(">H", start_data[1:3])[0]
    assert quantity_in_start == 2

    # V2 uses SET_DIMENSION with 6-byte payload (height + width + copies)
    dim_cmds = [(t, d) for t, d in commands if t == RequestCodeEnum.SET_DIMENSION]
    assert len(dim_cmds) == 1
    dim_data = dim_cmds[0][1]
    assert len(dim_data) == 6, f"V2 SET_DIMENSION should send 6-byte payload, got {len(dim_data)}"
    height, width, copies = struct.unpack(">HHH", dim_data)
    assert height == 4
    assert width == 16
    assert copies == 2

    # V2 should NOT call SET_QUANTITY (quantity is embedded in V2 commands)
    assert RequestCodeEnum.SET_QUANTITY not in types


async def test_print_image_with_density(make_client):
    """print_image with density=5 should send SET_LABEL_DENSITY with value 5."""
    client = make_client()
    commands = _auto_respond_with_data(client)

    img = Image.new("L", (16, 4), color=128)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_image(img, density=5, quantity=1)

    types = [t for t, _ in commands]
    assert RequestCodeEnum.SET_LABEL_DENSITY in types

    density_cmds = [(t, d) for t, d in commands if t == RequestCodeEnum.SET_LABEL_DENSITY]
    assert len(density_cmds) == 1
    density_data = density_cmds[0][1]
    assert density_data == bytes((5,)), f"Expected density payload b'\\x05', got {density_data!r}"


async def test_print_image_with_quantity(make_client):
    """print_image with quantity=3 should send SET_QUANTITY with value 3."""
    client = make_client()
    commands = _auto_respond_with_data(client, status_page=3)

    img = Image.new("L", (16, 4), color=128)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_image(img, density=3, quantity=3)

    types = [t for t, _ in commands]
    assert RequestCodeEnum.SET_QUANTITY in types

    qty_cmds = [(t, d) for t, d in commands if t == RequestCodeEnum.SET_QUANTITY]
    assert len(qty_cmds) == 1
    qty_data = qty_cmds[0][1]
    quantity_sent = struct.unpack(">H", qty_data)[0]
    assert quantity_sent == 3, f"Expected quantity 3, got {quantity_sent}"
