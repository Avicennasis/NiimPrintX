from __future__ import annotations

import os
import platform
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import platformdirs


class ImmutableConfig:
    """Platform detection, paths, and static device configuration."""

    def __init__(
        self,
        load_user_config: Callable[[], dict[str, Any]] | None = None,
        merge_label_sizes: Callable[[dict, dict], dict] | None = None,
    ) -> None:
        self.os_system: str = platform.system()
        self.current_dir: str = os.path.dirname(os.path.realpath(__file__))
        self.icon_folder: str = os.path.join(self.current_dir, "icons")
        self.cache_dir: str = platformdirs.user_cache_dir("NiimPrintX")
        self.label_sizes: dict = {
            "d110": {
                "size": {
                    "30mm x 15mm": (30, 15),
                    "40mm x 12mm": (40, 12),
                    "50mm x 14mm": (50, 14),
                    "75mm x 12mm": (75, 12),
                    "109mm x 12.5mm": (109, 12.5),
                },
                "density": 3,
                "print_dpi": 203,
                "rotation": 270,
            },
            "d11": {
                "size": {
                    "30mm x 14mm": (30, 14),
                    "40mm x 12mm": (40, 12),
                    "50mm x 14mm": (50, 14),
                    "75mm x 12mm": (75, 12),
                    "109mm x 12.5mm": (109, 12.5),
                },
                "density": 3,
                "print_dpi": 203,
                "rotation": 270,
            },
            "d11_h": {
                "size": {
                    "30mm x 14mm": (30, 14),
                    "40mm x 12mm": (40, 12),
                    "50mm x 14mm": (50, 14),
                    "75mm x 12mm": (75, 12),
                    "109mm x 12.5mm": (109, 12.5),
                },
                "density": 3,
                "print_dpi": 300,
                "rotation": 270,
            },
            "d101": {
                "size": {
                    "30mm x 14mm": (30, 14),
                    "40mm x 12mm": (40, 12),
                    "50mm x 14mm": (50, 14),
                    "75mm x 12mm": (75, 12),
                    "109mm x 12.5mm": (109, 12.5),
                },
                "density": 3,
                "print_dpi": 203,
                "rotation": 270,
            },
            "d110_m": {
                "size": {
                    "30mm x 15mm": (30, 15),
                    "40mm x 12mm": (40, 12),
                    "50mm x 14mm": (50, 14),
                    "75mm x 12mm": (75, 12),
                    "109mm x 12.5mm": (109, 12.5),
                },
                "density": 3,
                "print_dpi": 300,
                "rotation": 270,
            },
            "b18": {
                "size": {
                    "40mm x 14mm": (40, 14),
                    "50mm x 14mm": (50, 14),
                    "120mm x 14mm": (120, 14),
                },
                "density": 3,
                "print_dpi": 203,
                "rotation": 0,
            },
            "b21": {
                "size": {
                    "50mm x 30mm": (50, 30),
                    "40mm x 30mm": (40, 30),
                    "50mm x 15mm": (50, 15),
                    "30mm x 15mm": (30, 15),
                },
                "density": 5,
                "print_dpi": 203,
                "rotation": 0,
            },
            "b1": {
                "size": {
                    "50mm x 30mm": (50, 30),
                    "50mm x 15mm": (50, 15),
                    "60mm x 40mm": (60, 40),
                    "40mm x 30mm": (40, 30),
                },
                "density": 3,
                "print_dpi": 203,
                "rotation": 0,
            },
        }
        if load_user_config is not None and merge_label_sizes is not None:
            user_config = load_user_config()
            if user_config:
                self.label_sizes = merge_label_sizes(self.label_sizes, user_config)


class CanvasState:
    """Mutable editor/canvas state. Tk main thread only."""

    def __init__(self) -> None:
        self.canvas = None
        self.bounding_box = None
        self.text_items: dict = {}
        self.image_items: dict = {}
        self.current_selected = None
        self.current_selected_image = None
        self.frames: dict = {}


class PrinterState:
    """Mutable printer selection and connection state."""

    def __init__(self, default_device: str) -> None:
        self.device: str = default_device
        self.current_label_size = None
        self.printer_connected: bool = False
        self.print_job: bool = False


def mm_to_pixels(mm: float, dpi: int) -> int:
    """Convert millimeters to pixels at the given DPI."""
    return round((mm / 25.4) * dpi)
