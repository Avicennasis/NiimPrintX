from __future__ import annotations

from typing import Any, TypedDict


class HeartbeatResponse(TypedDict):
    closing_state: int | None
    power_level: int | None
    paper_state: int | None
    rfid_read_state: int | None


class RFIDResponse(TypedDict):
    uuid: str
    barcode: str
    serial: str
    used_len: int
    total_len: int
    type: int


class PrintStatus(TypedDict):
    page: int
    progress1: int
    progress2: int


class FontProps(TypedDict):
    family: str
    size: int
    slant: str
    weight: str
    underline: bool
    kerning: float


class TextItem(TypedDict):
    font_props: FontProps
    font_image: Any
    content: str
    handle: int | None
    bbox: int | None


class ImageItem(TypedDict):
    image: Any
    original_image: Any
    bbox: int | None
    handle: int | None
