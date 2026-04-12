import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from NiimPrintX.ui.component.FontList import (
    _load_disk_cache,
    _run_font_list,
    _save_disk_cache,
    fonts,
    group_fonts_by_family,
    parse_font_details,
)


@pytest.fixture(autouse=True)
def _clear_fonts_cache():
    """Clear the @lru_cache on fonts() before each test to prevent cross-test contamination."""
    fonts.cache_clear()
    yield
    fonts.cache_clear()


@pytest.fixture(autouse=True)
def _no_disk_cache():
    """Prevent disk cache side effects during tests."""
    with (
        patch("NiimPrintX.ui.component.FontList._load_disk_cache", return_value=None),
        patch("NiimPrintX.ui.component.FontList._save_disk_cache"),
    ):
        yield


# ---------- parse_font_details ----------

SINGLE_FONT_OUTPUT = """\
  Font: DejaVu-Sans
    family: DejaVu Sans
    style: Normal
    stretch: Normal
    weight: 400
    glyphs: /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
"""


def test_parse_font_details_single_font():
    """Well-formed ImageMagick output for one font returns one entry with all keys."""
    result = parse_font_details(SINGLE_FONT_OUTPUT)
    assert len(result) == 1
    font = result[0]
    assert font["name"] == "DejaVu-Sans"
    assert font["family"] == "DejaVu Sans"
    assert font["style"] == "Normal"
    assert font["stretch"] == "Normal"
    assert font["weight"] == "400"


def test_parse_font_details_empty_output():
    """Empty string returns an empty list."""
    assert parse_font_details("") == []


MISSING_FAMILY_OUTPUT = """\
  Font: Mystery-Font
    style: Italic
    stretch: Normal
    weight: 700
    glyphs: /usr/share/fonts/mystery.ttf
"""


def test_parse_font_details_missing_family():
    """Font entry without a family: line still has a name but no family key."""
    result = parse_font_details(MISSING_FAMILY_OUTPUT)
    assert len(result) == 1
    font = result[0]
    assert font["name"] == "Mystery-Font"
    assert "family" not in font


MULTI_FONT_OUTPUT = """\
  Font: DejaVu-Sans
    family: DejaVu Sans
    style: Normal
    stretch: Normal
    weight: 400
    glyphs: /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
  Font: DejaVu-Sans-Bold
    family: DejaVu Sans
    style: Normal
    stretch: Normal
    weight: 700
    glyphs: /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
"""


def test_parse_font_details_multiple_fonts():
    """Multiple font entries are each appended as separate dicts (covers lines 64-65)."""
    result = parse_font_details(MULTI_FONT_OUTPUT)
    assert len(result) == 2
    assert result[0]["name"] == "DejaVu-Sans"
    assert result[0]["weight"] == "400"
    assert result[1]["name"] == "DejaVu-Sans-Bold"
    assert result[1]["weight"] == "700"


# ---------- _run_font_list ----------


def test_run_font_list_success():
    """Successful subprocess returns grouped fonts dict."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = SINGLE_FONT_OUTPUT

    with patch("NiimPrintX.ui.component.FontList.subprocess.run", return_value=mock_result):
        result = _run_font_list(["magick", "-list", "font"])

    assert "DejaVu Sans" in result
    assert result["DejaVu Sans"]["family_name"] == "DejaVu Sans"


def test_run_font_list_nonzero_returncode():
    """Non-zero return code yields None."""
    mock_result = MagicMock()
    mock_result.returncode = 1

    with patch("NiimPrintX.ui.component.FontList.subprocess.run", return_value=mock_result):
        result = _run_font_list(["magick", "-list", "font"])

    assert result is None


def test_run_font_list_empty_output():
    """Empty stdout from subprocess returns an empty dict."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "   \n"

    with patch("NiimPrintX.ui.component.FontList.subprocess.run", return_value=mock_result):
        result = _run_font_list(["magick", "-list", "font"])

    assert result == {}


def test_run_font_list_timeout():
    """TimeoutExpired from subprocess returns None."""
    with patch(
        "NiimPrintX.ui.component.FontList.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="magick", timeout=10),
    ):
        result = _run_font_list(["magick", "-list", "font"])

    assert result is None


def test_run_font_list_file_not_found():
    """FileNotFoundError (binary missing) returns None."""
    with patch(
        "NiimPrintX.ui.component.FontList.subprocess.run",
        side_effect=FileNotFoundError("magick not found"),
    ):
        result = _run_font_list(["magick", "-list", "font"])

    assert result is None


# ---------- group_fonts_by_family ----------


def _make_font(name, family="TestFamily", style="Normal", stretch="Normal", weight="400"):
    """Helper to build a font dict matching parse_font_details output."""
    return {
        "name": name,
        "family": family,
        "style": style,
        "stretch": stretch,
        "weight": weight,
    }


def test_group_fonts_by_family_basic():
    """Fonts are grouped by family with variants detected from name suffix."""
    fonts = [
        _make_font("Roboto", family="Roboto"),
        _make_font("Roboto-Bold", family="Roboto"),
        _make_font("Roboto-Italic", family="Roboto"),
        _make_font("Roboto-Regular", family="Roboto"),
    ]
    grouped = group_fonts_by_family(fonts)
    assert "Roboto" in grouped

    roboto_fonts = grouped["Roboto"]["fonts"]
    assert "Roboto" in roboto_fonts

    variants = roboto_fonts["Roboto"]["variants"]
    assert "Bold" in variants
    assert "Italic" in variants
    assert "Regular" in variants


def test_group_fonts_by_family_filters_hidden():
    """Fonts whose family starts with '.' are excluded."""
    fonts = [
        _make_font("AppleSystemUIFont", family=".AppleSystemUIFont"),
        _make_font("Visible-Font", family="Visible"),
    ]
    grouped = group_fonts_by_family(fonts)
    assert ".AppleSystemUIFont" not in grouped
    assert "Visible" in grouped


def test_group_fonts_by_family_missing_name():
    """Font dict without a 'name' key is skipped without crashing."""
    fonts = [
        {"family": "Orphan", "style": "Normal"},  # no 'name'
        _make_font("GoodFont", family="GoodFamily"),
    ]
    grouped = group_fonts_by_family(fonts)
    assert "Orphan" not in grouped
    assert "GoodFamily" in grouped


def test_group_fonts_by_family_sorted():
    """Returned dict keys are sorted alphabetically."""
    fonts_list = [
        _make_font("Zebra", family="Zebra"),
        _make_font("Alpha", family="Alpha"),
        _make_font("Middle", family="Middle"),
    ]
    grouped = group_fonts_by_family(fonts_list)
    keys = list(grouped.keys())
    assert keys == sorted(keys)
    assert keys == ["Alpha", "Middle", "Zebra"]


# ---------- fonts() entry point ----------

FAKE_MEIPASS = "/tmp/fake_meipass"  # noqa: S108 — test-only dummy path
FAKE_GROUPED = {"FakeFamily": {"family_name": "FakeFamily", "fonts": {}}}


def test_fonts_bundled_path_macos():
    """Bundled (PyInstaller) macOS build constructs the correct magick path."""
    with (
        patch(
            "NiimPrintX.ui.component.FontList.hasattr",
            side_effect=lambda o, n: True if n == "_MEIPASS" else hasattr(o, n),
        ),
        patch.object(__import__("sys"), "_MEIPASS", FAKE_MEIPASS, create=True),
        patch("NiimPrintX.ui.component.FontList.platform") as mock_platform,
        patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=FAKE_GROUPED) as mock_run,
    ):
        mock_platform.system.return_value = "Darwin"
        result = fonts()

    expected_path = f"{FAKE_MEIPASS}/imagemagick/bin/magick"
    mock_run.assert_called_once_with([expected_path, "-list", "font"])
    assert result == FAKE_GROUPED


def test_fonts_bundled_path_windows():
    """Bundled (PyInstaller) Windows build constructs the correct magick path."""
    with (
        patch.object(__import__("sys"), "_MEIPASS", FAKE_MEIPASS, create=True),
        patch("NiimPrintX.ui.component.FontList.platform") as mock_platform,
        patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=FAKE_GROUPED) as mock_run,
    ):
        mock_platform.system.return_value = "Windows"
        result = fonts()

    # os.path.join is platform-dependent; on Linux it uses '/' even for a
    # "Windows" platform.system() mock.  Verify the path components instead.
    actual_path = mock_run.call_args[0][0][0]
    assert actual_path.startswith(FAKE_MEIPASS)
    assert "imagemagick" in actual_path
    assert actual_path.endswith("magick.exe")
    mock_run.assert_called_once()
    assert result == FAKE_GROUPED


def test_fonts_bundled_path_linux():
    """Bundled (PyInstaller) Linux build constructs the correct magick path (covers lines 37-38)."""
    with (
        patch.object(__import__("sys"), "_MEIPASS", FAKE_MEIPASS, create=True),
        patch("NiimPrintX.ui.component.FontList.platform") as mock_platform,
        patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=FAKE_GROUPED) as mock_run,
    ):
        mock_platform.system.return_value = "Linux"
        result = fonts()

    expected_path = f"{FAKE_MEIPASS}/imagemagick/bin/magick"
    mock_run.assert_called_once_with([expected_path, "-list", "font"])
    assert result == FAKE_GROUPED


def test_fonts_bundled_path_unknown_platform():
    """Bundled build on unknown platform falls back to shutil.which('magick')."""
    with (
        patch.object(__import__("sys"), "_MEIPASS", FAKE_MEIPASS, create=True),
        patch("NiimPrintX.ui.component.FontList.platform") as mock_platform,
        patch("NiimPrintX.ui.component.FontList.shutil") as mock_shutil,
        patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=FAKE_GROUPED) as mock_run,
    ):
        mock_platform.system.return_value = "FreeBSD"
        mock_shutil.which.return_value = "/usr/local/bin/magick"
        result = fonts()

    mock_run.assert_called_once_with(["/usr/local/bin/magick", "-list", "font"])
    assert result == FAKE_GROUPED


def test_fonts_system_magick_success():
    """System magick succeeds on first try -- no convert fallback attempted."""
    with (
        patch("NiimPrintX.ui.component.FontList.shutil") as mock_shutil,
        patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=FAKE_GROUPED) as mock_run,
    ):
        mock_shutil.which.return_value = "/usr/bin/magick"
        # Ensure no _MEIPASS so we hit the system-magick branch
        if hasattr(__import__("sys"), "_MEIPASS"):
            delattr(__import__("sys"), "_MEIPASS")
        result = fonts()

    mock_run.assert_called_once_with(["/usr/bin/magick", "-list", "font"])
    assert result == FAKE_GROUPED


def test_fonts_system_magick_fails_convert_fallback():
    """When system magick fails, fonts() falls back to 'convert' and returns its result."""
    convert_result = {"ConvertFamily": {"family_name": "ConvertFamily", "fonts": {}}}

    def which_side_effect(name):
        return {
            "magick": "/usr/bin/magick",
            "convert": "/usr/bin/convert",
        }.get(name)

    with (
        patch("NiimPrintX.ui.component.FontList.shutil") as mock_shutil,
        patch("NiimPrintX.ui.component.FontList._run_font_list", side_effect=[None, convert_result]) as mock_run,
        patch("NiimPrintX.ui.component.FontList.platform") as mock_platform,
    ):
        mock_shutil.which.side_effect = which_side_effect
        mock_platform.system.return_value = "Linux"
        if hasattr(__import__("sys"), "_MEIPASS"):
            delattr(__import__("sys"), "_MEIPASS")
        result = fonts()

    assert mock_run.call_count == 2
    mock_run.assert_any_call(["/usr/bin/magick", "-list", "font"])
    mock_run.assert_any_call(["/usr/bin/convert", "-list", "font"])
    assert result == convert_result


def test_fonts_both_fail():
    """When both magick and convert fail, fonts() returns an empty dict."""

    def which_side_effect(name):
        return {
            "magick": "/usr/bin/magick",
            "convert": "/usr/bin/convert",
        }.get(name)

    with (
        patch("NiimPrintX.ui.component.FontList.shutil") as mock_shutil,
        patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=None) as mock_run,
        patch("NiimPrintX.ui.component.FontList.platform") as mock_platform,
    ):
        mock_shutil.which.side_effect = which_side_effect
        mock_platform.system.return_value = "Linux"
        if hasattr(__import__("sys"), "_MEIPASS"):
            delattr(__import__("sys"), "_MEIPASS")
        result = fonts()

    assert mock_run.call_count == 2
    assert result == {}


# ---------- disk cache ----------


class TestDiskCache:
    """Tests for _load_disk_cache and _save_disk_cache.

    These override the _no_disk_cache autouse fixture by calling the real
    functions directly (the fixture patches the module-level names, but
    we import the functions directly so we get the real implementations).
    """

    def test_save_and_load_roundtrip(self, tmp_path):
        """Saved data can be loaded back."""
        data = {"TestFamily": {"family_name": "TestFamily", "fonts": {}}}
        magick_bin = tmp_path / "magick"
        magick_bin.write_text("fake")

        with patch("NiimPrintX.ui.component.FontList._get_cache_dir", return_value=str(tmp_path)):
            _save_disk_cache(data)
            loaded = _load_disk_cache(str(magick_bin))

        assert loaded == data

    def test_load_returns_none_when_no_cache_file(self, tmp_path):
        """Missing cache file returns None."""
        with patch("NiimPrintX.ui.component.FontList._get_cache_dir", return_value=str(tmp_path)):
            assert _load_disk_cache("/usr/bin/magick") is None

    def test_load_invalidates_when_binary_newer(self, tmp_path):
        """Cache is invalidated when the binary mtime is newer than cache mtime."""
        import time

        data = {"TestFamily": {"family_name": "TestFamily", "fonts": {}}}

        with patch("NiimPrintX.ui.component.FontList._get_cache_dir", return_value=str(tmp_path)):
            _save_disk_cache(data)

        # Make the binary newer than the cache
        magick_bin = tmp_path / "magick"
        magick_bin.write_text("fake")
        cache_file = tmp_path / "font_cache.json"
        # Set cache mtime to the past
        old_time = time.time() - 100
        os.utime(cache_file, (old_time, old_time))

        with patch("NiimPrintX.ui.component.FontList._get_cache_dir", return_value=str(tmp_path)):
            assert _load_disk_cache(str(magick_bin)) is None

    def test_load_valid_when_binary_older(self, tmp_path):
        """Cache is valid when the binary mtime is older than cache mtime."""
        import time

        data = {"TestFamily": {"family_name": "TestFamily", "fonts": {}}}
        magick_bin = tmp_path / "magick"
        magick_bin.write_text("fake")
        # Set binary mtime to the past
        old_time = time.time() - 100
        os.utime(magick_bin, (old_time, old_time))

        with patch("NiimPrintX.ui.component.FontList._get_cache_dir", return_value=str(tmp_path)):
            _save_disk_cache(data)
            loaded = _load_disk_cache(str(magick_bin))

        assert loaded == data

    def test_load_with_no_magick_path(self, tmp_path):
        """When magick_path is None, cache is still loaded (no mtime check)."""
        data = {"TestFamily": {"family_name": "TestFamily", "fonts": {}}}

        with patch("NiimPrintX.ui.component.FontList._get_cache_dir", return_value=str(tmp_path)):
            _save_disk_cache(data)
            loaded = _load_disk_cache(None)

        assert loaded == data

    def test_save_creates_directory(self, tmp_path):
        """_save_disk_cache creates the cache directory if it doesn't exist."""
        nested = tmp_path / "sub" / "dir"
        data = {"TestFamily": {"family_name": "TestFamily", "fonts": {}}}

        with patch("NiimPrintX.ui.component.FontList._get_cache_dir", return_value=str(nested)):
            _save_disk_cache(data)

        assert (nested / "font_cache.json").is_file()

    def test_load_handles_corrupt_json(self, tmp_path):
        """Corrupt JSON in cache file returns None instead of crashing."""
        cache_file = tmp_path / "font_cache.json"
        cache_file.write_text("{not valid json!!!")

        with patch("NiimPrintX.ui.component.FontList._get_cache_dir", return_value=str(tmp_path)):
            assert _load_disk_cache(None) is None

    def test_fonts_uses_disk_cache(self):
        """fonts() returns disk-cached data without running subprocess."""
        cached_data = {"CachedFamily": {"family_name": "CachedFamily", "fonts": {}}}
        with (
            patch("NiimPrintX.ui.component.FontList._load_disk_cache", return_value=cached_data),
            patch("NiimPrintX.ui.component.FontList._run_font_list") as mock_run,
            patch("NiimPrintX.ui.component.FontList.shutil") as mock_shutil,
        ):
            mock_shutil.which.return_value = "/usr/bin/magick"
            if hasattr(__import__("sys"), "_MEIPASS"):
                delattr(__import__("sys"), "_MEIPASS")
            result = fonts()

        mock_run.assert_not_called()
        assert result == cached_data

    def test_fonts_saves_to_disk_cache_on_miss(self):
        """fonts() saves result to disk cache when subprocess succeeds."""
        grouped = {"NewFamily": {"family_name": "NewFamily", "fonts": {}}}
        with (
            patch("NiimPrintX.ui.component.FontList._load_disk_cache", return_value=None),
            patch("NiimPrintX.ui.component.FontList._save_disk_cache") as mock_save,
            patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=grouped),
            patch("NiimPrintX.ui.component.FontList.shutil") as mock_shutil,
        ):
            mock_shutil.which.return_value = "/usr/bin/magick"
            if hasattr(__import__("sys"), "_MEIPASS"):
                delattr(__import__("sys"), "_MEIPASS")
            result = fonts()

        mock_save.assert_called_once_with(grouped)
        assert result == grouped
