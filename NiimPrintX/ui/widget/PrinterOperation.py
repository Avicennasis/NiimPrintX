from __future__ import annotations

from typing import TYPE_CHECKING

from NiimPrintX.nimmy.bluetooth import find_device
from NiimPrintX.nimmy.logger_config import get_logger
from NiimPrintX.nimmy.printer import V2_MODELS, PrinterClient

if TYPE_CHECKING:
    from NiimPrintX.ui.config import PrinterState

logger = get_logger()


class PrinterOperation:
    def __init__(self, printer: PrinterState) -> None:
        self.printer: PrinterState = printer
        self._client: PrinterClient | None = None

    @property
    def is_connected(self) -> bool:
        """Whether a BLE client is currently connected."""
        return self._client is not None

    async def printer_connect(self, model):
        try:
            device = await find_device(model)
            client = PrinterClient(device)
            await client.connect()
            self._client = client
            return True
        except Exception as e:
            logger.error(f"Cannot connect to printer {model}: {e}")
            self._client = None
            return False

    async def printer_disconnect(self):
        try:
            if self._client:
                await self._client.disconnect()
            self._client = None
            return True
        except Exception as e:
            self._client = None
            logger.error(f"Disconnect error: {e}")
            return False

    async def print(self, image, density, quantity):
        try:
            if not self.is_connected:
                connected = await self.printer_connect(self.printer.device)
                if not connected:
                    logger.error("Print failed: could not connect to printer")
                    return False
                self.printer.printer_connected = True

            if self.printer.device in V2_MODELS:
                await self._client.print_image_v2(image, density, quantity)
            else:
                await self._client.print_image(image, density, quantity)
            return True
        except Exception as e:
            logger.error(f"Print error: {e}")
            return False

    async def heartbeat(self):
        try:
            if self._client:
                hb = await self._client.heartbeat()
                return True, hb
            return False, {}
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            self._client = None
            return False, {}
