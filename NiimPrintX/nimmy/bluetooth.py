import asyncio
from bleak import BleakClient, BleakScanner

from .exception import BLEException
from .logger_config import get_logger

logger = get_logger()


async def find_device(device_name_prefix=None):
    if not device_name_prefix:
        raise BLEException("No device name prefix specified")
    devices = await BleakScanner.discover(return_adv=True)
    # For D110 variants, prefer the device without service UUIDs.
    # D110 appears as two BLE devices; the printing-capable one has no UUIDs.
    is_d110 = device_name_prefix.lower().startswith("d110")
    fallback = None
    for address, (device, adv_data) in devices.items():
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

    async def __aenter__(self):
        # Automatically connect if address is provided during initialization
        if self.address:
            self.client = BleakClient(self.address)
            if await self.client.connect():
                logger.info(f"Connected to {self.address}")
                return self
            else:
                raise BLEException(f"Failed to connect to the BLE device at {self.address}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected.")

    async def connect(self, address):
        if self.client is None:
            self.client = BleakClient(address)
        if not self.client.is_connected:
            return await self.client.connect()
        return False

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()

    async def write(self, data, char_uuid):
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(char_uuid, data)
        else:
            raise BLEException("BLE client is not connected.")

    async def start_notification(self, char_uuid, handler):
        if self.client and self.client.is_connected:
            await self.client.start_notify(char_uuid, handler)
        else:
            raise BLEException("BLE client is not connected.")

    async def stop_notification(self, char_uuid):
        if self.client and self.client.is_connected:
            await self.client.stop_notify(char_uuid)
        else:
            raise BLEException("BLE client is not connected.")
