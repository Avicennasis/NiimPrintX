"""Tests for NiimPrintX CLI commands (info_command & print_command).

Focuses on areas not covered by test_cli.py:
  - Info command with varied info enum types (density, battery, etc.)
  - Print command density capping per-model limits
  - Print command rotation with all valid angles
  - Print command offset passthrough
  - B-series routing to V2 protocol (print_imageV2)
  - D-series routing to V1 protocol (print_image)
  - Edge-case argument validation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from PIL import Image

from NiimPrintX.cli.command import niimbot_cli
from NiimPrintX.nimmy.printer import DEFAULT_MAX_DENSITY, V2_MODELS, InfoEnum


@pytest.fixture
def runner():
    return CliRunner()


def _mock_printer(*, connect_ok=True):
    """Build a mock PrinterClient with async methods pre-wired."""
    mock = AsyncMock()
    mock.connect.return_value = connect_ok
    mock.disconnect.return_value = None
    mock.print_image.return_value = None
    mock.print_imageV2.return_value = None
    return mock


def _mock_device(name="TestPrinter"):
    dev = MagicMock()
    dev.name = name
    return dev


# ---------------------------------------------------------------------------
# info_command tests
# ---------------------------------------------------------------------------


class TestInfoCommand:
    """Tests for the 'info' CLI sub-command."""

    def test_info_success_returns_serial_soft_hard(self, runner):
        """Successful info command prints device serial, software, and hardware versions."""
        device = _mock_device()
        printer = _mock_printer()

        async def fake_get_info(info_enum):
            return {
                InfoEnum.DEVICESERIAL: "SN-ABC-9999",
                InfoEnum.SOFTVERSION: "V3.00",
                InfoEnum.HARDVERSION: "HW2.0",
            }[info_enum]

        printer.get_info = AsyncMock(side_effect=fake_get_info)

        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
        ):
            result = runner.invoke(niimbot_cli, ["info", "-m", "d110"])
            assert result.exit_code == 0
            assert "SN-ABC-9999" in result.output
            assert "V3.00" in result.output
            assert "HW2.0" in result.output

    def test_info_queries_correct_enums(self, runner):
        """Info command should query DEVICESERIAL, SOFTVERSION, and HARDVERSION exactly."""
        device = _mock_device()
        printer = _mock_printer()
        printer.get_info = AsyncMock(return_value="dummy")

        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
        ):
            result = runner.invoke(niimbot_cli, ["info", "-m", "d110"])
            assert result.exit_code == 0

        queried = [c.args[0] for c in printer.get_info.call_args_list]
        assert InfoEnum.DEVICESERIAL in queried
        assert InfoEnum.SOFTVERSION in queried
        assert InfoEnum.HARDVERSION in queried

    def test_info_connect_failure_exits_nonzero(self, runner):
        """If printer.connect() returns False, info should exit 1."""
        device = _mock_device()
        printer = _mock_printer(connect_ok=False)

        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
        ):
            result = runner.invoke(niimbot_cli, ["info", "-m", "d110"])
            assert result.exit_code == 1

    def test_info_get_info_exception_exits_nonzero(self, runner):
        """If get_info raises an exception, info should exit 1."""
        device = _mock_device()
        printer = _mock_printer()
        printer.get_info = AsyncMock(side_effect=RuntimeError("BLE timeout"))

        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
        ):
            result = runner.invoke(niimbot_cli, ["info", "-m", "b1"])
            assert result.exit_code == 1

    @pytest.mark.parametrize(
        ("side_effect", "model"),
        [
            (None, "d110"),
            (RuntimeError("fail"), "b21"),
        ],
        ids=["after-success", "after-failure"],
    )
    def test_info_always_disconnects(self, runner, side_effect, model):
        """Printer should be disconnected regardless of success or failure."""
        device = _mock_device()
        printer = _mock_printer()
        if side_effect:
            printer.get_info = AsyncMock(side_effect=side_effect)
        else:
            printer.get_info = AsyncMock(return_value="value")

        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
        ):
            runner.invoke(niimbot_cli, ["info", "-m", model])
            printer.disconnect.assert_awaited_once()

    @pytest.mark.parametrize("model", ["b1", "b18", "b21", "d11", "d110", "d101"])
    def test_info_accepts_all_valid_models(self, runner, model):
        """Every valid model option should be accepted without a Click error."""
        device = _mock_device()
        printer = _mock_printer()
        printer.get_info = AsyncMock(return_value="ok")

        with (
            patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
            patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
        ):
            result = runner.invoke(niimbot_cli, ["info", "-m", model])
            assert result.exit_code == 0

    def test_info_invalid_model_rejected(self, runner):
        """An invalid model name should be rejected by Click."""
        result = runner.invoke(niimbot_cli, ["info", "-m", "z99"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# print_command: density capping
# ---------------------------------------------------------------------------


class TestPrintDensityCap:
    """Tests for per-model density capping logic."""

    @pytest.mark.parametrize(
        ("model", "density", "expected_density", "expect_capped", "img_width", "print_method"),
        [
            ("d110", "5", DEFAULT_MAX_DENSITY, True, 200, "print_image"),
            ("d110", "3", 3, False, 200, "print_image"),
            ("b21", "5", 5, False, 300, "print_imageV2"),
        ],
        ids=["d110-capped-at-max", "d110-within-limit", "b21-allows-density-5"],
    )
    def test_density_capping_per_model(
        self, runner, model, density, expected_density, expect_capped, img_width, print_method
    ):
        """Density is capped to model max and the correct message is shown."""
        device = _mock_device()
        printer = _mock_printer()
        captured_kwargs = {}

        async def capture_print(image, **kwargs):
            captured_kwargs.update(kwargs)

        setattr(printer, print_method, AsyncMock(side_effect=capture_print))

        with runner.isolated_filesystem():
            Image.new("RGB", (img_width, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", model, "-d", density, "-i", "test.png"])
                assert result.exit_code == 0
                if expect_capped:
                    assert "capping" in result.output.lower()
                else:
                    assert "capping" not in result.output.lower()
                assert captured_kwargs["density"] == expected_density

    @pytest.mark.parametrize("density", ["0", "6"], ids=["below-min", "above-max"])
    def test_density_out_of_range_rejected_by_click(self, runner, density):
        """Density outside IntRange(1, 5) should be rejected by Click."""
        with runner.isolated_filesystem():
            Image.new("RGB", (100, 100)).save("test.png")
            result = runner.invoke(niimbot_cli, ["print", "-d", density, "-i", "test.png"])
            assert result.exit_code != 0


# ---------------------------------------------------------------------------
# print_command: B-series V2 protocol routing
# ---------------------------------------------------------------------------


class TestV2ProtocolRouting:
    """Tests that B-series models route through print_imageV2."""

    @pytest.mark.parametrize("model", sorted(V2_MODELS))
    def test_b_series_uses_v2_protocol(self, runner, model):
        """All B-series models should call print_imageV2, not print_image."""
        device = _mock_device()
        printer = _mock_printer()

        with runner.isolated_filesystem():
            Image.new("RGB", (300, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", model, "-d", "1", "-i", "test.png"])
                assert result.exit_code == 0
                printer.print_imageV2.assert_awaited_once()
                printer.print_image.assert_not_awaited()

    def test_b_series_v2_output_message(self, runner):
        """B-series print should show 'V2 protocol' in output."""
        device = _mock_device()
        printer = _mock_printer()

        with runner.isolated_filesystem():
            Image.new("RGB", (300, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "b1", "-d", "1", "-i", "test.png"])
                assert result.exit_code == 0
                assert "v2" in result.output.lower()

    @pytest.mark.parametrize("model", ["d11", "d110", "d101", "d11_h", "d110_m"])
    def test_d_series_uses_v1_protocol(self, runner, model):
        """D-series models should call print_image (V1), not print_imageV2."""
        device = _mock_device()
        printer = _mock_printer()

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", model, "-d", "1", "-i", "test.png"])
                assert result.exit_code == 0
                printer.print_image.assert_awaited_once()
                printer.print_imageV2.assert_not_awaited()

    def test_d_series_v1_output_message(self, runner):
        """D-series print should show 'V1 protocol' in output."""
        device = _mock_device()
        printer = _mock_printer()

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-d", "1", "-i", "test.png"])
                assert result.exit_code == 0
                assert "v1" in result.output.lower()

    def test_b_series_max_width_384(self, runner):
        """B-series models allow up to 384px wide; 385 should fail."""
        device = _mock_device()
        printer = _mock_printer()

        with runner.isolated_filesystem():
            Image.new("RGB", (385, 100)).save("too_wide.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "b1", "-i", "too_wide.png"])
                assert result.exit_code != 0
                assert "exceeds" in result.output.lower() or "width" in result.output.lower()

    def test_b_series_exact_max_width_ok(self, runner):
        """384px wide should be accepted for B-series."""
        device = _mock_device()
        printer = _mock_printer()

        with runner.isolated_filesystem():
            Image.new("RGB", (384, 100)).save("exact.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "b18", "-i", "exact.png"])
                assert result.exit_code == 0


# --- Print rotation ---


class TestPrintRotation:
    """Tests for image rotation options."""

    @pytest.mark.parametrize("angle", ["0", "90", "180", "270"])
    def test_valid_rotation_accepted(self, runner, angle):
        """All valid rotation angles should be accepted."""
        device = _mock_device()
        printer = _mock_printer()

        with runner.isolated_filesystem():
            Image.new("RGB", (100, 50)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-r", angle, "-i", "test.png"])
                assert result.exit_code == 0

    def test_rotation_180_preserves_dimensions(self, runner):
        """180-degree rotation should keep width and height the same."""
        device = _mock_device()
        printer = _mock_printer()
        captured_size = {}

        async def capture(image, **kwargs):
            captured_size["w"] = image.width
            captured_size["h"] = image.height

        printer.print_image = AsyncMock(side_effect=capture)

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 80)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-r", "180", "-i", "test.png"])
                assert result.exit_code == 0
                assert captured_size["w"] == 200
                assert captured_size["h"] == 80

    def test_rotation_270_swaps_dimensions(self, runner):
        """270-degree rotation should swap width and height (like 90)."""
        device = _mock_device()
        printer = _mock_printer()
        captured_size = {}

        async def capture(image, **kwargs):
            captured_size["w"] = image.width
            captured_size["h"] = image.height

        printer.print_image = AsyncMock(side_effect=capture)

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 80)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-r", "270", "-i", "test.png"])
                assert result.exit_code == 0
                assert captured_size["w"] == 80
                assert captured_size["h"] == 200

    def test_rotation_can_make_image_too_wide(self, runner):
        """A tall narrow image rotated 90 degrees may exceed width limit."""
        with runner.isolated_filesystem():
            # 100w x 300h; after 90-degree rotation becomes 300w x 100h (exceeds 240px for d110)
            Image.new("RGB", (100, 300)).save("tall.png")
            result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-r", "90", "-i", "tall.png"])
            assert result.exit_code != 0
            assert "exceeds" in result.output.lower() or "width" in result.output.lower()


# --- Print offsets ---


class TestPrintOffsets:
    """Tests for vertical and horizontal offset passthrough."""

    def test_offsets_passed_to_print_image(self, runner):
        """Vertical and horizontal offsets should be forwarded to print_image."""
        device = _mock_device()
        printer = _mock_printer()
        captured_kwargs = {}

        async def capture(image, **kwargs):
            captured_kwargs.update(kwargs)

        printer.print_image = AsyncMock(side_effect=capture)

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(
                    niimbot_cli, ["print", "-m", "d110", "--vo", "10", "--ho", "5", "-i", "test.png"]
                )
                assert result.exit_code == 0
                assert captured_kwargs["vertical_offset"] == 10
                assert captured_kwargs["horizontal_offset"] == 5

    def test_offsets_passed_to_v2_print(self, runner):
        """Offsets should also be forwarded to print_imageV2 for B-series."""
        device = _mock_device()
        printer = _mock_printer()
        captured_kwargs = {}

        async def capture(image, **kwargs):
            captured_kwargs.update(kwargs)

        printer.print_imageV2 = AsyncMock(side_effect=capture)

        with runner.isolated_filesystem():
            Image.new("RGB", (300, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "b21", "--vo", "7", "--ho", "3", "-i", "test.png"])
                assert result.exit_code == 0
                assert captured_kwargs["vertical_offset"] == 7
                assert captured_kwargs["horizontal_offset"] == 3

    def test_default_offsets_are_zero(self, runner):
        """Without --vo/--ho, offsets default to 0."""
        device = _mock_device()
        printer = _mock_printer()
        captured_kwargs = {}

        async def capture(image, **kwargs):
            captured_kwargs.update(kwargs)

        printer.print_image = AsyncMock(side_effect=capture)

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "test.png"])
                assert result.exit_code == 0
                assert captured_kwargs["vertical_offset"] == 0
                assert captured_kwargs["horizontal_offset"] == 0

    def test_negative_offsets_accepted(self, runner):
        """Negative offsets should be accepted (unbounded int type)."""
        device = _mock_device()
        printer = _mock_printer()
        captured_kwargs = {}

        async def capture(image, **kwargs):
            captured_kwargs.update(kwargs)

        printer.print_image = AsyncMock(side_effect=capture)

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(
                    niimbot_cli, ["print", "-m", "d110", "--vo", "-5", "--ho", "-3", "-i", "test.png"]
                )
                assert result.exit_code == 0
                assert captured_kwargs["vertical_offset"] == -5
                assert captured_kwargs["horizontal_offset"] == -3


# --- Print quantity ---


class TestPrintQuantity:
    """Tests for print quantity option."""

    def test_quantity_passed_to_printer(self, runner):
        """Quantity flag should be forwarded to the print call."""
        device = _mock_device()
        printer = _mock_printer()
        captured_kwargs = {}

        async def capture(image, **kwargs):
            captured_kwargs.update(kwargs)

        printer.print_image = AsyncMock(side_effect=capture)

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-n", "5", "-i", "test.png"])
                assert result.exit_code == 0
                assert captured_kwargs["quantity"] == 5

    @pytest.mark.parametrize("quantity", ["0", "65536"], ids=["below-min", "above-max"])
    def test_quantity_out_of_range_rejected(self, runner, quantity):
        """Quantity outside IntRange(1, 65535) should be rejected by Click."""
        with runner.isolated_filesystem():
            Image.new("RGB", (100, 100)).save("test.png")
            result = runner.invoke(niimbot_cli, ["print", "-n", quantity, "-i", "test.png"])
            assert result.exit_code != 0


# ---------------------------------------------------------------------------
# print_command: error handling
# ---------------------------------------------------------------------------


class TestPrintErrorHandling:
    """Tests for error paths in the print command."""

    def test_print_exception_during_printing_exits_nonzero(self, runner):
        """If print_image raises, the command should exit 1."""
        device = _mock_device()
        printer = _mock_printer()
        printer.print_image = AsyncMock(side_effect=RuntimeError("BLE write failed"))

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "test.png"])
                assert result.exit_code == 1

    @pytest.mark.parametrize(
        "side_effect",
        [None, RuntimeError("fail")],
        ids=["after-success", "after-failure"],
    )
    def test_print_always_disconnects(self, runner, side_effect):
        """Printer should be disconnected regardless of success or failure."""
        device = _mock_device()
        printer = _mock_printer()
        if side_effect:
            printer.print_image = AsyncMock(side_effect=side_effect)

        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with (
                patch("NiimPrintX.cli.command.find_device", new_callable=AsyncMock, return_value=device),
                patch("NiimPrintX.cli.command.PrinterClient", return_value=printer),
            ):
                runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "test.png"])
                printer.disconnect.assert_awaited_once()

    def test_find_device_failure_exits_nonzero(self, runner):
        """If find_device raises (no BLE adapter), command should exit 1."""
        with runner.isolated_filesystem():
            Image.new("RGB", (200, 100)).save("test.png")
            with patch(
                "NiimPrintX.cli.command.find_device",
                new_callable=AsyncMock,
                side_effect=RuntimeError("No BLE adapter"),
            ):
                result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "test.png"])
                assert result.exit_code == 1

    def test_corrupt_image_exits_nonzero(self, runner):
        """A corrupt image file should cause a non-zero exit."""
        with runner.isolated_filesystem():
            with open("corrupt.png", "wb") as f:
                f.write(b"not a real image")
            result = runner.invoke(niimbot_cli, ["print", "-m", "d110", "-i", "corrupt.png"])
            assert result.exit_code != 0


# ---------------------------------------------------------------------------
# print_command: verbose flag
# ---------------------------------------------------------------------------


class TestVerboseFlag:
    """Tests for the -v/--verbose global option."""

    def test_verbose_flag_accepted(self, runner):
        """The -v flag should be accepted without error."""
        result = runner.invoke(niimbot_cli, ["-v", "info", "--help"])
        assert result.exit_code == 0

    def test_double_verbose_accepted(self, runner):
        """Multiple -v flags should be accepted."""
        result = runner.invoke(niimbot_cli, ["-vv", "info", "--help"])
        assert result.exit_code == 0
