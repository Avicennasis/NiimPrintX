import pytest
from PIL import Image


@pytest.fixture
def small_image():
    """Create a small test image for D-series printers (240px wide)."""
    return Image.new("1", (240, 100), color=0)


@pytest.fixture
def wide_image():
    """Create a wider test image for B-series printers (384px wide)."""
    return Image.new("1", (384, 200), color=0)
