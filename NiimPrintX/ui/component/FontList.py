from __future__ import annotations

import functools
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from typing import Any

import platformdirs

from NiimPrintX.nimmy.logger_config import get_logger

logger = get_logger()

_CACHE_FILENAME = "font_cache.json"


def _get_cache_dir() -> str:
    """Return the NiimPrintX cache directory path."""
    return platformdirs.user_cache_dir("NiimPrintX")


def _resolve_magick_path() -> tuple[str | None, bool]:
    """Resolve the magick binary path and whether it came from PATH fallback.

    Returns a (magick_path, path_fallback) tuple.
    """
    path_fallback = False
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
        imagemagick_base_path = os.path.join(base_path, "imagemagick")
        match platform.system():
            case "Darwin" | "Linux":
                magick_path = os.path.join(imagemagick_base_path, "bin", "magick")
            case "Windows":
                magick_path = os.path.join(imagemagick_base_path, "magick.exe")
            case _:
                magick_path = shutil.which("magick")
                if magick_path is None:
                    logger.warning("ImageMagick 'magick' not found in PATH")
                    return None, False
                path_fallback = True
                logger.warning("Using PATH fallback for 'magick': %s", magick_path)
        if not os.path.isfile(magick_path):
            path_fallback = True
            logger.warning("Bundled magick not found at %s; will try PATH", magick_path)
    else:
        magick_path = shutil.which("magick")
        if magick_path is None:
            logger.warning("ImageMagick 'magick' not found in PATH")
        else:
            path_fallback = True
            logger.debug("Using PATH fallback for 'magick': %s", magick_path)

    return magick_path, path_fallback


def _load_disk_cache(magick_path: str | None) -> dict[str, Any] | None:
    """Load the font cache from disk if it is still valid.

    The cache is valid when the cache file exists and its mtime is newer
    than the magick binary's mtime (i.e. the binary hasn't been replaced
    since we last cached).

    Returns the cached grouped-fonts dict, or None on cache miss.
    """
    try:
        cache_dir = _get_cache_dir()
        cache_file = os.path.join(cache_dir, _CACHE_FILENAME)
        if not os.path.isfile(cache_file):
            return None

        cache_mtime = os.path.getmtime(cache_file)

        # If we have a known magick path, invalidate when the binary is newer
        if magick_path is not None and os.path.isfile(magick_path):
            binary_mtime = os.path.getmtime(magick_path)
            if binary_mtime > cache_mtime:
                logger.info("Font disk cache invalidated (binary newer than cache)")
                return None

        with open(cache_file, encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)

        logger.info("Loaded font list from disk cache (%s)", cache_file)
        return data
    except Exception:  # noqa: BLE001 — best-effort cache; must not break app startup
        logger.warning("Failed to load font disk cache; will regenerate", exc_info=True)
        return None


def _save_disk_cache(data: dict[str, Any]) -> None:
    """Persist the grouped-fonts dict to the disk cache."""
    try:
        cache_dir = _get_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, _CACHE_FILENAME)
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        logger.info("Saved font list to disk cache (%s)", cache_file)
    except Exception:  # noqa: BLE001 — best-effort cache; must not break app startup
        logger.warning("Failed to save font disk cache", exc_info=True)


def _run_font_list(cmd: list[str]) -> dict[str, Any] | None:
    """Run a font-listing command and return grouped fonts, or None on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf8", timeout=10, check=False)
        if result.returncode != 0:
            logger.warning("Font list command failed (rc=%d): %s", result.returncode, result.stderr.strip()[:500])
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
def fonts() -> dict[str, Any]:
    magick_path, path_fallback = _resolve_magick_path()

    # Try disk cache before running the subprocess
    cached = _load_disk_cache(magick_path)
    if cached is not None:
        return cached

    if magick_path is not None:
        grouped = _run_font_list([magick_path, "-list", "font"])
        if grouped is not None:
            _save_disk_cache(grouped)
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
                _save_disk_cache(grouped)
                return grouped

    label = magick_path or "magick"
    logger.warning("ImageMagick at %s failed. Font list unavailable.", label)
    return {}


def parse_font_details(output: str) -> list[dict[str, str]]:
    font_details: list[dict[str, str]] = []
    font: dict[str, str] = {}
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


def group_fonts_by_family(fonts_details: list[dict[str, str]]) -> dict[str, Any]:
    variant_pattern = re.compile(r"-(Bold-Italic|Italic|Bold|Regular|Oblique)$")
    grouped_fonts: defaultdict[str, dict[str, Any]] = defaultdict(lambda: {"family_name": "", "fonts": {}})

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

    sorted_grouped_fonts: dict[str, Any] = {}
    for family in sorted(grouped_fonts):
        sorted_grouped_fonts[family] = grouped_fonts[family]
        sorted_grouped_fonts[family]["fonts"] = dict(sorted_grouped_fonts[family]["fonts"])

    return sorted_grouped_fonts
