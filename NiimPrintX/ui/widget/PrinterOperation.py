from NiimPrintX.nimmy.bluetooth import find_device
from NiimPrintX.nimmy.logger_config import get_logger
from NiimPrintX.nimmy.printer import V2_MODELS, PrinterClient

logger = get_logger()


class PrinterOperation:
    def __init__(self, config):
        self.config = config
        self.printer = None

    async def printer_connect(self, model):
        try:
            device = await find_device(model)
            client = PrinterClient(device)
            if await client.connect():
                self.printer = client
                self.config.printer_connected = True
                return True
            self.config.printer_connected = False
            self.printer = None
            return False
        except Exception as e:
            logger.error(f"Cannot connect to printer {model}: {e}")
            self.config.printer_connected = False
            self.printer = None
            return False

    async def printer_disconnect(self):
        try:
            if self.printer:
                await self.printer.disconnect()
            self.config.printer_connected = False
            self.printer = None
            return True
        except Exception as e:
            self.config.printer_connected = False
            self.printer = None
            logger.error(f"Disconnect error: {e}")
            return False

    async def print(self, image, density, quantity):
        try:
            if not self.config.printer_connected or not self.printer:
                connected = await self.printer_connect(self.config.device)
                if not connected:
                    logger.error("Print failed: could not connect to printer")
                    return False

            if self.config.device in V2_MODELS:
                await self.printer.print_imageV2(image, density, quantity)
            else:
                await self.printer.print_image(image, density, quantity)
            return True
        except Exception as e:
            logger.error(f"Print error: {e}")
            return False

    async def heartbeat(self):
        try:
            if self.printer:
                hb = await self.printer.heartbeat()
                return True, hb
            return False, {}
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            self.config.printer_connected = False
            self.printer = None
            return False, {}
