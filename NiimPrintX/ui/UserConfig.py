import os
import tomllib

from platformdirs import user_config_dir
from loguru import logger

CONFIG_DIR = user_config_dir("NiimPrintX")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.toml")


def load_user_config():
    """Load user config, return empty dict if not found."""
    if not os.path.isfile(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        logger.warning(f"Failed to load user config: {e}")
        return {}


def _validate_dims(dims):
    """Validate that dims is a list/tuple of 2 positive numbers."""
    if not isinstance(dims, (list, tuple)) or len(dims) != 2:
        return None
    try:
        w, h = float(dims[0]), float(dims[1])
        if w <= 0 or h <= 0:
            return None
        return (w, h)
    except (TypeError, ValueError):
        return None


def _safe_int(value, default):
    """Convert to int with fallback for invalid TOML values."""
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid config value {value!r}, using default {default}")
        return default


def merge_label_sizes(builtin_sizes, user_config):
    """Merge user device configs into built-in label sizes."""
    user_devices = user_config.get("devices", {})
    for device_name, device_conf in user_devices.items():
        if not isinstance(device_conf, dict):
            continue
        if device_name in builtin_sizes:
            # Merge sizes into existing device
            if "size" in device_conf and isinstance(device_conf["size"], dict):
                for label, dims in device_conf["size"].items():
                    validated = _validate_dims(dims)
                    if validated:
                        builtin_sizes[device_name]["size"][label] = validated
        else:
            # Add entirely new device — require at least one valid size
            sizes = {}
            raw_sizes = device_conf.get("size")
            if isinstance(raw_sizes, dict):
                for k, v in raw_sizes.items():
                    validated = _validate_dims(v)
                    if validated:
                        sizes[k] = validated
            if not sizes:
                continue
            builtin_sizes[device_name] = {
                "size": sizes,
                "density": _safe_int(device_conf.get("density", 3), 3),
                "print_dpi": _safe_int(device_conf.get("print_dpi", 203), 203),
                "rotation": _safe_int(device_conf.get("rotation", -90), -90),
            }
    return builtin_sizes
