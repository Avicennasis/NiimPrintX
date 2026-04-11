from NiimPrintX.ui.component.FontList import group_fonts_by_family, parse_font_details

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
    fonts = [
        _make_font("Zebra", family="Zebra"),
        _make_font("Alpha", family="Alpha"),
        _make_font("Middle", family="Middle"),
    ]
    grouped = group_fonts_by_family(fonts)
    keys = list(grouped.keys())
    assert keys == sorted(keys)
    assert keys == ["Alpha", "Middle", "Zebra"]
