from __future__ import annotations

import copy
import math
import os
import tomllib
from typing import Any

from loguru import logger
from platformdirs import user_config_dir

CONFIG_DIR = user_config_dir("NiimPrintX")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.toml")


def load_user_config() -> dict[str, Any]:
    """Load user config, return empty dict if not found."""
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        logger.warning(f"User config is malformed (TOML parse error): {e}")
        return {}
    except OSError as e:
        logger.warning(f"Could not read user config file: {e}")
        return {}


def _validate_dims(dims: Any) -> tuple[float, float] | None:
    """Validate that dims is a list/tuple of 2 positive numbers."""
    if not isinstance(dims, (list, tuple)) or len(dims) != 2:
        return None
    try:
        w, h = float(dims[0]), float(dims[1])
        if not (math.isfinite(w) and math.isfinite(h)):
            return None
        if w <= 0 or h <= 0:
            return None
        return (w, h)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int) -> int:
    """Convert to int with fallback for invalid TOML values."""
    if isinstance(value, bool):
        logger.warning(f"Expected integer, got boolean {value!r}; using default {default}")
        return default
    if isinstance(value, float) and not value.is_integer():
        logger.warning(f"Expected integer, got {value}; using default {default}")
        return default
    if isinstance(value, float):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid config value {value!r}, using default {default}")
        return default


def merge_label_sizes(builtin_sizes: dict[str, Any], user_config: dict[str, Any]) -> dict[str, Any]:
    """Merge user device configs into built-in label sizes."""
    builtin_sizes = copy.deepcopy(builtin_sizes)
    user_devices = user_config.get("devices", {})
    for device_name, device_conf in user_devices.items():
        if not isinstance(device_conf, dict):
            continue
        if device_name in builtin_sizes:
            # Warn about ignored keys for built-in devices
            ignored = {k for k in device_conf if k != "size"}
            if ignored:
                logger.warning(
                    f"Config keys {ignored} for built-in device '{device_name}' are ignored; only 'size' can be extended"
                )
            # Merge sizes into existing device
            if "size" in device_conf and isinstance(device_conf["size"], dict):
                for label, dims in device_conf["size"].items():
                    validated = _validate_dims(dims)
                    if validated:
                        builtin_sizes[device_name]["size"][label] = validated
                    else:
                        logger.warning(f"Skipping invalid dims for {device_name!r} label {label!r}: {dims!r}")
        else:
            # Add entirely new device — require at least one valid size
            sizes = {}
            raw_sizes = device_conf.get("size")
            if isinstance(raw_sizes, dict):
                for k, v in raw_sizes.items():
                    validated = _validate_dims(v)
                    if validated:
                        sizes[k] = validated
                    else:
                        logger.warning(f"Skipping invalid dims for {device_name!r} label {k!r}: {v!r}")
            if not sizes:
                continue
            raw_rot = _safe_int(device_conf.get("rotation", -90), -90) % 360
            if raw_rot not in (0, 90, 180, 270):
                logger.warning(f"Invalid rotation {raw_rot} for '{device_name}'; defaulting to 270")
                raw_rot = 270
            builtin_sizes[device_name] = {
                "size": sizes,
                "density": max(1, min(_safe_int(device_conf.get("density", 3), 3), 5)),
                "print_dpi": max(72, min(_safe_int(device_conf.get("print_dpi", 203), 203), 600)),
                "rotation": raw_rot,
            }
    return builtin_sizes
