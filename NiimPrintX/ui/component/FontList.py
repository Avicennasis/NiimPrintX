import functools
import os
import platform
import re
import shutil
import subprocess
import sys
from collections import defaultdict

from NiimPrintX.nimmy.logger_config import get_logger

logger = get_logger()


def _run_font_list(cmd):
    """Run a font-listing command and return grouped fonts, or None on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf8", timeout=10, check=False)
        if result.returncode != 0:
            return None
        output = result.stdout
        if not output.strip():
            logger.warning("ImageMagick returned no font data")
            return {}
        fonts_details = parse_font_details(output)
        return group_fonts_by_family(fonts_details)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


@functools.lru_cache(maxsize=1)
def fonts():
    path_fallback = False
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
        imagemagick_base_path = os.path.join(base_path, "imagemagick")
        if platform.system() == "Darwin":
            magick_path = os.path.join(imagemagick_base_path, "bin", "magick")
        elif platform.system() == "Windows":
            magick_path = os.path.join(imagemagick_base_path, "magick.exe")
        elif platform.system() == "Linux":
            magick_path = os.path.join(imagemagick_base_path, "bin", "magick")
        else:
            magick_path = shutil.which("magick")
            if magick_path is None:
                logger.warning("ImageMagick 'magick' not found in PATH")
                return {}
            path_fallback = True
            logger.warning("Using PATH fallback for 'magick': %s", magick_path)
    else:
        magick_path = shutil.which("magick")
        if magick_path is None:
            logger.warning("ImageMagick 'magick' not found in PATH")
            # Still try the IM6 convert fallback below
        else:
            path_fallback = True
            logger.warning("Using PATH fallback for 'magick': %s", magick_path)

    if magick_path is not None:
        grouped = _run_font_list([magick_path, "-list", "font"])
        if grouped is not None:
            return grouped

    # Fallback to IM6 'convert' on non-Windows when using system magick
    if (magick_path is None or path_fallback) and platform.system() != "Windows":
        convert_path = shutil.which("convert")
        if convert_path is None:
            logger.warning("ImageMagick 'convert' not found in PATH")
        else:
            logger.warning("Using PATH fallback for 'convert': %s", convert_path)
            grouped = _run_font_list([convert_path, "-list", "font"])
            if grouped is not None:
                return grouped

    label = magick_path or "magick"
    logger.warning("ImageMagick at %s failed. Font list unavailable.", label)
    return {}


def parse_font_details(output):
    font_details = []
    font = {}
    for line in output.splitlines():
        if line.startswith("  Font:"):
            if font:
                font_details.append(font)
                font = {}
            font["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("    family:"):
            font["family"] = line.split(":", 1)[1].strip()
        elif line.startswith("    style:"):
            font["style"] = line.split(":", 1)[1].strip()
        elif line.startswith("    stretch:"):
            font["stretch"] = line.split(":", 1)[1].strip()
        elif line.startswith("    weight:"):
            font["weight"] = line.split(":", 1)[1].strip()
        elif line.startswith("    glyphs:"):
            font["glyphs"] = line.split(":", 1)[1].strip()
    if font:
        font_details.append(font)
    return font_details


def group_fonts_by_family(fonts_details):
    variant_pattern = re.compile(r"-(Bold-Italic|Italic|Bold|Regular|Oblique)$")
    grouped_fonts = defaultdict(lambda: {"family_name": "", "fonts": {}})

    for font in fonts_details:
        family = font.get("family", "Unknown")
        if family.startswith((".", "System")):
            continue
        name = font.get("name")
        if not name:
            continue
        variant_match = variant_pattern.search(name)
        variant = variant_match.group(1) if variant_match else "Other"
        base_name = name[: variant_match.start()] if variant_match else name
        font_name_key = base_name.replace("-", " ")

        if font_name_key not in grouped_fonts[family]["fonts"]:
            grouped_fonts[family]["fonts"][font_name_key] = {
                "name": base_name,
                "main": variant == "Other",
                "variants": [],
            }

        if variant == "Other":
            grouped_fonts[family]["fonts"][font_name_key]["main"] = True
        else:
            grouped_fonts[family]["fonts"][font_name_key]["variants"].append(variant)

        grouped_fonts[family]["family_name"] = family

    sorted_grouped_fonts = {}
    for family in sorted(grouped_fonts):
        sorted_grouped_fonts[family] = grouped_fonts[family]
        sorted_grouped_fonts[family]["fonts"] = dict(sorted_grouped_fonts[family]["fonts"])

    return sorted_grouped_fonts
