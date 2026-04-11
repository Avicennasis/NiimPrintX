# Upstream Open Issues (labbots/NiimPrintX)

> Captured 2026-04-11 from https://github.com/labbots/NiimPrintX/issues
> 31 open issues total

---

## Connection / Pairing Issues

| # | Title | Author | Date | Printer | Platform |
|---|-------|--------|------|---------|----------|
| [#42](https://github.com/labbots/NiimPrintX/issues/42) | Can't Connect to NiimBot B1 | @balucio | 2026-01-12 | B1 | Linux Mint 22.3 |
| [#40](https://github.com/labbots/NiimPrintX/issues/40) | Request B1 support in GUI | @newtrashcan | 2025-11-19 | B1 | macOS Sequoia |
| [#35](https://github.com/labbots/NiimPrintX/issues/35) | How to add as printer on Xubuntu 22.04 | @mrinvader | 2025-04-16 | B1/D110 | Xubuntu 22.04 |
| [#25](https://github.com/labbots/NiimPrintX/issues/25) | Can't pair with D101 under Windows | @NeoMod | 2025-01-08 | D101 | Windows 11 |
| [#22](https://github.com/labbots/NiimPrintX/issues/22) | Not connecting to D110 | @DaveBrindley | 2024-11-12 | D110 | — |
| [#13](https://github.com/labbots/NiimPrintX/issues/13) | Cant connect D110 | @akeilox | 2024-10-07 | D110 | Windows 11 |
| [#11](https://github.com/labbots/NiimPrintX/issues/11) | Cant select printer | @IsirElektronika | 2024-09-11 | B18 | — |

## Printing Bugs

| # | Title | Author | Date | Printer | Details |
|---|-------|--------|------|---------|---------|
| [#32](https://github.com/labbots/NiimPrintX/issues/32) | Cannot print on D110_M | @jonsnow1357 | 2025-02-11 | D110_M | Crash at line 296 in printer.py — return packet has 8 bytes instead of 4 |
| [#24](https://github.com/labbots/NiimPrintX/issues/24) | Wrong printing orientation (portrait instead of landscape) | @krp-ulag | 2025-01-06 | D11 | Flatpak on Linux — printed text is 90° rotated |
| [#20](https://github.com/labbots/NiimPrintX/issues/20) | B1 printing blank label through CLI | @Tiers93 | 2024-10-26 | B1 | CLI accepts commands but prints blank labels |
| [#8](https://github.com/labbots/NiimPrintX/issues/8) | D11_H Bug when printing — unpack requires a buffer of 4 bytes | @Adrian-Grimm | 2024-08-14 | D11_H (300dpi) | `unpack requires a buffer of 4 bytes` — prints empty label |
| [#3](https://github.com/labbots/NiimPrintX/issues/3) | 'NoneType' object has no attribute 'data' | @omartazi | 2024-06-26 | D110 | Error after 20s when pressing Print |
| [#1](https://github.com/labbots/NiimPrintX/issues/1) | Error message displayed after successful print | @icarosadero | 2024-06-19 | D110 | `unpack requires a buffer of 4 bytes` post-print error |

## App Crashes / Startup Errors

| # | Title | Author | Date | Details |
|---|-------|--------|------|---------|
| [#31](https://github.com/labbots/NiimPrintX/issues/31) | Python 3.13.2 not working with Poetry install | @sjanssen15 | 2025-02-10 | pyproject.toml restricts to `>=3.12,<3.13` |
| [#26](https://github.com/labbots/NiimPrintX/issues/26) | Fails to run in Korean Windows | @kwon0408 | 2025-01-20 | `UnicodeDecodeError: 'cp949' codec can't decode byte` in FontList.py |
| [#18](https://github.com/labbots/NiimPrintX/issues/18) | CLI throws 'Event loop is closed' | @quistuipater | 2024-10-24 | macOS Big Sur + B21 — CoreBluetooth event loop crash |

## Feature Requests

| # | Title | Author | Date | Description |
|---|-------|--------|------|-------------|
| [#38](https://github.com/labbots/NiimPrintX/issues/38) | Rotate text/image | @verglor | 2025-06-20 | Rotate text/image for vertical labels |
| [#21](https://github.com/labbots/NiimPrintX/issues/21) | Multi-line labels | @hadess | 2024-11-11 | Multiple text labels or multi-line text |
| [#17](https://github.com/labbots/NiimPrintX/issues/17) | Can't open saved files from command-line | @hadess | 2024-10-11 | `python -m NiimPrintX.ui foo.niim` should open file in GUI |
| [#15](https://github.com/labbots/NiimPrintX/issues/15) | Flatpak package | @hadess | 2024-10-10 | Flathub packaging — PR at flathub/flathub#5701 |
| [#14](https://github.com/labbots/NiimPrintX/issues/14) | Better look on Linux? | @hadess | 2024-10-10 | ttkthemes mixing styles — wants modern Linux look |
| [#7](https://github.com/labbots/NiimPrintX/issues/7) | Config file for label sizes | @Cvaniak | 2024-07-24 | JSON/YAML/TOML config for custom label sizes |
| [#10](https://github.com/labbots/NiimPrintX/issues/10) | Phomemo printer support? | @X3msnake | 2024-08-27 | Phomemo Q31 uses similar hardware |

## Device Support Requests

| # | Title | Author | Date | Printer |
|---|-------|--------|------|---------|
| [#37](https://github.com/labbots/NiimPrintX/issues/37) | Support for Niimbot B21S | @Pr33my | 2025-06-06 | B21S |
| [#34](https://github.com/labbots/NiimPrintX/issues/34) | K3 Printer | @iamLukyy | 2025-02-27 | K3 |
| [#23](https://github.com/labbots/NiimPrintX/issues/23) | Support for B3S? | @uhlhosting | 2024-12-11 | B3S |
| [#19](https://github.com/labbots/NiimPrintX/issues/19) | B21 not listed in the GUI version | @quistuipater | 2024-10-24 | B21 |
| [#5](https://github.com/labbots/NiimPrintX/issues/5) | B1 label size missing | @parisneto | 2024-07-09 | B1 |
| [#4](https://github.com/labbots/NiimPrintX/issues/4) | Different DPI for 2024 models | @raenye | 2024-07-07 | D11-H / D110-M (300dpi) |
| [#2](https://github.com/labbots/NiimPrintX/issues/2) | Add support for D101 | @cropse | 2024-06-21 | D101 |

## Miscellaneous / Non-English

| # | Title | Author | Date | Notes |
|---|-------|--------|------|-------|
| [#44](https://github.com/labbots/NiimPrintX/issues/44) | Update the project | @roboso | 2026-02-17 | Asking if project is still active |
| [#27](https://github.com/labbots/NiimPrintX/issues/27) | Imprimer sur B1 via Excel | @Mod77420 | 2025-01-24 | French — wants to print from Excel VBA to B1 |

---

## Summary

| Category | Count |
|----------|-------|
| Connection/Pairing | 7 |
| Printing Bugs | 6 |
| App Crashes/Startup | 3 |
| Feature Requests | 7 |
| Device Support | 7 |
| Miscellaneous | 1 |
| **Total** | **31** |

### Key Themes

1. **The `unpack requires a buffer of 4 bytes` error** is widespread (#1, #8, #32) — likely a protocol parsing issue with newer firmware returning 8-byte packets
2. **B1 printer support** is heavily requested but broken (#5, #20, #40, #42) — PR #6 attempted a fix
3. **D110 connection issues** are the most common complaint (#3, #13, #22, #35)
4. **300 DPI models** (D11-H, D110-M) are not properly supported (#4, #8, #32)
5. **Python version constraint** needs widening to support 3.13+ (#31)
6. **Non-ASCII font names** crash the GUI on non-English Windows (#26) — PR #28 has a fix
