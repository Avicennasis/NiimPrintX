import asyncio
import contextlib
import enum
import math
import struct

from PIL import Image, ImageOps

from .bluetooth import BLETransport
from .exception import BLEException, PrinterException
from .logger_config import get_logger
from .packet import NiimbotPacket, packet_to_int

logger = get_logger()

V2_MODELS = frozenset({"b1", "b18", "b21"})


class InfoEnum(enum.IntEnum):
    DENSITY = 1
    PRINTSPEED = 2
    LABELTYPE = 3
    LANGUAGETYPE = 6
    AUTOSHUTDOWNTIME = 7
    DEVICETYPE = 8
    SOFTVERSION = 9
    BATTERY = 10
    DEVICESERIAL = 11
    HARDVERSION = 12


class RequestCodeEnum(enum.IntEnum):
    GET_INFO = 64  # 0x40
    GET_RFID = 26  # 0x1A
    HEARTBEAT = 220  # 0xDC
    SET_LABEL_TYPE = 35  # 0x23
    SET_LABEL_DENSITY = 33  # 0x21
    START_PRINT = 1  # 0x01
    END_PRINT = 243  # 0xF3
    START_PAGE_PRINT = 3  # 0x03
    END_PAGE_PRINT = 227  # 0xE3
    SET_DIMENSION = 19  # 0x13
    SET_QUANTITY = 21  # 0x15
    GET_PRINT_STATUS = 163  # 0xA3


class PrinterClient:
    def __init__(self, device):
        self.char_uuid = None
        self.device = device
        self.transport = BLETransport()
        self.notification_event = asyncio.Event()
        self.notification_data = None
        self._loop = None
        self._command_lock = asyncio.Lock()
        self._print_lock = asyncio.Lock()

    async def connect(self):
        if await self.transport.connect(self.device.address):
            if not self.char_uuid:
                try:
                    await self.find_characteristics()
                except PrinterException:
                    await self.transport.disconnect()
                    raise
            self._loop = asyncio.get_running_loop()
            logger.info(f"Successfully connected to {self.device.name}")
            return True
        logger.error("Connection failed.")
        return False

    async def disconnect(self):
        self.char_uuid = None
        await self.transport.disconnect()
        logger.info(f"Printer {self.device.name} disconnected.")

    async def find_characteristics(self):
        services = {}
        for service in self.transport.client.services:
            s = [
                {"id": char.uuid, "handle": char.handle, "properties": char.properties}
                for char in service.characteristics
            ]

            services[service.uuid] = s

        candidates = []
        for characteristics in services.values():
            if len(characteristics) == 1:  # Check if there's exactly one characteristic
                props = characteristics[0]["properties"]
                if "read" in props and "write-without-response" in props and "notify" in props:
                    candidates.append(characteristics[0]["id"])
        if not candidates:
            raise PrinterException("Cannot find bluetooth characteristics.")
        if len(candidates) > 1:
            logger.warning(f"Multiple matching characteristics found: {candidates}; using first")
        self.char_uuid = candidates[0]

    async def send_command(self, request_code, data, timeout=10):  # noqa: ASYNC109 — uses asyncio.wait_for internally
        async with self._command_lock:
            notifying = False
            try:
                if (not self.transport.client or not self.transport.client.is_connected) and not await self.connect():
                    raise PrinterException("Failed to reconnect to printer")
                # Clear stale state BEFORE arming notifications
                self.notification_event.clear()
                self.notification_data = None
                packet = NiimbotPacket(request_code, data)
                await self.transport.start_notification(self.char_uuid, self.notification_handler)
                notifying = True
                await self.transport.write(packet.to_bytes(), self.char_uuid)
                logger.debug(
                    f"Printer command sent - {RequestCodeEnum(request_code).name}:{request_code} - {list(data)}"
                )
                await asyncio.wait_for(self.notification_event.wait(), timeout)
                response = NiimbotPacket.from_bytes(self.notification_data)
                logger.debug(f"Printer response received - {list(response.data)} - {len(response.data)} bytes")
                return response
            except TimeoutError:
                logger.error(f"Timeout occurred for request {RequestCodeEnum(request_code).name}")
                raise PrinterException(f"Printer timed out on {RequestCodeEnum(request_code).name}") from None
            except BLEException as e:
                logger.error(f"An error occurred: {e}")
                raise PrinterException(f"BLE error during {RequestCodeEnum(request_code).name}: {e}") from e
            except (ValueError, TypeError) as e:
                logger.error(f"Malformed response for {RequestCodeEnum(request_code).name}: {e}")
                raise PrinterException(f"Malformed printer response: {e}") from e
            finally:
                if notifying:
                    try:
                        await self.transport.stop_notification(self.char_uuid)
                    except Exception as e:  # noqa: BLE001 — best-effort cleanup during notification teardown
                        logger.warning(f"stop_notify failed: {e}")
                self.notification_event.clear()

    async def write_raw(self, data):
        async with self._command_lock:
            try:
                if (not self.transport.client or not self.transport.client.is_connected) and not await self.connect():
                    raise PrinterException("Failed to reconnect to printer")
                await self.transport.write(data.to_bytes(), self.char_uuid)
            except (BLEException, ValueError, TypeError) as e:
                logger.error(f"Write error: {e}")
                raise PrinterException(f"BLE write failed: {e}") from e

    def notification_handler(self, sender, data):
        logger.trace(f"Notification: {data}")
        if self._loop is None:
            return

        def _set():
            if not self.notification_event.is_set():
                self.notification_data = data
                self.notification_event.set()

        self._loop.call_soon_threadsafe(_set)

    async def print_image(
        self, image: Image.Image, density: int = 3, quantity: int = 1, vertical_offset=0, horizontal_offset=0
    ):
        await self._print_job(image, density, quantity, vertical_offset, horizontal_offset, v2=False)

    async def print_imageV2(
        self, image: Image.Image, density: int = 3, quantity: int = 1, vertical_offset=0, horizontal_offset=0
    ):
        await self._print_job(image, density, quantity, vertical_offset, horizontal_offset, v2=True)

    async def _print_job(
        self,
        image: Image.Image,
        density: int,
        quantity: int,
        vertical_offset: int,
        horizontal_offset: int,
        *,
        v2: bool = False,
    ):
        async with self._print_lock:
            try:
                await self.set_label_density(density)
                await self.set_label_type(1)

                if v2:
                    await self.start_printV2(quantity=quantity)
                else:
                    await self.start_print()

                await self.start_page_print()

                # Calculate post-offset dimensions
                effective_height = image.height
                effective_width = image.width
                if horizontal_offset > 0:
                    effective_width += horizontal_offset
                elif horizontal_offset < 0:
                    effective_width = max(0, effective_width + horizontal_offset)
                if vertical_offset > 0:
                    effective_height += vertical_offset
                elif vertical_offset < 0:
                    effective_height = max(0, effective_height + vertical_offset)

                if effective_width == 0 or effective_height == 0:
                    raise PrinterException("Image produces no data after applying offsets")

                if v2:
                    await self.set_dimensionV2(effective_height, effective_width, quantity)
                else:
                    await self.set_dimension(effective_height, effective_width)
                    await self.set_quantity(quantity)

                for pkt in self._encode_image(image, vertical_offset, horizontal_offset):
                    await self.write_raw(pkt)
                    await asyncio.sleep(0.01)

                for _ in range(200):  # ~10 seconds at 0.05s interval
                    if await self.end_page_print():
                        break
                    await asyncio.sleep(0.05)
                else:
                    raise PrinterException("end_page_print timed out")

                max_status_checks = 600  # ~60 seconds at 0.1s interval
                status = {"page": 0, "progress1": 0, "progress2": 0}
                for _ in range(max_status_checks):
                    status = await self.get_print_status()
                    if status["page"] >= quantity:
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise PrinterException(f"Print status timeout: page {status['page']}/{quantity}")

                await self.end_print()
            except BaseException as e:
                logger.error(f"Print job failed: {e}")
                if self.transport.client and self.transport.client.is_connected:
                    with contextlib.suppress(Exception):
                        await self.end_print()
                raise

    def _encode_image(self, image: Image.Image, vertical_offset=0, horizontal_offset=0):
        if image.width > (255 - 6) * 8:  # 6-byte header (>HBBBB): row_idx(2)+counts(3)+flag(1)
            raise PrinterException(f"Image width {image.width}px exceeds protocol limit")

        # Convert the image to monochrome, closing intermediate images
        gray = image.convert("L")
        try:
            inverted = ImageOps.invert(gray)
        finally:
            gray.close()
        try:
            img = inverted.convert("1")
        finally:
            inverted.close()

        try:
            # Apply horizontal offset
            if horizontal_offset > 0:
                old = img
                img = ImageOps.expand(img, border=(horizontal_offset, 0, 0, 0), fill=0)
                old.close()
            elif horizontal_offset < 0:
                old = img
                img = img.crop((-horizontal_offset, 0, img.width, img.height))
                old.close()

            # Apply vertical offset
            if vertical_offset > 0:
                old = img
                img = ImageOps.expand(img, border=(0, vertical_offset, 0, 0), fill=0)
                old.close()
            elif vertical_offset < 0:
                old = img
                img = img.crop((0, -vertical_offset, img.width, img.height))
                old.close()

            if img.width == 0 or img.height == 0:
                raise PrinterException("Image produces no data after applying offsets")

            byte_count = math.ceil(img.width / 8)
            all_bytes = img.tobytes()

            for y in range(img.height):
                line_data = all_bytes[y * byte_count : (y + 1) * byte_count]
                counts = (0, 0, 0)  # It seems like you can always send zeros
                header = struct.pack(">HBBBB", y, *counts, 1)
                pkt = NiimbotPacket(0x85, header + line_data)
                yield pkt
        finally:
            img.close()

    async def get_info(self, key):
        response = await self.send_command(RequestCodeEnum.GET_INFO, bytes((key,)))

        if len(response.data) < 1:
            raise PrinterException(f"Empty response for GET_INFO key {key}")

        match key:
            case InfoEnum.DEVICESERIAL:
                return response.data.hex()
            case InfoEnum.SOFTVERSION:
                return packet_to_int(response) / 100
            case InfoEnum.HARDVERSION:
                return packet_to_int(response) / 100
            case _:
                return packet_to_int(response)

    async def get_rfid(self):
        packet = await self.send_command(RequestCodeEnum.GET_RFID, b"\x01")
        data = packet.data

        try:
            if not data or data[0] == 0:
                return None
            uuid = data[0:8].hex()
            idx = 8

            barcode_len = data[idx]
            idx += 1
            barcode = data[idx : idx + barcode_len].decode("utf-8", errors="replace")

            idx += barcode_len
            serial_len = data[idx]
            idx += 1
            serial = data[idx : idx + serial_len].decode("utf-8", errors="replace")

            idx += serial_len
            total_len, used_len, type_ = struct.unpack(">HHB", data[idx : idx + 5])
            return {
                "uuid": uuid,
                "barcode": barcode,
                "serial": serial,
                "used_len": used_len,
                "total_len": total_len,
                "type": type_,
            }
        except (IndexError, struct.error) as e:
            logger.error(f"Malformed RFID response: {e}")
            return None

    async def heartbeat(self):
        packet = await self.send_command(RequestCodeEnum.HEARTBEAT, b"\x01")
        closing_state = None
        power_level = None
        paper_state = None
        rfid_read_state = None

        match len(packet.data):
            case 20:
                paper_state = packet.data[18]
                rfid_read_state = packet.data[19]
            case 13:
                closing_state = packet.data[9]
                power_level = packet.data[10]
                paper_state = packet.data[11]
                rfid_read_state = packet.data[12]
            case 19:
                closing_state = packet.data[15]
                power_level = packet.data[16]
                paper_state = packet.data[17]
                rfid_read_state = packet.data[18]
            case 10:
                closing_state = packet.data[8]
                power_level = packet.data[9]
            case 9:
                closing_state = packet.data[8]
            case _:
                logger.warning(f"Unrecognized heartbeat length {len(packet.data)}, cannot parse state")

        return {
            "closing_state": closing_state,
            "power_level": power_level,
            "paper_state": paper_state,
            "rfid_read_state": rfid_read_state,
        }

    async def set_label_type(self, n):
        if not 1 <= n <= 3:
            raise ValueError(f"Label type must be 1-3, got {n}")
        packet = await self.send_command(RequestCodeEnum.SET_LABEL_TYPE, bytes((n,)))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def set_label_density(self, n):
        if not 1 <= n <= 5:
            raise ValueError(f"Label density must be 1-5, got {n}")
        packet = await self.send_command(RequestCodeEnum.SET_LABEL_DENSITY, bytes((n,)))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def start_print(self):
        packet = await self.send_command(RequestCodeEnum.START_PRINT, b"\x01")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def start_printV2(self, quantity):
        if not 1 <= quantity <= 65535:
            raise ValueError(f"Quantity must be 1-65535, got {quantity}")
        command = struct.pack(">H", quantity)
        packet = await self.send_command(RequestCodeEnum.START_PRINT, b"\x00" + command + b"\x00\x00\x00\x00")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def end_print(self):
        packet = await self.send_command(RequestCodeEnum.END_PRINT, b"\x01")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def start_page_print(self):
        packet = await self.send_command(RequestCodeEnum.START_PAGE_PRINT, b"\x01")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def end_page_print(self):
        packet = await self.send_command(RequestCodeEnum.END_PAGE_PRINT, b"\x01")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def set_dimension(self, height, width):
        packet = await self.send_command(RequestCodeEnum.SET_DIMENSION, struct.pack(">HH", height, width))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def set_dimensionV2(self, height, width, copies):
        logger.debug(f"Setting dimension: {height}x{width}")
        packet = await self.send_command(RequestCodeEnum.SET_DIMENSION, struct.pack(">HHH", height, width, copies))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def set_quantity(self, n):
        if not 1 <= n <= 65535:
            raise ValueError(f"Quantity must be 1-65535, got {n}")
        packet = await self.send_command(RequestCodeEnum.SET_QUANTITY, struct.pack(">H", n))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer")
        return bool(packet.data[0])

    async def get_print_status(self):
        packet = await self.send_command(RequestCodeEnum.GET_PRINT_STATUS, b"\x01")
        if len(packet.data) < 4:
            raise PrinterException(f"get_print_status: short response ({len(packet.data)} bytes)")
        page, progress1, progress2 = struct.unpack(">HBB", packet.data[:4])
        return {"page": page, "progress1": progress1, "progress2": progress2}
