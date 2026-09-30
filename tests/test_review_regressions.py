"""September review regression coverage."""

from types import SimpleNamespace

import pytest
from PIL import Image

from NiimPrintX.ui.__main__ import resource_path
from NiimPrintX.ui.widget.TabbedIconGrid import TabbedIconGrid


def test_source_splash_resource_exists():
    from pathlib import Path

    assert Path(resource_path("NiimPrintX/ui/assets/Niimprintx.png")).is_file()


def test_destroyed_icon_frame_releases_rasters():
    image = Image.new("RGBA", (4, 4))
    frame = SimpleNamespace(winfo_exists=lambda: False)
    TabbedIconGrid._create_icon_widgets(SimpleNamespace(), frame, [("icon.png", image, "tab")], "tab", object())
    with pytest.raises(ValueError, match="closed"):
        image.getpixel((0, 0))


def test_failed_icon_callback_releases_rasters(tmp_path, monkeypatch):
    folder = tmp_path / "50x50"
    folder.mkdir()
    with Image.new("RGBA", (4, 4)) as image:
        image.save(folder / "icon.png")
    captured = []

    def fail_after(_, callback):
        captured.append(callback.__closure__)
        raise RuntimeError("main thread is not in main loop")

    grid = SimpleNamespace(after=fail_after)
    TabbedIconGrid.load_icons(grid, object(), str(tmp_path), "tab", object())
    images = next(cell.cell_contents for cell in captured[0] if isinstance(cell.cell_contents, list))
    with pytest.raises(ValueError, match="closed"):
        images[0][1].getpixel((0, 0))


@pytest.mark.parametrize("cache", [[], None, 42, {"Arial": []}])
def test_invalid_font_cache_is_regenerated(tmp_path, monkeypatch, cache):
    import json

    from NiimPrintX.ui.component.FontList import _load_disk_cache

    (tmp_path / "font_cache.json").write_text(json.dumps(cache))
    monkeypatch.setattr("NiimPrintX.ui.component.FontList._get_cache_dir", lambda: str(tmp_path))
    assert _load_disk_cache(None) is None
