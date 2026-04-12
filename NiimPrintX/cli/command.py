from __future__ import annotations

import asyncio
import sys

import click
from PIL import Image

from NiimPrintX.nimmy.bluetooth import find_device
from NiimPrintX.nimmy.helper import print_error, print_info, print_success
from NiimPrintX.nimmy.logger_config import get_logger, logger_enable, setup_logger
from NiimPrintX.nimmy.printer import DEFAULT_MAX_DENSITY, MODEL_MAX_DENSITY, V2_MODELS, InfoEnum, PrinterClient

# Max print width per model in pixels (derived from label width x DPI)
# V2 models (b1/b18/b21) use 384px; 300 DPI models use 354px (30mm @ 300 DPI)
MODEL_MAX_WIDTH = {"d11_h": 354, "d110_m": 354}
DEFAULT_MAX_WIDTH_V1 = 240  # 30mm @ 203 DPI

logger = get_logger()

_ALL_MODELS = ["b1", "b18", "b21", "d11", "d11_h", "d101", "d110", "d110_m"]


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging",
)
def niimbot_cli(verbose: int) -> None:
    setup_logger()
    logger_enable(verbose)


@niimbot_cli.command("print")
@click.option(
    "-m",
    "--model",
    type=click.Choice(_ALL_MODELS, case_sensitive=False),
    default="d110",
    show_default=True,
    help="Niimbot printer model",
)
@click.option(
    "-d",
    "--density",
    type=click.IntRange(1, 5),
    default=3,
    show_default=True,
    help="Print density",
)
@click.option(
    "-n",
    "--quantity",
    type=click.IntRange(1, 65535),
    default=1,
    show_default=True,
    help="Print quantity",
)
@click.option(
    "--vo",
    "vertical_offset",
    type=int,
    default=0,
    show_default=True,
    help="Vertical offset in pixels",
)
@click.option(
    "--ho",
    "horizontal_offset",
    type=int,
    default=0,
    show_default=True,
    help="Horizontal offset in pixels",
)
@click.option(
    "-r",
    "--rotate",
    type=click.Choice(["0", "90", "180", "270"]),
    default="0",
    show_default=True,
    help="Image rotation (clockwise)",
)
@click.option(
    "-i",
    "--image",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    required=True,
    help="Image path",
)
def print_command(
    model: str, density: int, rotate: str, image: str, quantity: int, vertical_offset: int, horizontal_offset: int
) -> None:
    logger.info("Niimbot Printing Start")

    max_width_px = 384 if model in V2_MODELS else MODEL_MAX_WIDTH.get(model, DEFAULT_MAX_WIDTH_V1)

    # Cap density to the per-model hardware limit
    max_density = MODEL_MAX_DENSITY.get(model, DEFAULT_MAX_DENSITY)
    if density > max_density:
        print_info(f"Model {model.upper()} supports max density {max_density}; capping {density} to {max_density}")
        density = max_density
    Image.MAX_IMAGE_PIXELS = 5_000_000
    try:
        with Image.open(image) as raw_img:
            # PIL library rotates counterclockwise, so we need to multiply by -1
            rotated = raw_img.rotate(-int(rotate), expand=True) if rotate != "0" else None
            prepared = rotated if rotated is not None else raw_img
            try:
                if prepared.width > max_width_px:
                    print_error(f"Image width {prepared.width}px exceeds max {max_width_px}px for {model.upper()}")
                    sys.exit(1)
                _MAX_HEIGHT_PX = 65535  # 16-bit row index protocol limit
                if prepared.height > _MAX_HEIGHT_PX:
                    print_error(f"Image height {prepared.height}px exceeds protocol limit")
                    sys.exit(1)
                success = asyncio.run(_print(model, density, prepared, quantity, vertical_offset, horizontal_offset))
                if not success:
                    sys.exit(1)
            finally:
                if rotated is not None:
                    rotated.close()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print_error("Interrupted")
        sys.exit(1)
    except Exception as e:
        print_error(f"{e}")
        sys.exit(1)


async def _print(
    model: str, density: int, image: Image.Image, quantity: int, vertical_offset: int, horizontal_offset: int
) -> bool:
    printer: PrinterClient | None = None
    try:
        print_info("Starting print job")
        device = await find_device(model)
        printer = PrinterClient(device)
        if not await printer.connect():
            print_error("Failed to connect to printer")
            return False
        print_info(f"Connected to {device.name!r}")
        if model in V2_MODELS:
            print_info("Printing with V2 protocol")
            await printer.print_imageV2(
                image,
                density=density,
                quantity=quantity,
                vertical_offset=vertical_offset,
                horizontal_offset=horizontal_offset,
            )
        else:
            print_info("Printing with V1 protocol")
            await printer.print_image(
                image,
                density=density,
                quantity=quantity,
                vertical_offset=vertical_offset,
                horizontal_offset=horizontal_offset,
            )
        print_success("Print job completed")
        return True
    except Exception as e:
        logger.opt(exception=True).debug(f"Command failed: {e}")
        print_error(f"{e}")
        return False
    finally:
        if printer:
            await printer.disconnect()


@niimbot_cli.command("info")
@click.option(
    "-m",
    "--model",
    type=click.Choice(_ALL_MODELS, case_sensitive=False),
    default="d110",
    show_default=True,
    help="Niimbot printer model",
)
def info_command(model: str) -> None:
    logger.info("Niimbot Information")
    print_info("Niimbot Information")
    success = False
    try:
        success = asyncio.run(_info(model))
    except KeyboardInterrupt:
        print_error("Interrupted")
        sys.exit(1)
    except Exception as e:
        print_error(f"{e}")
        sys.exit(1)
    if not success:
        sys.exit(1)


async def _info(model: str) -> bool:
    printer: PrinterClient | None = None
    try:
        device = await find_device(model)
        printer = PrinterClient(device)
        if not await printer.connect():
            print_error("Failed to connect to printer")
            return False
        device_serial = await printer.get_info(InfoEnum.DEVICESERIAL)
        software_version = await printer.get_info(InfoEnum.SOFTVERSION)
        hardware_version = await printer.get_info(InfoEnum.HARDVERSION)
        print_info(f"Device Serial : {device_serial}")
        print_info(f"Software Version : {software_version}")
        print_info(f"Hardware Version : {hardware_version}")
        return True
    except Exception as e:
        logger.opt(exception=True).debug(f"Command failed: {e}")
        print_error(f"{e}")
        return False
    finally:
        if printer:
            await printer.disconnect()


if __name__ == "__main__":
    niimbot_cli()
