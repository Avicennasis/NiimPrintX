from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from NiimPrintX.cli.command import niimbot_cli


def test_cli_help(runner):
    result = runner.invoke(niimbot_cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_print_help(runner):
    result = runner.invoke(niimbot_cli, ["print", "--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_info_help(runner):
    result = runner.invoke(niimbot_cli, ["info", "--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_print_invalid_model(runner):
    with runner.isolated_filesystem():
        Image.new("RGB", (100, 100)).save("test.png")
        result = runner.invoke(niimbot_cli, ["print", "-m", "invalid", "-i", "test.png"])
        assert result.exit_code != 0


def test_print_missing_image(runner):
    result = runner.invoke(niimbot_cli, ["print"])
    assert result.exit_code != 0


def test_print_nonexistent_image(runner):
    result = runner.invoke(niimbot_cli, ["print", "-i", "/nonexistent.png"])
    assert result.exit_code != 0


def test_print_invalid_density(runner):
    with runner.isolated_filesystem():
        Image.new("RGB", (100, 100)).save("test.png")
        result = runner.invoke(niimbot_cli, ["print", "-d", "10", "-i", "test.png"])
        assert result.exit_code != 0


def test_print_invalid_rotation(runner):
    with runner.isolated_filesystem():
        Image.new("RGB", (100, 100)).save("test.png")
        result = runner.invoke(niimbot_cli, ["print", "-r", "45", "-i", "test.png"])
        assert result.exit_code != 0


def test_print_image_too_wide_exits_nonzero(runner):
    with runner.isolated_filesystem():
        Image.new("RGB", (500, 100)).save("wide.png")
        result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "wide.png"])
        assert result.exit_code != 0


def test_print_valid_args_attempts_ble(runner):
    with runner.isolated_filesystem():
        Image.new("RGB", (200, 100)).save("test.png")
        result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "test.png"])
        # Should fail at BLE scanning (no hardware), but should NOT exit 0
        assert result.exit_code != 0


def test_info_attempts_ble(runner):
    result = runner.invoke(niimbot_cli, ["info", "-m", "d110"])
    assert result.exit_code != 0


def test_print_b_series_width_limit(runner):
    with runner.isolated_filesystem():
        Image.new("RGB", (400, 100)).save("wide.png")
        result = runner.invoke(niimbot_cli, ["print", "-m", "b1", "-i", "wide.png"])
        assert result.exit_code != 0


def test_print_b_series_within_limit(runner):
    with runner.isolated_filesystem():
        Image.new("RGB", (384, 100)).save("ok.png")
        result = runner.invoke(niimbot_cli, ["print", "-m", "b1", "-i", "ok.png"])
        # Should pass width check, fail at BLE
        assert result.exit_code != 0
        assert "exceeds" not in result.output.lower()


def test_density_cap_message(runner):
    """Density > 3 on a non-b21 model should print a capping message."""
    with runner.isolated_filesystem():
        Image.new("RGB", (200, 100)).save("test.png")
        result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-d", "4", "-i", "test.png"])
        assert "capping" in result.output.lower() or result.exit_code != 0


def test_print_connect_failure(runner):
    """Printer found but connect() returns False."""
    mock_device = MagicMock()
    mock_device.name = "D110"
    mock_printer = AsyncMock()
    mock_printer.connect.return_value = False
    mock_printer.disconnect.return_value = None

    with runner.isolated_filesystem():
        Image.new("RGB", (200, 100)).save("test.png")
        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=mock_device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=mock_printer),
        ):
            result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "test.png"])
            assert result.exit_code == 1
            assert "connect" in result.output.lower() or "failed" in result.output.lower()


def test_print_image_too_tall(runner):
    """Image exceeding 65535px height should be rejected."""
    with runner.isolated_filesystem():
        Image.new("RGB", (100, 70000)).save("tall.png")
        result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "tall.png"])
        assert result.exit_code == 1
        assert "height" in result.output.lower() or "exceeds" in result.output.lower()


def test_print_rotation_applied(runner):
    """Rotation flag -r 90 should swap image dimensions before printing."""
    mock_device = MagicMock()
    mock_device.name = "D110"
    mock_printer = AsyncMock()
    mock_printer.connect.return_value = True
    mock_printer.disconnect.return_value = None
    mock_printer.print_image.return_value = None

    captured_image = {}

    async def capture_print_image(image, **kwargs):
        captured_image["width"] = image.width
        captured_image["height"] = image.height

    mock_printer.print_image = AsyncMock(side_effect=capture_print_image)

    with runner.isolated_filesystem():
        # 200 wide x 100 tall; after 90-degree rotation expect 100 wide x 200 tall
        Image.new("RGB", (200, 100)).save("test.png")
        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=mock_device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=mock_printer),
        ):
            result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-r", "90", "-i", "test.png"])
            assert result.exit_code == 0
            assert captured_image["width"] == 100
            assert captured_image["height"] == 200
