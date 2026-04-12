import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from NiimPrintX.nimmy.printer import PrinterClient

# ---------------------------------------------------------------------------
# Shared helper: build a fake_write side-effect for transport.write
# ---------------------------------------------------------------------------


def make_fake_write(client, response_pkt):
    """Return an async side-effect suitable for ``transport.write``.

    When called, the coroutine sets ``client.notification_data`` to the
    serialised *response_pkt* and fires ``client.notification_event`` so
    that ``send_command`` unblocks with the expected response.

    Usage::

        from tests.conftest import make_fake_write

        client = make_client()
        pkt = NiimbotPacket(RequestCodeEnum.GET_INFO, b"\\x01")
        client.transport.write = AsyncMock(side_effect=make_fake_write(client, pkt))
    """

    async def _fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    return _fake_write


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def small_image():
    """Create a small test image for D-series printers (240px wide)."""
    return Image.new("1", (240, 100), color=0)


@pytest.fixture
def wide_image():
    """Create a wider test image for B-series printers (384px wide)."""
    return Image.new("1", (384, 200), color=0)


@pytest.fixture
def make_client():
    """Factory fixture for creating mock PrinterClient instances.

    Returns a callable that builds a PrinterClient with a fully mocked
    BLE device and transport, suitable for both sync and async tests.
    """

    def _make_client():
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
        try:
            client._loop = asyncio.get_running_loop()
        except RuntimeError:
            client._loop = None  # sync tests don't need the event loop
        return client

    return _make_client
