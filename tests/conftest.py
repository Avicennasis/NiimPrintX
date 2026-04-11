import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from PIL import Image

from NiimPrintX.nimmy.printer import PrinterClient


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
            client._loop = asyncio.new_event_loop()
        return client

    return _make_client
