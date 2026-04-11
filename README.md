<h1 align="center">NiimPrintX</h1>
<p align="center">
<a href="https://github.com/avicennasis/NiimPrintX/releases"><img src="https://img.shields.io/github/release/avicennasis/NiimPrintX.svg?style=for-the-badge" alt="Latest Release"></a>
<a href="https://github.com/avicennasis/NiimPrintX/actions/workflows/tag.yaml"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/avicennasis/NiimPrintX/tag.yaml?style=for-the-badge"></a>
<a href="https://github.com/avicennasis/NiimPrintX/actions/workflows/ci.yaml"><img alt="CI Status" src="https://img.shields.io/github/actions/workflow/status/avicennasis/NiimPrintX/ci.yaml?style=for-the-badge&label=CI"></a>
<a href="https://github.com/avicennasis/NiimPrintX/commits/main/"><img alt="GitHub commits since latest release" src="https://img.shields.io/github/commits-since/avicennasis/NiimPrintX/latest?style=for-the-badge"></a>
</p>


![NiimPrintX](docs/assets/NiimPrintX.gif)

NiimPrintX is a Python library designed to seamlessly interface with NiimBot label printers via Bluetooth.
It provides both a Command-Line Interface (CLI) and a Graphical User Interface (GUI) for users to design and print labels efficiently.

## Fork Notice

This is a community-maintained fork of the original [labbots/NiimPrintX](https://github.com/labbots/NiimPrintX). The upstream project was last updated in May 2024 and is no longer actively maintained. We picked up where it left off to keep NiimPrintX alive and moving forward.

Since forking, we have:

- Merged outstanding upstream pull requests from the community
- Conducted 6 rounds of deep code review, hardening the codebase throughout
- Added a comprehensive test suite (100+ pytest tests) and CI/CD pipeline
- Replaced the pickle-based `.niim` file format with a secure JSON-based format
- Introduced user-configurable custom label sizes, per-device rotation, and BLE resilience improvements

**Current version: v0.4.0**

A huge thank you to [labbots](https://github.com/labbots) for creating NiimPrintX and building the foundation this project stands on.

## Key Features

* **Cross-Platform Compatibility:** Works on Windows, macOS, and Linux.
* **Bluetooth Connectivity:** Effortlessly connect to NiimBot label printers via BLE, with auto-reconnect and lock-based concurrency for resilient connections.
* **Comprehensive Model Support:** Compatible with multiple NiimBot printer models (D11, D11_H, D101, D110, D110_M, B1, B18, B21).
* **Dual Interface Options:** Provides both a Command-Line Interface (CLI) and a Graphical User Interface (GUI).
* **Custom Label Design:** The GUI enables users to design labels tailored to specific devices and label sizes.
* **Advanced Print Settings:** Customize print density, quantity, and image rotation for precise label printing.
* **JSON-Based .niim Format:** Label designs are saved in a secure JSON format, replacing the original pickle-based approach to eliminate deserialization risks.
* **User-Configurable Label Sizes:** Define custom label dimensions and device profiles via a simple TOML config file.
* **Per-Device Rotation Settings:** Configure default rotation on a per-device basis through the config file.
* **Decompression Bomb Protection:** Image loading includes safeguards against decompression bomb attacks.
* **Comprehensive Test Suite:** 100+ pytest tests covering packets, Bluetooth communication, image encoding, configuration, CLI, and print integration.
* **CI/CD Pipeline:** Automated ruff linting, pytest runs on every push, and PyInstaller builds for Linux, macOS, and Windows on tagged releases.

## Requirements

To run NiimPrintX, you need to have the following installed:

* **Python 3.12 or later** -- `bleak`'s winrt backend requires Python 3.12+, and the TOML config parser (`tomllib`) requires Python 3.11+
* ImageMagick library
* Poetry for dependency management

### Supported Printer Models

D11, D11_H, D101, D110, D110_M, B1, B18, B21


## Installation

Ensure that ImageMagick is installed and properly configured on your system. You can download it from [here](https://imagemagick.org/script/download.php).

Clone the repository:

```shell
git clone https://github.com/avicennasis/NiimPrintX.git
cd NiimPrintX
```
Install the necessary dependencies using Poetry (Poetry manages its own virtual environment automatically):

```shell
poetry install
```

To include the optional GUI dependencies (Tkinter theme):

```shell
poetry install --extras gui
```

### Note:
macOS specific setup for local development:

```shell
brew install libffi
brew install glib gobject-introspection cairo pkg-config

export PKG_CONFIG_PATH="/usr/local/opt/libffi/lib/pkgconfig"
export LDFLAGS="-L/usr/local/opt/libffi/lib"
export CFLAGS="-I/usr/local/opt/libffi/include"
```


## User Configuration

NiimPrintX supports an optional TOML configuration file for customizing device settings and adding custom label sizes. The config file is located at:

* **Linux/macOS:** `~/.config/NiimPrintX/config.toml`
* **Windows:** `%LOCALAPPDATA%\NiimPrintX\config.toml`

(The exact path is determined by [platformdirs](https://github.com/platformdirs/platformdirs).)

### Example config.toml

```toml
# Add custom label sizes to an existing built-in device
[devices.d110.size]
"30mm x 15mm" = [30, 15]
"custom" = [60, 20]

# Define an entirely new device (must include at least one valid size)
[devices.myprinter]
density = 3
print_dpi = 203
rotation = -90

[devices.myprinter.size]
"50mm x 25mm" = [50, 25]
```

### How merging works

* **Existing devices:** User-defined sizes are merged into the built-in size list. You can add new label sizes without losing the defaults.
* **New devices:** You can define entirely new device entries. A new device must include at least one valid size (a `[width, height]` pair). Optional settings (`density`, `print_dpi`, `rotation`) default to `3`, `203`, and `-90` respectively if omitted.


## Usage

NiimPrintX provides both CLI and GUI applications to use the printer.

### Command-Line Interface (CLI)

The CLI allows you to print images and get information about the printer models.

#### General CLI Usage
```shell
Usage: python -m NiimPrintX.cli [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --verbose  Enable verbose logging
  -h, --help     Show this message and exit.

Commands:
  info
  print
```
#### Print Command
```shell
Usage: python -m NiimPrintX.cli print [OPTIONS]

Options:
  -m, --model [b1|b18|b21|d11|d11_h|d110|d101|d110_m]
                                  Niimbot printer model  [default: d110]
  -d, --density INTEGER RANGE     Print density  [default: 3; 1<=x<=5]
  -n, --quantity INTEGER RANGE    Print quantity  [default: 1; 1<=x<=65535]
  -r, --rotate [0|90|180|270]     Image rotation (clockwise)  [default: 0]
  --vo INTEGER                    Vertical offset in pixels  [default: 0]
  --ho INTEGER                    Horizontal offset in pixels  [default: 0]
  -i, --image PATH                Image path  [required]
  -h, --help                      Show this message and exit.
```
**Example:**

```shell
python -m NiimPrintX.cli print -m d110 -d 3 -n 1 -r 90 -i path/to/image.png
```

#### Info Command

```shell
Usage: python -m NiimPrintX.cli info [OPTIONS]

Options:
  -m, --model [b1|b18|b21|d11|d11_h|d110|d101|d110_m]
                                  Niimbot printer model  [default: d110]
  -h, --help                      Show this message and exit.
```

**Example:**

```shell
python -m NiimPrintX.cli info -m d110
```

### Graphical User Interface (GUI)

The GUI application allows users to design labels based on the label device and label size. Simply run the GUI application:

```shell
python -m NiimPrintX.ui
```

## Development

Contributions are welcome! Please fork the repository and submit a pull request with your improvements.

### Running Tests

```shell
poetry run pytest -v
```

### Running Lint

```shell
poetry run ruff check NiimPrintX/
```

### Building

Automated builds for Linux, macOS (Intel and Apple Silicon), and Windows are handled by [GitHub Actions workflows](.github/workflows/). Tagged releases trigger PyInstaller builds and publish artifacts to [GitHub Releases](https://github.com/avicennasis/NiimPrintX/releases).

## Credits

* Special thanks to [labbots](https://github.com/labbots) for creating the original NiimPrintX project. The vision, architecture, and initial implementation are all theirs -- this fork simply carries the torch forward.
* Icons made by [Dave Gandy](https://www.flaticon.com/authors/dave-gandy) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [Pixel perfect](https://www.flaticon.com/authors/pixel-perfect) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [Freepik](https://www.freepik.com) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [rddrt](https://www.flaticon.com/authors/rddrt) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [Icongeek26](https://www.flaticon.com/authors/icongeek26) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [SyafriStudio](https://www.flaticon.com/authors/syafristudio) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [Wahyu Adam](https://www.flaticon.com/authors/wahyu-adam) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [meaicon](https://www.flaticon.com/authors/meaicon) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [IconKanan](https://www.flaticon.com/authors/iconkanan) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [kornkun](https://www.flaticon.com/authors/kornkun) from [www.flaticon.com](https://www.flaticon.com/)
* Icons made by [Rifaldi Ridha Aisy](https://www.flaticon.com/authors/rifaldi-ridha-aisy) from [www.flaticon.com](https://www.flaticon.com/)

## License

NiimPrintX is licensed under the [GNU General Public License v3.0](LICENSE). See the LICENSE file for details.
