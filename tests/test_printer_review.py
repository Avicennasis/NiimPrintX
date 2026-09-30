"""September review regression coverage."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from NiimPrintX.nimmy.exception import PrinterException
from NiimPrintX.ui.config import PrinterState
from NiimPrintX.ui.widget.PrinterOperation import PrinterOperation


async def test_model_switch_disconnects_old_client_before_print(monkeypatch):
    state = PrinterState("d110")
    operation = PrinterOperation(state)
    old = SimpleNamespace(disconnect=AsyncMock(), print_image_v2=AsyncMock())
    new = SimpleNamespace(connect=AsyncMock(), disconnect=AsyncMock(), print_image_v2=AsyncMock())
    operation._client = old
    state.printer_connected = True
    state.device = "b21"
    monkeypatch.setattr("NiimPrintX.ui.widget.PrinterOperation.find_device", AsyncMock(return_value=object()))
    monkeypatch.setattr("NiimPrintX.ui.widget.PrinterOperation.PrinterClient", lambda _: new)
    with Image.new("1", (100, 20)) as image:
        assert await operation.print(image, 3, 1)
        new.print_image_v2.assert_awaited_once_with(image, 3, 1, model="b21")
    old.disconnect.assert_awaited_once()
    old.print_image_v2.assert_not_awaited()


async def test_heartbeat_cannot_restore_old_model_connection():
    state = PrinterState("d110")
    operation = PrinterOperation(state)
    old = SimpleNamespace(disconnect=AsyncMock(), heartbeat=AsyncMock())
    operation._client = old
    state.device = "b21"
    assert await operation.heartbeat() == (False, {})
    old.disconnect.assert_awaited_once()
    old.heartbeat.assert_not_awaited()
    assert not state.printer_connected


async def test_failed_connect_releases_partial_client(monkeypatch):
    operation = PrinterOperation(PrinterState("d110"))
    client = SimpleNamespace(connect=AsyncMock(side_effect=RuntimeError("discovery failed")), disconnect=AsyncMock())
    monkeypatch.setattr("NiimPrintX.ui.widget.PrinterOperation.find_device", AsyncMock(return_value=object()))
    monkeypatch.setattr("NiimPrintX.ui.widget.PrinterOperation.PrinterClient", lambda _: client)
    assert not await operation.printer_connect("d110")
    client.disconnect.assert_awaited_once()


@pytest.mark.parametrize("quantity", [0, 65536, 1.5, True])
async def test_invalid_quantity_is_rejected_before_ble(make_client, quantity):
    client = make_client()
    client.set_label_density = AsyncMock()
    with Image.new("1", (8, 2)) as image, pytest.raises(PrinterException, match="Quantity"):
        await client.print_image(image, quantity=quantity)
    client.set_label_density.assert_not_awaited()
    client.transport.write.assert_not_awaited()


async def test_oversized_image_is_rejected_before_ble(make_client):
    client = make_client()
    client.set_label_density = AsyncMock()
    with Image.new("1", (1993, 2)) as image, pytest.raises(PrinterException, match="width"):
        await client.print_image(image)
    client.set_label_density.assert_not_awaited()


@pytest.mark.parametrize("phase", ["end_page", "status"])
async def test_polling_deadline_includes_command_time(make_client, monkeypatch, phase):
    client = make_client()
    for name in (
        "set_label_density",
        "set_label_type",
        "start_print",
        "start_page_print",
        "set_dimension",
        "set_quantity",
        "end_page_print",
        "end_print",
    ):
        setattr(client, name, AsyncMock(return_value=True))
    client.write_raw = AsyncMock()
    client.get_print_status = AsyncMock(return_value={"page": 1, "progress1": 100, "progress2": 100})
    client._encode_image = lambda *_: iter(())

    async def slow_response():
        await asyncio.sleep(1)
        return False

    if phase == "end_page":
        client.end_page_print = AsyncMock(side_effect=slow_response)
    else:
        client.get_print_status = AsyncMock(side_effect=slow_response)
    real_timeout = asyncio.timeout
    deadlines = []

    def short_timeout(delay):
        deadlines.append(delay)
        return real_timeout(0.01)

    monkeypatch.setattr("NiimPrintX.nimmy.printer.asyncio.timeout", short_timeout)
    match = "end_page_print timed out" if phase == "end_page" else "Print status timeout"
    with Image.new("1", (8, 2)) as image, pytest.raises(PrinterException, match=match):
        await client.print_image(image)
    assert deadlines == ([10] if phase == "end_page" else [10, 60])
    client.end_print.assert_awaited_once()
