"""End-to-end integration tests for the full print workflow.

These tests exercise print_image and print_image_v2 with mocked BLE transport,
verifying that all protocol methods are called in the correct order and that
failure recovery (end_print cleanup) works as expected.
"""

import struct
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from NiimPrintX.nimmy.exception import PrinterException
from NiimPrintX.nimmy.packet import NiimbotPacket
from NiimPrintX.nimmy.printer import RequestCodeEnum


def _auto_respond_tracking(client, *, status_page=1):
    """Set up transport.write to auto-respond and track command names in order.

    Returns a list that accumulates human-readable method names (matching the
    protocol step names from the spec) as each command is sent.
    """
    method_names = []

    # Map request codes to readable method names
    code_to_name = {
        RequestCodeEnum.SET_LABEL_DENSITY: "set_label_density",
        RequestCodeEnum.SET_LABEL_TYPE: "set_label_type",
        RequestCodeEnum.START_PRINT: "start_print",
        RequestCodeEnum.START_PAGE_PRINT: "start_page_print",
        RequestCodeEnum.SET_DIMENSION: "set_dimension",
        RequestCodeEnum.SET_QUANTITY: "set_quantity",
        RequestCodeEnum.END_PAGE_PRINT: "end_page_print",
        RequestCodeEnum.GET_PRINT_STATUS: "get_print_status",
        RequestCodeEnum.END_PRINT: "end_print",
    }

    async def fake_write(data, char_uuid):
        pkt = NiimbotPacket.from_bytes(data)

        if pkt.type == 0x85:
            method_names.append("write_raw")
            return

        # Distinguish V2 variants by payload length
        name = code_to_name.get(pkt.type, f"unknown_{pkt.type}")
        if pkt.type == RequestCodeEnum.START_PRINT and len(pkt.data) == 7:
            name = "start_print_v2"
        if pkt.type == RequestCodeEnum.SET_DIMENSION and len(pkt.data) == 6:
            name = "set_dimension_v2"

        method_names.append(name)

        response_type = pkt.type
        response_data = (
            struct.pack(">HBB", status_page, 100, 100) if pkt.type == RequestCodeEnum.GET_PRINT_STATUS else b"\x01"
        )
        response_pkt = NiimbotPacket(response_type, response_data)
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)
    return method_names


# ---------------------------------------------------------------------------
# Test 1: V1 print with rotation + offset
# ---------------------------------------------------------------------------


async def test_v1_print_with_rotation_and_offset(make_client):
    """V1 print_image with density=2, quantity=1, vertical_offset=5, horizontal_offset=3.

    Verify all protocol methods are called in the correct order:
    set_label_density -> set_label_type -> start_print -> start_page_print ->
    set_dimension -> set_quantity -> write_raw x N -> end_page_print ->
    get_print_status -> end_print
    """
    client = make_client()
    methods = _auto_respond_tracking(client)

    # Real 8x8 white PIL image
    img = Image.new("RGB", (8, 8), color=(255, 255, 255))

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_image(
            img,
            density=2,
            quantity=1,
            vertical_offset=5,
            horizontal_offset=3,
        )

    # The image is 8px wide + 3px horizontal_offset = 11px effective width
    # The image is 8px tall + 5px vertical_offset = 13 rows of image data
    expected_write_raw_count = 13

    # Build the expected ordered sequence (collapsing write_raw repetitions)
    expected_prefix = [
        "set_label_density",
        "set_label_type",
        "start_print",
        "start_page_print",
        "set_dimension",
        "set_quantity",
    ]
    expected_suffix = [
        "end_page_print",
        "get_print_status",
        "end_print",
    ]

    # Verify exact ordering: prefix, then N write_raws, then suffix
    assert methods[: len(expected_prefix)] == expected_prefix
    assert methods[-len(expected_suffix) :] == expected_suffix

    # All methods between prefix and suffix should be write_raw
    middle = methods[len(expected_prefix) : -len(expected_suffix)]
    assert all(m == "write_raw" for m in middle)
    assert len(middle) == expected_write_raw_count

    # Verify no V2 methods were used
    assert "start_print_v2" not in methods
    assert "set_dimension_v2" not in methods


# ---------------------------------------------------------------------------
# Test 2: V2 print with B21 model
# ---------------------------------------------------------------------------


async def test_v2_print_with_b21_model(make_client):
    """V2 print_image_v2 verifies start_print_v2 and set_dimension_v2 are used.

    Protocol order for V2:
    set_label_density -> set_label_type -> start_print_v2 -> start_page_print ->
    set_dimension_v2 -> write_raw x N -> end_page_print ->
    get_print_status -> end_print

    V2 does NOT call set_quantity (quantity is embedded in V2 commands).
    """
    client = make_client()
    methods = _auto_respond_tracking(client)

    # Real 8x8 white PIL image
    img = Image.new("RGB", (8, 8), color=(255, 255, 255))

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_image_v2(
            img,
            density=2,
            quantity=1,
            vertical_offset=5,
            horizontal_offset=3,
        )

    expected_write_raw_count = 13  # 8 rows + 5 vertical offset

    expected_prefix = [
        "set_label_density",
        "set_label_type",
        "start_print_v2",
        "start_page_print",
        "set_dimension_v2",
    ]
    expected_suffix = [
        "end_page_print",
        "get_print_status",
        "end_print",
    ]

    # Verify exact ordering
    assert methods[: len(expected_prefix)] == expected_prefix
    assert methods[-len(expected_suffix) :] == expected_suffix

    # All methods between prefix and suffix should be write_raw
    middle = methods[len(expected_prefix) : -len(expected_suffix)]
    assert all(m == "write_raw" for m in middle)
    assert len(middle) == expected_write_raw_count

    # V2 must NOT use set_quantity
    assert "set_quantity" not in methods

    # V2 must use the V2 variants, not V1
    assert "start_print" not in methods  # only start_print_v2
    assert "set_dimension" not in methods  # only set_dimension_v2


# ---------------------------------------------------------------------------
# Test 3: Print failure recovery -- end_print called on BLE error
# ---------------------------------------------------------------------------


async def test_print_failure_recovery_calls_end_print(make_client):
    """When write_raw raises a BLE error, end_print should still be called.

    The _print_job except handler calls end_print for cleanup when the
    transport is still connected. Verify this cleanup happens even when
    a write fails mid-job.
    """
    client = make_client()

    call_count = 0
    end_print_called = False

    async def fake_write(data, char_uuid):
        nonlocal call_count, end_print_called
        pkt = NiimbotPacket.from_bytes(data)

        if pkt.type == 0x85:
            # Fail on the first image data write to simulate BLE error
            raise PrinterException("BLE write failed: simulated transport error")

        if pkt.type == RequestCodeEnum.END_PRINT:
            end_print_called = True

        call_count += 1

        # Normal response for command packets
        response_type = pkt.type
        response_data = struct.pack(">HBB", 1, 100, 100) if pkt.type == RequestCodeEnum.GET_PRINT_STATUS else b"\x01"
        response_pkt = NiimbotPacket(response_type, response_data)
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    client.transport.write = AsyncMock(side_effect=fake_write)

    img = Image.new("RGB", (8, 8), color=(255, 255, 255))

    with pytest.raises(PrinterException, match="BLE write failed"), patch("asyncio.sleep", new_callable=AsyncMock):
        await client.print_image(img, density=2, quantity=1)

    # The except handler in _print_job should have called end_print for cleanup
    assert end_print_called, "end_print must be called for cleanup after a print failure"
