import asyncio
import sys

import click
from PIL import Image

from NiimPrintX.nimmy.bluetooth import find_device
from NiimPrintX.nimmy.helper import print_error, print_info, print_success
from NiimPrintX.nimmy.logger_config import get_logger, logger_enable, setup_logger
from NiimPrintX.nimmy.printer import InfoEnum, PrinterClient

setup_logger()
logger = get_logger()


@click.group(context_settings={"help_option_names": ['-h', '--help']})
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Enable verbose logging",
)
@click.pass_context
def niimbot_cli(ctx, verbose):
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose
    logger_enable(verbose)


@niimbot_cli.command("print")
@click.option(
    "-m",
    "--model",
    type=click.Choice(["b1", "b18", "b21", "d11", "d11_h", "d110", "d101", "d110_m"], False),
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
    default=0,
    show_default=True,
    help="Vertical offset in pixels",
)
@click.option(
    "--ho",
    "horizontal_offset",
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
    type=click.Path(exists=True),
    required=True,
    help="Image path",
)
def print_command(model, density, rotate, image, quantity, vertical_offset, horizontal_offset):
    logger.info("Niimbot Printing Start")

    if model in ("b1", "b18", "b21"):
        max_width_px = 384
    elif model in ("d11", "d11_h", "d110", "d101", "d110_m"):
        max_width_px = 240
    else:
        max_width_px = 240

    # Cap density for models that only support 3 levels
    if model not in ("b21",) and density > 3:
        print_info(f"Model {model.upper()} supports max density 3; capping from {density}")
        density = 3
    try:
        image = Image.open(image)

        if rotate != "0":
            # PIL library rotates counterclockwise, so we need to multiply by -1
            image = image.rotate(-int(rotate), expand=True)
        if image.width > max_width_px:
            print_error(f"Image width {image.width}px exceeds max {max_width_px}px for {model.upper()}")
            sys.exit(1)
        success = asyncio.run(_print(model, density, image, quantity, vertical_offset, horizontal_offset))
        if not success:
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print_error(f"{e}")
        sys.exit(1)


async def _print(model, density, image, quantity, vertical_offset, horizontal_offset):
    printer = None
    try:
        print_info("Starting print job")
        device = await find_device(model)
        printer = PrinterClient(device)
        if not await printer.connect():
            print_error("Failed to connect to printer")
            return False
        print_info(f"Connected to {device.name}")
        if model == "b1":
            print_info("Printing with B1 model")
            await printer.print_imageV2(image, density=density, quantity=quantity)
        else:
            print_info("Printing with D model")
            await printer.print_image(image, density=density, quantity=quantity, vertical_offset=vertical_offset,
                                      horizontal_offset=horizontal_offset)
        print_success("Print job completed")
        return True
    except Exception as e:
        logger.debug(f"{e}")
        print_error(f"{e}")
        return False
    finally:
        if printer:
            await printer.disconnect()


@niimbot_cli.command("info")
@click.option(
    "-m",
    "--model",
    type=click.Choice(["b1", "b18", "b21", "d11", "d11_h", "d110", "d101", "d110_m"], False),
    default="d110",
    show_default=True,
    help="Niimbot printer model",
)
def info_command(model):
    logger.info("Niimbot Information")
    print_info("Niimbot Information")
    success = asyncio.run(_info(model))
    if not success:
        sys.exit(1)


async def _info(model):
    printer = None
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
        logger.debug(f"{e}")
        print_error(e)
        return False
    finally:
        if printer:
            await printer.disconnect()


cli = click.CommandCollection(sources=[niimbot_cli])
if __name__ == "__main__":
    niimbot_cli(obj={})
