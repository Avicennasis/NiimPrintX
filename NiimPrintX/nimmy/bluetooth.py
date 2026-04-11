import contextlib

from bleak import BleakClient, BleakScanner

from .exception import BLEException
from .logger_config import get_logger

logger = get_logger()


async def find_device(device_name_prefix=None):
    if device_name_prefix is None or device_name_prefix == "":
        raise BLEException("No device name prefix specified")
    devices = await BleakScanner.discover(return_adv=True)
    # For D110 variants, prefer the device without service UUIDs.
    # D110 appears as two BLE devices; the printing-capable one has no UUIDs.
    is_d110 = device_name_prefix.lower().startswith("d110")
    fallback = None
    for _address, (device, adv_data) in devices.items():
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
    def __init__(self, address=None):
        self.address = address
        self.client = None
        self._notifying_uuids = set()

    async def connect(self, address):
        if self.client is not None and self.address != address:
            # Address changed — disconnect old client first
            await self.disconnect()
        self.address = address
        if self.client is None:
            self.client = BleakClient(address)
        if not self.client.is_connected:
            try:
                await self.client.connect()
            except Exception:
                self.client = None
                raise
            return True
        return True  # already connected

    async def disconnect(self):
        if self.client:
            with contextlib.suppress(Exception):
                await self.client.disconnect()
        self.client = None
        self._notifying_uuids.clear()

    async def write(self, data, char_uuid):
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(char_uuid, data)
        else:
            raise BLEException("BLE client is not connected.")

    async def start_notification(self, char_uuid, handler):
        if not (self.client and self.client.is_connected):
            raise BLEException("BLE client is not connected.")
        if char_uuid not in self._notifying_uuids:
            await self.client.start_notify(char_uuid, handler)
            self._notifying_uuids.add(char_uuid)

    async def stop_notification(self, char_uuid):
        if not (self.client and self.client.is_connected):
            raise BLEException("BLE client is not connected.")
        if char_uuid in self._notifying_uuids:
            await self.client.stop_notify(char_uuid)
            self._notifying_uuids.discard(char_uuid)
