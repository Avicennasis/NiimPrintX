"""Tests for PrinterOperation — async connect/disconnect/print/heartbeat logic."""

from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from NiimPrintX.nimmy.exception import BLEException
from NiimPrintX.ui.widget.PrinterOperation import PrinterOperation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides):
    """Build minimal mock printer state for PrinterOperation."""
    printer = MagicMock()
    printer.printer_connected = overrides.get("printer_connected", False)
    printer.device = overrides.get("device", "d110")
    return printer


def _make_mock_printer():
    """Return a MagicMock pretending to be a PrinterClient with async methods."""
    printer = MagicMock()
    printer.connect = AsyncMock(return_value=True)
    printer.disconnect = AsyncMock()
    printer.heartbeat = AsyncMock(return_value={"status": "ok"})
    printer.print_image = AsyncMock()
    printer.print_image_v2 = AsyncMock()
    return printer


# ---------------------------------------------------------------------------
# 1. printer_connect — success
# ---------------------------------------------------------------------------


@patch("NiimPrintX.ui.widget.PrinterOperation.PrinterClient")
@patch("NiimPrintX.ui.widget.PrinterOperation.find_device", new_callable=AsyncMock)
async def test_printer_connect_success(mock_find_device, MockPrinterClient):
    """find_device returns a device and PrinterClient.connect returns True."""
    mock_device = MagicMock()
    mock_find_device.return_value = mock_device

    mock_printer = _make_mock_printer()
    MockPrinterClient.return_value = mock_printer

    printer = _make_state()
    op = PrinterOperation(printer)

    result = await op.printer_connect("d110")

    assert result is True
    assert op._client is mock_printer
    mock_find_device.assert_awaited_once_with("d110")
    mock_printer.connect.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. printer_connect — device not found (BLEException)
# ---------------------------------------------------------------------------


@patch("NiimPrintX.ui.widget.PrinterOperation.PrinterClient")
@patch("NiimPrintX.ui.widget.PrinterOperation.find_device", new_callable=AsyncMock)
async def test_printer_connect_device_not_found(mock_find_device, MockPrinterClient):
    """find_device raises BLEException — connect must return False."""
    mock_find_device.side_effect = BLEException("No device found")

    printer = _make_state()
    op = PrinterOperation(printer)

    result = await op.printer_connect("d110")

    assert result is False
    assert op._client is None
    MockPrinterClient.assert_not_called()


# ---------------------------------------------------------------------------
# 3. printer_connect — connection fails (connect returns False)
# ---------------------------------------------------------------------------


@patch("NiimPrintX.ui.widget.PrinterOperation.PrinterClient")
@patch("NiimPrintX.ui.widget.PrinterOperation.find_device", new_callable=AsyncMock)
async def test_printer_connect_connection_fails(mock_find_device, MockPrinterClient):
    """find_device succeeds but PrinterClient.connect raises — should return False."""
    mock_device = MagicMock()
    mock_find_device.return_value = mock_device

    mock_printer = _make_mock_printer()
    mock_printer.connect = AsyncMock(side_effect=Exception("Connection failed"))
    MockPrinterClient.return_value = mock_printer

    printer = _make_state()
    op = PrinterOperation(printer)

    result = await op.printer_connect("d110")

    assert result is False
    assert op._client is None


# ---------------------------------------------------------------------------
# 4. printer_disconnect — clears state
# ---------------------------------------------------------------------------


async def test_printer_disconnect():
    """Disconnecting a connected printer must clear printer reference."""
    printer = _make_state(printer_connected=True)
    op = PrinterOperation(printer)
    op._client = _make_mock_printer()

    result = await op.printer_disconnect()

    assert result is True
    assert op._client is None


# ---------------------------------------------------------------------------
# 5. print — auto-reconnects when not connected
# ---------------------------------------------------------------------------


@patch("NiimPrintX.ui.widget.PrinterOperation.PrinterClient")
@patch("NiimPrintX.ui.widget.PrinterOperation.find_device", new_callable=AsyncMock)
async def test_print_auto_reconnects(mock_find_device, MockPrinterClient):
    """print() should reconnect when printer_connected is False, then print."""
    mock_device = MagicMock()
    mock_find_device.return_value = mock_device

    mock_printer = _make_mock_printer()
    MockPrinterClient.return_value = mock_printer

    printer = _make_state(printer_connected=False, device="d110")
    op = PrinterOperation(printer)

    img = Image.new("1", (240, 100), color=0)
    result = await op.print(img, density=3, quantity=1)

    assert result is True
    # Verify it reconnected
    mock_find_device.assert_awaited_once_with("d110")
    mock_printer.connect.assert_awaited_once()
    # d110 is NOT a V2 model, so print_image should be called
    mock_printer.print_image.assert_awaited_once_with(img, 3, 1)
    mock_printer.print_image_v2.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5b. print — V2 model uses print_image_v2
# ---------------------------------------------------------------------------


@patch("NiimPrintX.ui.widget.PrinterOperation.PrinterClient")
@patch("NiimPrintX.ui.widget.PrinterOperation.find_device", new_callable=AsyncMock)
async def test_print_v2_model_uses_print_image_v2(mock_find_device, MockPrinterClient):
    """For V2 models (b1, b18, b21), print() should call print_image_v2."""
    mock_device = MagicMock()
    mock_find_device.return_value = mock_device

    mock_printer = _make_mock_printer()
    MockPrinterClient.return_value = mock_printer

    printer = _make_state(printer_connected=False, device="b21")
    op = PrinterOperation(printer)

    img = Image.new("1", (384, 200), color=0)
    result = await op.print(img, density=5, quantity=2)

    assert result is True
    mock_printer.print_image_v2.assert_awaited_once_with(img, 5, 2)
    mock_printer.print_image.assert_not_awaited()


# ---------------------------------------------------------------------------
# 6. heartbeat — returns status dict
# ---------------------------------------------------------------------------


async def test_heartbeat_returns_status():
    """heartbeat() should return (True, dict) when the printer responds."""
    printer = _make_state(printer_connected=True)
    op = PrinterOperation(printer)
    op._client = _make_mock_printer()
    op._client.heartbeat = AsyncMock(return_value={"battery": 80, "status": "ok"})

    success, hb = await op.heartbeat()

    assert success is True
    assert hb == {"battery": 80, "status": "ok"}
    op._client.heartbeat.assert_awaited_once()


# ---------------------------------------------------------------------------
# 6b. heartbeat — no printer returns (False, {})
# ---------------------------------------------------------------------------


async def test_heartbeat_no_printer():
    """heartbeat() with no printer set should return (False, {})."""
    printer = _make_state(printer_connected=False)
    op = PrinterOperation(printer)

    success, hb = await op.heartbeat()

    assert success is False
    assert hb == {}


# ---------------------------------------------------------------------------
# 7. heartbeat — failure clears printer
# ---------------------------------------------------------------------------


async def test_heartbeat_failure_clears_printer():
    """When heartbeat() raises, printer should be set to None."""
    printer = _make_state(printer_connected=True)
    op = PrinterOperation(printer)
    op._client = _make_mock_printer()
    op._client.heartbeat = AsyncMock(side_effect=Exception("BLE timeout"))

    success, hb = await op.heartbeat()

    assert success is False
    assert hb == {}
    assert op._client is None


# ---------------------------------------------------------------------------
# P1 gap: print() failure path returns False
# ---------------------------------------------------------------------------


@patch("NiimPrintX.ui.widget.PrinterOperation.PrinterClient")
@patch("NiimPrintX.ui.widget.PrinterOperation.find_device", new_callable=AsyncMock)
async def test_print_exception_returns_false(mock_find_device, MockPrinterClient):
    """When print_image raises, print() must return False."""
    mock_device = MagicMock()
    mock_find_device.return_value = mock_device

    mock_printer = _make_mock_printer()
    mock_printer.print_image = AsyncMock(side_effect=Exception("BLE dropped"))
    MockPrinterClient.return_value = mock_printer

    printer = _make_state(printer_connected=True, device="d110")
    op = PrinterOperation(printer)
    op._client = mock_printer

    result = await op.print(Image.new("1", (8, 4)), density=3, quantity=1)
    assert result is False
