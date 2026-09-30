"""September review regression coverage."""

import pytest

from NiimPrintX.nimmy.userconfig import merge_label_sizes
from NiimPrintX.ui.config import ImmutableConfig


@pytest.mark.parametrize(
    ("rotation", "expected"), [(0, 0), (90, 90), (180, 180), (270, 270), (-90, 270), (45, 270), (True, 270)]
)
def test_builtin_rotation_override(rotation, expected):
    original = ImmutableConfig().label_sizes
    merged = merge_label_sizes(original, {"devices": {"d110": {"rotation": rotation}}})
    assert merged["d110"]["rotation"] == expected
    assert original["d110"]["rotation"] == 270
    assert merged["d110"]["print_dpi"] == 203
