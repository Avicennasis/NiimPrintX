import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from NiimPrintX.nimmy.bluetooth import BLETransport, find_device
from NiimPrintX.nimmy.exception import BLEException

# ---------------------------------------------------------------------------
# find_device tests
# ---------------------------------------------------------------------------


async def test_find_device_no_prefix_raises():
    """find_device(None) should raise BLEException."""
    with pytest.raises(BLEException, match="No device name prefix specified"):
        await find_device(None)


async def test_find_device_empty_prefix_raises():
    """find_device("") should raise BLEException."""
    with pytest.raises(BLEException, match="No device name prefix specified"):
        await find_device("")


@patch("NiimPrintX.nimmy.bluetooth.BleakScanner.discover", new_callable=AsyncMock)
async def test_find_device_no_devices_found(mock_discover):
    """Empty scan results should raise BLEException."""
    mock_discover.return_value = {}
    with pytest.raises(BLEException, match="Failed to find device"):
        await find_device("D110")


@patch("NiimPrintX.nimmy.bluetooth.BleakScanner.discover", new_callable=AsyncMock)
async def test_find_device_matches_prefix(mock_discover):
    """A device whose name starts with the prefix should be returned."""
    device = MagicMock()
    device.name = "D110_xxx"
    adv_data = MagicMock()
    adv_data.service_uuids = []

    mock_discover.return_value = {"AA:BB:CC:DD:EE:FF": (device, adv_data)}
    result = await find_device("d110")
    assert result is device


@patch("NiimPrintX.nimmy.bluetooth.BleakScanner.discover", new_callable=AsyncMock)
async def test_find_device_d110_prefers_no_uuids(mock_discover):
    """For D110, prefer the device with no service UUIDs over one with UUIDs."""
    device_with_uuids = MagicMock()
    device_with_uuids.name = "D110_A"
    adv_with_uuids = MagicMock()
    adv_with_uuids.service_uuids = ["0000ae01-0000-1000-8000-00805f9b34fb"]

    device_no_uuids = MagicMock()
    device_no_uuids.name = "D110_B"
    adv_no_uuids = MagicMock()
    adv_no_uuids.service_uuids = []

    mock_discover.return_value = {
        "AA:BB:CC:DD:EE:01": (device_with_uuids, adv_with_uuids),
        "AA:BB:CC:DD:EE:02": (device_no_uuids, adv_no_uuids),
    }
    result = await find_device("D110")
    assert result is device_no_uuids


@patch("NiimPrintX.nimmy.bluetooth.BleakScanner.discover", new_callable=AsyncMock)
async def test_find_device_d110_fallback(mock_discover):
    """If only a D110 with service UUIDs exists, return it as fallback."""
    device = MagicMock()
    device.name = "D110_A"
    adv_data = MagicMock()
    adv_data.service_uuids = ["0000ae01-0000-1000-8000-00805f9b34fb"]

    mock_discover.return_value = {"AA:BB:CC:DD:EE:FF": (device, adv_data)}
    result = await find_device("d110")
    assert result is device


@patch("NiimPrintX.nimmy.bluetooth.BleakScanner.discover", new_callable=AsyncMock)
async def test_find_device_case_insensitive(mock_discover):
    """Prefix matching should be case-insensitive."""
    device = MagicMock()
    device.name = "D11_ABC"
    adv_data = MagicMock()
    adv_data.service_uuids = []

    mock_discover.return_value = {"AA:BB:CC:DD:EE:FF": (device, adv_data)}
    result = await find_device("d11")
    assert result is device


# ---------------------------------------------------------------------------
# BLETransport tests
# ---------------------------------------------------------------------------


def test_transport_init():
    """Default BLETransport should have address=None and client=None."""
    transport = BLETransport()
    assert transport.address is None
    assert transport.client is None


async def test_transport_write_not_connected_raises():
    """write() when client is None should raise BLEException."""
    transport = BLETransport()
    with pytest.raises(BLEException, match="BLE client is not connected"):
        await transport.write(b"\x00", "some-uuid")


async def test_transport_disconnect_when_not_connected():
    """disconnect() when client is None should not raise."""
    transport = BLETransport()
    await transport.disconnect()  # should complete silently


@patch("NiimPrintX.nimmy.bluetooth.BleakClient")
async def test_connect_exception_resets_client(MockBleakClient):
    """If BleakClient.connect() raises, transport.client should be reset to None."""
    mock_instance = MockBleakClient.return_value
    mock_instance.connect = AsyncMock(side_effect=OSError("Connection refused"))

    transport = BLETransport()
    with pytest.raises(OSError, match="Connection refused"):
        await transport.connect("AA:BB:CC:DD:EE:FF")

    assert transport.client is None


async def test_stop_notification_disconnected_cleans_uuid():
    """stop_notification on a disconnected client should remove the UUID without raising."""
    transport = BLETransport()

    # Simulate a client that is disconnected
    mock_client = MagicMock()
    mock_client.is_connected = False
    mock_client.stop_notify = AsyncMock()
    transport.client = mock_client

    uuid = "00001234-0000-1000-8000-00805f9b34fb"
    transport._notifying_uuids.add(uuid)

    await transport.stop_notification(uuid)

    assert uuid not in transport._notifying_uuids
    # stop_notify should NOT have been called since the client is disconnected
    mock_client.stop_notify.assert_not_called()


async def test_write_timeout():
    """write() should raise BLEException when the GATT write times out."""
    transport = BLETransport()

    mock_client = MagicMock()
    mock_client.is_connected = True

    async def hang(*args, **kwargs):
        await asyncio.sleep(100)

    mock_client.write_gatt_char = hang
    transport.client = mock_client

    with pytest.raises(BLEException, match="BLE write timed out"):
        await transport.write(b"\x01\x02", "some-uuid", timeout=0.05)
