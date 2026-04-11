import os
import tomllib

from appdirs import user_config_dir
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
    """Validate that dims is a list/tuple of 2 numbers."""
    if not isinstance(dims, (list, tuple)) or len(dims) != 2:
        return None
    try:
        return (float(dims[0]), float(dims[1]))
    except (TypeError, ValueError):
        return None


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
            for k, v in device_conf.get("size", {}).items() if isinstance(device_conf.get("size", {}), dict) else []:
                validated = _validate_dims(v)
                if validated:
                    sizes[k] = validated
            if not sizes:
                continue
            builtin_sizes[device_name] = {
                "size": sizes,
                "density": int(device_conf.get("density", 3)),
                "print_dpi": int(device_conf.get("print_dpi", 203)),
                "rotation": int(device_conf.get("rotation", -90)),
            }
    return builtin_sizes
