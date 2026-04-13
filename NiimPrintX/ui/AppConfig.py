from __future__ import annotations

from NiimPrintX.nimmy.userconfig import load_user_config, merge_label_sizes

from .config import (
    CanvasState,
    ImmutableConfig,
    PrinterState,
)
from .config import (
    mm_to_pixels as _mm_to_pixels,
)


class AppConfig:
    def __init__(self) -> None:
        self._immutable = ImmutableConfig(
            load_user_config=load_user_config,
            merge_label_sizes=merge_label_sizes,
        )
        self._canvas = CanvasState()
        self._printer = PrinterState(default_device=next(iter(self._immutable.label_sizes)))

    @property
    def immutable(self) -> ImmutableConfig:
        return self._immutable

    @property
    def canvas_state(self) -> CanvasState:
        return self._canvas

    @property
    def printer_state(self) -> PrinterState:
        return self._printer

    # --- ImmutableConfig delegators ---
    @property
    def os_system(self) -> str:
        return self._immutable.os_system

    @property
    def current_dir(self) -> str:
        return self._immutable.current_dir

    @property
    def icon_folder(self) -> str:
        return self._immutable.icon_folder

    @property
    def cache_dir(self) -> str:
        return self._immutable.cache_dir

    @property
    def label_sizes(self) -> dict:
        return self._immutable.label_sizes

    # --- CanvasState delegators ---
    @property
    def canvas(self):
        return self._canvas.canvas

    @canvas.setter
    def canvas(self, value) -> None:
        self._canvas.canvas = value

    @property
    def bounding_box(self):
        return self._canvas.bounding_box

    @bounding_box.setter
    def bounding_box(self, value) -> None:
        self._canvas.bounding_box = value

    @property
    def text_items(self) -> dict:
        return self._canvas.text_items

    @text_items.setter
    def text_items(self, value: dict) -> None:
        self._canvas.text_items = value

    @property
    def image_items(self) -> dict:
        return self._canvas.image_items

    @image_items.setter
    def image_items(self, value: dict) -> None:
        self._canvas.image_items = value

    @property
    def current_selected(self):
        return self._canvas.current_selected

    @current_selected.setter
    def current_selected(self, value) -> None:
        self._canvas.current_selected = value

    @property
    def current_selected_image(self):
        return self._canvas.current_selected_image

    @current_selected_image.setter
    def current_selected_image(self, value) -> None:
        self._canvas.current_selected_image = value

    @property
    def frames(self) -> dict:
        return self._canvas.frames

    @frames.setter
    def frames(self, value: dict) -> None:
        self._canvas.frames = value

    # --- PrinterState delegators ---
    @property
    def device(self) -> str:
        return self._printer.device

    @device.setter
    def device(self, value: str) -> None:
        self._printer.device = value

    @property
    def current_label_size(self):
        return self._printer.current_label_size

    @current_label_size.setter
    def current_label_size(self, value) -> None:
        self._printer.current_label_size = value

    @property
    def printer_connected(self) -> bool:
        return self._printer.printer_connected

    @printer_connected.setter
    def printer_connected(self, value: bool) -> None:
        self._printer.printer_connected = value

    @property
    def print_job(self) -> bool:
        return self._printer.print_job

    @print_job.setter
    def print_job(self, value: bool) -> None:
        self._printer.print_job = value

    def mm_to_pixels(self, mm: float) -> int:
        """Convert millimeters to pixels using the current device's DPI."""
        dpi = self._immutable.label_sizes[self._printer.device]["print_dpi"]
        return _mm_to_pixels(mm, dpi)
