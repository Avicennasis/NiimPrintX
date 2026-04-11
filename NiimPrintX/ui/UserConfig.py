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


def merge_label_sizes(builtin_sizes, user_config):
    """Merge user device configs into built-in label sizes."""
    user_devices = user_config.get("devices", {})
    for device_name, device_conf in user_devices.items():
        if device_name in builtin_sizes:
            # Merge sizes into existing device
            if "size" in device_conf:
                for label, dims in device_conf["size"].items():
                    builtin_sizes[device_name]["size"][label] = tuple(dims)
        else:
            # Add entirely new device
            builtin_sizes[device_name] = {
                "size": {k: tuple(v) for k, v in device_conf.get("size", {}).items()},
                "density": device_conf.get("density", 3),
                "print_dpi": device_conf.get("print_dpi", 203),
                "rotation": device_conf.get("rotation", -90),
            }
    return builtin_sizes
