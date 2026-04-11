from unittest.mock import MagicMock
from PIL import Image
from NiimPrintX.nimmy.printer import PrinterClient


def _make_client():
    """Create a PrinterClient without connecting to any device."""
    client = PrinterClient.__new__(PrinterClient)
    # Stub transport so __del__ does not raise when teardown fires
    transport = MagicMock()
    transport.client.is_connected = False
    client.transport = transport
    return client


def test_encode_image_produces_packets(small_image):
    """Image encoding should produce one packet per row."""
    client = _make_client()
    packets = list(client._encode_image(small_image))
    assert len(packets) == small_image.height


def test_encode_image_with_vertical_offset(small_image):
    """Vertical offset should produce additional packets."""
    client = _make_client()
    packets_no_offset = list(client._encode_image(small_image, vertical_offset=0))
    packets_with_offset = list(client._encode_image(small_image, vertical_offset=10))
    assert len(packets_with_offset) == len(packets_no_offset) + 10


def test_encode_image_wide(wide_image):
    """Wide images (B-series) should also encode correctly."""
    client = _make_client()
    packets = list(client._encode_image(wide_image))
    assert len(packets) == wide_image.height
