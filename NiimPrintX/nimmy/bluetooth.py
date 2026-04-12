from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from bleak import BleakClient, BleakGATTCharacteristic, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from .exception import BLEException
from .logger_config import get_logger

logger = get_logger()

# Callback type for BLE notification handlers (matches bleak's start_notify signature)
NotifyCallback = Callable[[BleakGATTCharacteristic, bytearray], None | Awaitable[None]]


async def find_device(device_name_prefix: str | None = None, *, scan_timeout: float = 5.0) -> BLEDevice:
    if device_name_prefix is None or device_name_prefix == "":
        raise BLEException("No device name prefix specified")
    devices = await BleakScanner.discover(return_adv=True, timeout=scan_timeout)
    # For D110 variants, prefer the device without service UUIDs.
    # D110 appears as two BLE devices; the printing-capable one has no UUIDs.
    is_d110 = device_name_prefix.lower().startswith("d110")
    fallback: BLEDevice | None = None
    for device, adv_data in devices.values():
        if device.name and device.name.lower().startswith(device_name_prefix.lower()):
            if is_d110:
                if len(adv_data.service_uuids) == 0:
                    return device
                fallback = device
            else:
                return device
    if fallback:
        return fallback
    raise BLEException(f"Failed to find device {device_name_prefix}")


class BLETransport:
    # NOTE: Niimbot printers use unauthenticated BLE pairing. There is no
    # PIN/passkey exchange. Any device advertising the correct name prefix
    # can be paired. This is a hardware protocol limitation, not a software bug.

    def __init__(self, address: str | None = None) -> None:
        self.address: str | None = address
        self.client: BleakClient | None = None
        self._notifying_uuids: set[str] = set()

    async def connect(self, address: str) -> bool:
        if self.client is not None and self.address != address:
            # Address changed — disconnect old client first
            await self.disconnect()
        self.address = address
        if self.client is not None and not self.client.is_connected:
            # Bleak clients are single-use; discard stale instance
            self.client = None
            self._notifying_uuids.clear()
        if self.client is None:
            self.client = BleakClient(address)
            self._notifying_uuids.clear()
            try:
                await self.client.connect()
            except BleakError as e:
                self.client = None
                raise BLEException(f"BLE connect failed: {e}") from e
            except Exception:
                self.client = None
                raise
            return True
        return True  # already connected

    async def disconnect(self) -> None:
        if self.client:
            with contextlib.suppress(Exception):
                await self.client.disconnect()
        self.client = None
        self._notifying_uuids.clear()

    async def write(self, data: bytes | bytearray, char_uuid: str, timeout: float = 10.0) -> None:  # noqa: ASYNC109 — uses asyncio.wait_for internally
        if self.client and self.client.is_connected:
            try:
                await asyncio.wait_for(self.client.write_gatt_char(char_uuid, data, response=None), timeout=timeout)
            except TimeoutError:
                raise BLEException(f"BLE write timed out after {timeout}s") from None
            except BleakError as e:
                raise BLEException(f"BLE GATT write error: {e}") from e
        else:
            raise BLEException("BLE client is not connected.")

    async def start_notification(self, char_uuid: str, handler: NotifyCallback) -> None:
        if not (self.client and self.client.is_connected):
            raise BLEException("BLE client is not connected.")
        if char_uuid not in self._notifying_uuids:
            self._notifying_uuids.add(char_uuid)
            try:
                await self.client.start_notify(char_uuid, handler)
            except Exception:
                self._notifying_uuids.discard(char_uuid)
                raise

    async def stop_notification(self, char_uuid: str) -> None:
        if char_uuid in self._notifying_uuids and self.client and self.client.is_connected:
            await self.client.stop_notify(char_uuid)
        self._notifying_uuids.discard(char_uuid)
