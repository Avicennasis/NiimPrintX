"""UI-layer TypedDicts for canvas items.

Available for future UI type annotations (e.g., text and image canvas objects).
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class FontProps(TypedDict):
    family: str
    size: int | float
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
    initial_x: NotRequired[int]
    initial_y: NotRequired[int]
    initial_size: NotRequired[int]


class ImageItem(TypedDict):
    image: Any
    original_image: Any
    bbox: int | None
    handle: int | None
    initial_x: NotRequired[int]
    initial_y: NotRequired[int]
