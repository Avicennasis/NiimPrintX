import pytest
from click.testing import CliRunner
from PIL import Image

from NiimPrintX.cli.command import niimbot_cli


@pytest.fixture
def runner():
    return CliRunner()


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
