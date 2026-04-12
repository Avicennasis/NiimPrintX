from unittest.mock import patch

from NiimPrintX.ui.component.FontList import fonts, group_fonts_by_family, parse_font_details

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


def test_fonts_system_magick_success():
    """System magick succeeds on first try -- no convert fallback attempted."""
    with (
        patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=FAKE_GROUPED) as mock_run,
    ):
        # Ensure no _MEIPASS so we hit the system-magick branch
        if hasattr(__import__("sys"), "_MEIPASS"):
            delattr(__import__("sys"), "_MEIPASS")
        result = fonts()

    mock_run.assert_called_once_with(["magick", "-list", "font"])
    assert result == FAKE_GROUPED


def test_fonts_system_magick_fails_convert_fallback():
    """When system magick fails, fonts() falls back to 'convert' and returns its result."""
    convert_result = {"ConvertFamily": {"family_name": "ConvertFamily", "fonts": {}}}

    with (
        patch("NiimPrintX.ui.component.FontList._run_font_list", side_effect=[None, convert_result]) as mock_run,
        patch("NiimPrintX.ui.component.FontList.platform") as mock_platform,
    ):
        mock_platform.system.return_value = "Linux"
        if hasattr(__import__("sys"), "_MEIPASS"):
            delattr(__import__("sys"), "_MEIPASS")
        result = fonts()

    assert mock_run.call_count == 2
    mock_run.assert_any_call(["magick", "-list", "font"])
    mock_run.assert_any_call(["convert", "-list", "font"])
    assert result == convert_result


def test_fonts_both_fail():
    """When both magick and convert fail, fonts() returns an empty dict."""
    with (
        patch("NiimPrintX.ui.component.FontList._run_font_list", return_value=None) as mock_run,
        patch("NiimPrintX.ui.component.FontList.platform") as mock_platform,
    ):
        mock_platform.system.return_value = "Linux"
        if hasattr(__import__("sys"), "_MEIPASS"):
            delattr(__import__("sys"), "_MEIPASS")
        result = fonts()

    assert mock_run.call_count == 2
    assert result == {}
