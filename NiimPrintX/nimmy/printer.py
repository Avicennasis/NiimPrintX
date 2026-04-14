from __future__ import annotations

import asyncio
import contextlib
import enum
import math
import struct
from typing import TYPE_CHECKING, Any, cast

from PIL import Image, ImageOps

from .bluetooth import BLETransport
from .exception import BLEException, PrinterException
from .logger_config import get_logger
from .packet import NiimbotPacket

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .types import HeartbeatResponse, PrintStatus, RFIDResponse

logger = get_logger()

V2_MODELS = frozenset({"b1", "b18", "b21"})
V4_MODELS = frozenset({"d110_m"})  # 2025 D110M uses V4 protocol per NiimBlueLib

# Maximum density per model (from hardware specs)
MODEL_MAX_DENSITY = {"b21": 5}  # All other models default to DEFAULT_MAX_DENSITY
DEFAULT_MAX_DENSITY = 3


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
    def __init__(self, device: Any) -> None:
        self.char_uuid: str | None = None
        self.device = device
        self.transport: BLETransport = BLETransport()
        self.notification_event: asyncio.Event = asyncio.Event()
        self.notification_data: bytes | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._command_lock: asyncio.Lock = asyncio.Lock()
        self._print_lock: asyncio.Lock = asyncio.Lock()
        self._expecting_response: bool = False

    async def connect(self) -> None:
        await self.transport.connect(self.device.address)
        if not self.char_uuid:
            try:
                await self.find_characteristics()
            except PrinterException:
                await self.transport.disconnect()
                raise
        self._loop = asyncio.get_running_loop()
        logger.info(f"Successfully connected to {self.device.name!r}")

    async def disconnect(self) -> None:
        if self.char_uuid is not None:
            with contextlib.suppress(Exception):
                await self.transport.stop_notification(self.char_uuid)
        self.char_uuid = None
        await self.transport.disconnect()
        logger.info(f"Printer {self.device.name!r} disconnected.")

    async def find_characteristics(self) -> None:
        if self.transport.client is None:
            raise PrinterException("BLE client not initialized")
        services: dict[str, list[dict[str, Any]]] = {}
        for service in self.transport.client.services:
            s = [
                {"id": char.uuid, "handle": char.handle, "properties": char.properties}
                for char in service.characteristics
            ]

            services[service.uuid] = s

        candidates: list[str] = []
        for svc_uuid, characteristics in services.items():
            logger.debug(f"Service {svc_uuid}:")
            for char in characteristics:
                props = char["properties"]
                logger.debug(f"  Char {char['id']}: {props}")
                if "read" in props and "write-without-response" in props and "notify" in props:
                    candidates.append(char["id"])
        if not candidates:
            raise PrinterException("Cannot find bluetooth characteristics.")
        if len(candidates) > 1:
            logger.warning(f"Multiple matching characteristics found: {candidates}; using first")
        self.char_uuid = candidates[0]
        logger.debug(f"Selected characteristic: {self.char_uuid}")

    async def send_command(self, request_code: int, data: bytes, timeout: float = 10) -> NiimbotPacket:  # noqa: ASYNC109 — uses asyncio.wait_for internally
        async with self._command_lock:
            code_label = hex(request_code)  # default before try; overridden with enum name inside
            try:
                if not self.transport.client or not self.transport.client.is_connected:
                    self.char_uuid = None  # force re-discovery after unilateral disconnect
                    await self.connect()
                if self.char_uuid is None:
                    raise PrinterException("No characteristic UUID available")
                # Clear stale state BEFORE arming notifications
                self.notification_event.clear()
                self.notification_data = None
                try:
                    code_label = RequestCodeEnum(request_code).name
                except ValueError:
                    code_label = hex(request_code)
                packet = NiimbotPacket(request_code, data)
                # start_notification is idempotent — no-ops if already armed
                await self.transport.start_notification(self.char_uuid, self.notification_handler)
                self._expecting_response = True
                await self.transport.write(packet.to_bytes(), self.char_uuid)
                logger.debug(f"Printer command sent - {code_label}:{request_code} - {list(data)}")
                await asyncio.wait_for(self.notification_event.wait(), timeout)
                # notification_data is set by notification_handler callback via call_soon_threadsafe;
                # cast defeats mypy's flow narrowing from the line-125 reset assignment.
                response_data = cast("bytes | None", self.notification_data)
                if response_data is None:
                    msg = "Notification arrived but contained no data"
                    raise PrinterException(msg)
                response = NiimbotPacket.from_bytes(response_data)
                logger.debug(f"Printer response received - {list(response.data)} - {len(response.data)} bytes")
                return response
            except TimeoutError:
                logger.debug(f"Timeout occurred for request {code_label}")
                raise PrinterException(f"Printer timed out on {code_label}") from None
            except BLEException as e:
                logger.debug(f"BLE error during command: {e}")
                raise PrinterException(f"BLE error during {code_label}: {e}") from e
            except (ValueError, TypeError) as e:
                logger.debug(f"Malformed response for {code_label}: {e}")
                raise PrinterException(f"Malformed printer response: {e}") from e
            finally:
                self._expecting_response = False
                self.notification_event.clear()

    async def write_raw(self, data: NiimbotPacket, *, response: bool = False) -> None:
        async with self._command_lock:
            try:
                if not self.transport.client or not self.transport.client.is_connected:
                    await self.connect()
                if self.char_uuid is None:
                    raise PrinterException("No characteristic UUID available")
                await self.transport.write(data.to_bytes(), self.char_uuid, response=response)
            except (BLEException, ValueError, TypeError) as e:
                logger.error(f"Write error: {e}")
                raise PrinterException(f"BLE write failed: {e}") from e

    def notification_handler(self, sender: Any, data: bytearray) -> None:
        logger.trace(f"Notification: {data}")
        if self._loop is None:
            logger.warning("Notification received but event loop is None; dropping")
            return

        snapshot = bytes(data)

        def _set() -> None:
            if self._expecting_response and not self.notification_event.is_set():
                self.notification_data = snapshot
                self.notification_event.set()
            else:
                logger.debug(f"Dropped unsolicited notification ({len(snapshot)} bytes): {list(snapshot)}")

        try:
            self._loop.call_soon_threadsafe(_set)
        except RuntimeError:
            logger.debug("Event loop closed; dropping late notification")

    async def print_image(
        self,
        image: Image.Image,
        density: int = 3,
        quantity: int = 1,
        vertical_offset: int = 0,
        horizontal_offset: int = 0,
    ) -> None:
        await self._print_job(image, density, quantity, vertical_offset, horizontal_offset, v2=False)

    async def print_image_v2(
        self,
        image: Image.Image,
        density: int = 3,
        quantity: int = 1,
        vertical_offset: int = 0,
        horizontal_offset: int = 0,
    ) -> None:
        await self._print_job(image, density, quantity, vertical_offset, horizontal_offset, v2=True)

    async def print_image_v4(
        self,
        image: Image.Image,
        density: int = 3,
        quantity: int = 1,
        vertical_offset: int = 0,
        horizontal_offset: int = 0,
    ) -> None:
        """V4 protocol for D110_M (2025 model) - different command formats."""
        await self._print_job(image, density, quantity, vertical_offset, horizontal_offset, v4=True)

    async def _print_job(
        self,
        image: Image.Image,
        density: int,
        quantity: int,
        vertical_offset: int,
        horizontal_offset: int,
        *,
        v2: bool = False,
        v4: bool = False,
    ) -> None:
        async with self._print_lock:
            print_started = False
            page_started = False
            epp_timed_out = False
            try:
                # Calculate post-offset dimensions before any BLE traffic
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
                    raise PrinterException(
                        f"Image produces no data after applying offsets "
                        f"(effective size: {effective_width}x{effective_height})"
                    )

                if not await self.set_label_density(density):
                    raise PrinterException("Printer rejected set_label_density")
                if not await self.set_label_type(1):
                    raise PrinterException("Printer rejected set_label_type")

                if v4:
                    if not await self.start_print_v4(quantity=quantity):
                        raise PrinterException("Printer rejected start_print_v4")
                elif v2:
                    if not await self.start_print_v2(quantity=quantity):
                        raise PrinterException("Printer rejected start_print_v2")
                elif not await self.start_print():
                    raise PrinterException("Printer rejected start_print")
                print_started = True

                # V4 protocol (D110_M) omits PageStart entirely
                if not v4:
                    if not await self.start_page_print():
                        raise PrinterException("Printer rejected start_page_print")
                    page_started = True

                if v4:
                    if not await self.set_dimension_v4(effective_height, effective_width, quantity):
                        raise PrinterException("Printer rejected set_dimension_v4")
                    # V4 protocol: fire-and-forget PrintStatus before image data
                    await self.write_raw(NiimbotPacket(RequestCodeEnum.GET_PRINT_STATUS, b"\x01"))
                    logger.debug("V4: sent fire-and-forget PrintStatus before image data")
                elif v2:
                    if not await self.set_dimension_v2(effective_height, effective_width, quantity):
                        raise PrinterException("Printer rejected set_dimension_v2")
                else:
                    if not await self.set_dimension(effective_height, effective_width):
                        raise PrinterException("Printer rejected set_dimension")
                    if not await self.set_quantity(quantity):
                        raise PrinterException("Printer rejected set_quantity")

                pkt_count = 0
                non_zero_rows = 0
                for pkt in self._encode_image(image, vertical_offset, horizontal_offset):
                    # Check if this row has any non-zero data (actual content)
                    row_data = pkt.data[6:]  # Skip 6-byte header
                    if any(b != 0 for b in row_data):
                        non_zero_rows += 1
                        if non_zero_rows <= 3:
                            # Show header bytes (first 6) + first 10 data bytes
                            header_bytes = list(pkt.data[:6])
                            raw_bytes = pkt.to_bytes()
                            logger.debug(f"Row {pkt_count} header={header_bytes} data={list(row_data[:10])}...")
                            logger.debug(f"  Raw packet ({len(raw_bytes)} bytes): {raw_bytes[:20].hex()}...")
                    await self.write_raw(pkt)  # fire-and-forget for image data
                    pkt_count += 1
                    # Small delay to let printer process
                    if pkt_count % 10 == 0:
                        await asyncio.sleep(0.01)
                logger.debug(f"Sent {pkt_count} image packets, {non_zero_rows} with non-zero content")

                # Give printer time to process all image data before end_page_print
                await asyncio.sleep(0.5)

                for _ in range(200):  # ~10 seconds at 0.05s interval
                    if await self.end_page_print():
                        page_started = False  # page cleanly closed; don't re-send in cleanup
                        break
                    await asyncio.sleep(0.05)
                else:
                    epp_timed_out = True
                    raise PrinterException("end_page_print timed out")

                max_status_checks = 600  # ~60 seconds at 0.1s interval
                status: PrintStatus = {"page": 0, "progress1": 0, "progress2": 0}
                for _ in range(max_status_checks):
                    status = await self.get_print_status_v4() if v4 else await self.get_print_status()
                    if status["page"] >= quantity:
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise PrinterException(f"Print status timeout: page {status['page']}/{quantity}")

                await self.end_print()
            except BaseException as e:
                # BaseException includes CancelledError — must clean up printer
                # to avoid leaving hardware in mid-print state (requires power cycle)
                logger.error(f"Print job failed: {e}")
                if print_started and self.transport.client and self.transport.client.is_connected:
                    if page_started and not epp_timed_out:
                        with contextlib.suppress(BaseException):
                            await asyncio.wait_for(self.end_page_print(), timeout=2.0)
                    with contextlib.suppress(BaseException):
                        await asyncio.wait_for(self.end_print(), timeout=2.0)
                raise

    def _encode_image(
        self, image: Image.Image, vertical_offset: int = 0, horizontal_offset: int = 0
    ) -> Iterator[NiimbotPacket]:
        effective_height = image.height + max(0, vertical_offset)
        if effective_height > 65535:
            raise PrinterException(
                f"Effective height {effective_height}px (image {image.height}px + offset {vertical_offset}px) "
                f"exceeds protocol limit of 65535 rows"
            )

        max_width = (255 - 6) * 8  # 6-byte header (>HBBBB): row_idx(2)+counts(3)+flag(1) → 1992px
        if image.width > max_width:
            raise PrinterException(f"Image width {image.width}px exceeds protocol limit of {max_width}px")

        effective_width = image.width + max(0, horizontal_offset)
        if effective_width > max_width:
            raise PrinterException(
                f"Effective width {effective_width}px (image {image.width}px + offset {horizontal_offset}px) "
                f"exceeds protocol limit of {max_width}px"
            )

        # Composite alpha onto white background before grayscale conversion
        # (RGBA/LA images have undefined RGB in transparent regions;
        #  PA mode stores transparency in palette, not per-pixel — convert first)
        if image.mode in ("PA", "P"):
            image = image.convert("RGBA")
        if image.mode in ("RGBA", "LA"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            try:
                alpha = image.split()[-1]
                try:
                    background.paste(image, mask=alpha)
                finally:
                    alpha.close()
                gray = background.convert("L")
            finally:
                background.close()
        else:
            gray = image.convert("L")
        try:
            inverted = ImageOps.invert(gray)
        finally:
            gray.close()
        try:
            img = inverted.convert("1", dither=Image.Dither.NONE)  # threshold, no Floyd-Steinberg — crisp for thermal
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
                raise PrinterException(
                    f"Image produces no data after applying offsets (effective size: {img.width}x{img.height})"
                )

            byte_count = math.ceil(img.width / 8)
            all_bytes = img.tobytes()
            mv = memoryview(all_bytes)

            for y in range(img.height):
                line_data = bytes(mv[y * byte_count : (y + 1) * byte_count])
                # Per niimprint: "It seems like you can always send zeros" for pixel counts
                counts = (0, 0, 0)
                # Use big-endian for row index (matches niimprint library)
                row_fmt = ">HBBBB"
                header = struct.pack(row_fmt, y, *counts, 1)
                pkt = NiimbotPacket(0x85, header + line_data)
                yield pkt
        finally:
            img.close()

    async def get_info(self, key: int) -> int | float | str:
        response = await self.send_command(RequestCodeEnum.GET_INFO, bytes((key,)))

        if len(response.data) < 1:
            raise PrinterException(f"Empty response from printer for GET_INFO key {key}")

        match key:
            case InfoEnum.DEVICESERIAL:
                return response.data.hex()
            case InfoEnum.SOFTVERSION:
                return response.to_int() / 100
            case InfoEnum.HARDVERSION:
                return response.to_int() / 100
            case _:
                return response.to_int()

    async def get_rfid(self) -> RFIDResponse | None:  # noqa: PLR0911 — early returns for malformed RFID data are clearer than nesting
        packet = await self.send_command(RequestCodeEnum.GET_RFID, b"\x01")
        data = packet.data

        try:
            if not data or data[0] == 0:
                return None
            if len(data) < 9:
                logger.error("Malformed RFID response: data too short (%d bytes)", len(data))
                return None
            uuid = data[0:8].hex()
            idx = 8

            barcode_len = data[idx]
            idx += 1
            if idx + barcode_len > len(data):
                logger.error("Malformed RFID response: barcode length exceeds data bounds")
                return None
            barcode = data[idx : idx + barcode_len].decode("utf-8", errors="replace")
            barcode = barcode.replace("\n", " ").replace("\r", " ")

            idx += barcode_len
            serial_len = data[idx]
            idx += 1
            if idx + serial_len > len(data):
                logger.error("Malformed RFID response: serial length exceeds data bounds")
                return None
            serial = data[idx : idx + serial_len].decode("utf-8", errors="replace")
            serial = serial.replace("\n", " ").replace("\r", " ")

            idx += serial_len
            if idx + 5 > len(data):
                logger.error("Malformed RFID response: not enough data for trailer fields")
                return None
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

    async def heartbeat(self) -> HeartbeatResponse:
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

    async def set_label_type(self, n: int) -> bool:
        if not 1 <= n <= 3:
            raise PrinterException(f"Label type must be 1-3, got {n}")
        packet = await self.send_command(RequestCodeEnum.SET_LABEL_TYPE, bytes((n,)))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for SET_LABEL_TYPE")
        return bool(packet.data[0])

    async def set_label_density(self, n: int) -> bool:
        if not 1 <= n <= 5:
            raise PrinterException(f"Label density must be 1-5, got {n}")
        packet = await self.send_command(RequestCodeEnum.SET_LABEL_DENSITY, bytes((n,)))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for SET_LABEL_DENSITY")
        return bool(packet.data[0])

    async def start_print(self) -> bool:
        packet = await self.send_command(RequestCodeEnum.START_PRINT, b"\x01")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for START_PRINT")
        return bool(packet.data[0])

    async def start_print_v2(self, quantity: int) -> bool:
        if not 1 <= quantity <= 65535:
            raise PrinterException(f"Quantity must be 1-65535, got {quantity}")
        command = struct.pack(">H", quantity)
        packet = await self.send_command(RequestCodeEnum.START_PRINT, b"\x00" + command + b"\x00\x00\x00\x00")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for START_PRINT")
        return bool(packet.data[0])

    async def start_print_v4(self, quantity: int, speed: int = 2, page_color: int = 0) -> bool:
        """V4 protocol (D110_M 2025): 9-byte PrintStart per NiimBlueLib.

        Format: totalPages(2) + zeros(4) + pageColor(1) + speed(1) + flag(1)
        """
        if not 1 <= quantity <= 65535:
            raise PrinterException(f"Quantity must be 1-65535, got {quantity}")
        if not 0 <= speed <= 255:
            raise PrinterException(f"Speed must be 0-255, got {speed}")
        # NiimBlueLib format: totalPages(u16 BE) + 4 zeros + pageColor + speed + flag(0x01)
        data = struct.pack(">H", quantity) + b"\x00\x00\x00\x00" + bytes([page_color, speed, 0x01])
        logger.debug(f"start_print_v4: {list(data)}")
        packet = await self.send_command(RequestCodeEnum.START_PRINT, data)
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for START_PRINT_V4")
        return bool(packet.data[0])

    async def end_print(self) -> bool:
        packet = await self.send_command(RequestCodeEnum.END_PRINT, b"\x01")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for END_PRINT")
        return bool(packet.data[0])

    async def start_page_print(self) -> bool:
        packet = await self.send_command(RequestCodeEnum.START_PAGE_PRINT, b"\x01")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for START_PAGE_PRINT")
        return bool(packet.data[0])

    async def end_page_print(self) -> bool:
        packet = await self.send_command(RequestCodeEnum.END_PAGE_PRINT, b"\x01")
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for END_PAGE_PRINT")
        return bool(packet.data[0])

    async def set_dimension(self, height: int, width: int) -> bool:
        if not 1 <= height <= 65535:
            raise PrinterException(f"Height must be 1-65535, got {height}")
        if not 1 <= width <= 65535:
            raise PrinterException(f"Width must be 1-65535, got {width}")
        packet = await self.send_command(RequestCodeEnum.SET_DIMENSION, struct.pack(">HH", height, width))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for SET_DIMENSION")
        return bool(packet.data[0])

    async def set_dimension_v2(self, height: int, width: int, copies: int) -> bool:
        if not 1 <= height <= 65535:
            raise PrinterException(f"Height must be 1-65535, got {height}")
        if not 1 <= width <= 65535:
            raise PrinterException(f"Width must be 1-65535, got {width}")
        if not 1 <= copies <= 65535:
            raise PrinterException(f"Copies must be 1-65535, got {copies}")
        logger.debug(f"Setting dimension: {height}x{width}")
        packet = await self.send_command(RequestCodeEnum.SET_DIMENSION, struct.pack(">HHH", height, width, copies))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for SET_DIMENSION")
        return bool(packet.data[0])

    async def set_dimension_v4(self, height: int, width: int, copies: int) -> bool:
        """V4 protocol (D110_M 2025): 13-byte SetPageSize per NiimBlueLib.

        Format: rows(2) + cols(2) + copiesCount(2) + cutHeight(2) + cutType(1) + zero(1) + sendAll(1) + partHeight(2)
        """
        if not 1 <= height <= 65535:
            raise PrinterException(f"Height must be 1-65535, got {height}")
        if not 1 <= width <= 65535:
            raise PrinterException(f"Width must be 1-65535, got {width}")
        if not 1 <= copies <= 65535:
            raise PrinterException(f"Copies must be 1-65535, got {copies}")
        # NiimBlueLib format with sendAll=1 at byte 10
        # cutHeight=0, cutType=0, zero=0, sendAll=1, partHeight=0
        data = struct.pack(">HHH", height, width, copies) + b"\x00\x00\x00\x00\x01\x00\x00"
        logger.debug(f"set_dimension_v4: height={height}, width={width}, copies={copies}, data={list(data)}")
        packet = await self.send_command(RequestCodeEnum.SET_DIMENSION, data)
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for SET_DIMENSION_V4")
        return bool(packet.data[0])

    async def set_quantity(self, n: int) -> bool:
        if not 1 <= n <= 65535:
            raise PrinterException(f"Quantity must be 1-65535, got {n}")
        packet = await self.send_command(RequestCodeEnum.SET_QUANTITY, struct.pack(">H", n))
        if len(packet.data) < 1:
            raise PrinterException("Empty response from printer for SET_QUANTITY")
        return bool(packet.data[0])

    async def get_print_status(self) -> PrintStatus:
        packet = await self.send_command(RequestCodeEnum.GET_PRINT_STATUS, b"\x01")
        if len(packet.data) < 4:
            raise PrinterException(f"get_print_status: short response ({len(packet.data)} bytes)")
        page, progress1, progress2 = struct.unpack(">HBB", packet.data[:4])
        return {"page": page, "progress1": progress1, "progress2": progress2}

    async def get_print_status_v4(self) -> PrintStatus:
        """V4 protocol (D110_M): 8-byte status with page count in bytes 6-7."""
        packet = await self.send_command(RequestCodeEnum.GET_PRINT_STATUS, b"\x01")
        if len(packet.data) < 8:
            # Fall back to V1 parsing for shorter responses
            if len(packet.data) >= 4:
                page, progress1, progress2 = struct.unpack(">HBB", packet.data[:4])
                return {"page": page, "progress1": progress1, "progress2": progress2}
            raise PrinterException(f"get_print_status_v4: short response ({len(packet.data)} bytes)")
        # V4 format: bytes 6-7 contain page count (big-endian)
        page = struct.unpack(">H", packet.data[6:8])[0]
        logger.debug(f"V4 status: page={page} (from bytes 6-7 of {list(packet.data)})")
        return {"page": page, "progress1": 0, "progress2": 0}
