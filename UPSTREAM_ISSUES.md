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

---

# D110_M (2025 Hardware) - Comprehensive Debug Log

**Status**: UNRESOLVED - Commands succeed but no visible output on labels  
**Date**: 2026-04-14  
**Related Issue**: [#32](https://github.com/labbots/NiimPrintX/issues/32)

## Hardware Details

| Property | Value |
|----------|-------|
| Model | D110_M (device ID 2320) |
| Software Version | 10.52 |
| Hardware Version | 10.25 |
| Serial | HC23072563 |
| Printhead Width | 96 pixels (per NiimBlueLib) |
| Resolution | 203 DPI |
| Label Type | RFID-enabled (type 1) |
| RFID Barcode | 01222281 |
| RFID Serial | PZ1HA23529008505 |

## Symptoms

- BLE connection succeeds
- All protocol commands return success responses `[1]`
- Print status shows job "completing" (page 1/1, progress 100%)
- Printer beeps (acknowledges job receipt)
- Label advances
- **NO visible content prints** - labels are completely blank

---

## Complete Debug History

### 1. Protocol Versions Tested

#### V1 Protocol (Standard D110)
```
SET_LABEL_DENSITY(3) → [1] (success)
SET_LABEL_TYPE(1) → [1] (success)
START_PRINT(1 byte: 0x01) → [1] (success)
START_PAGE_PRINT → [1] (success)
SET_DIMENSION(4 bytes: height_hi, height_lo, width_hi, width_lo) → [1, 0] (success)
SET_QUANTITY → [1] (success)
PrintBitmapRow (0x85) × N packets
END_PAGE_PRINT → [1] (success)
GET_PRINT_STATUS → [0, 1, 100, 100, 34, 195, 0, 1] (8 bytes, page complete)
END_PRINT → [1] (success)
```
**Result**: Commands succeed, blank labels

#### V4 Protocol (D110_M 2025 per NiimBlueLib)
```
SET_LABEL_DENSITY(3) → [1] (success)
SET_LABEL_TYPE(1) → [1] (success)
START_PRINT(9 bytes): totalPages(2) + zeros(4) + pageColor(1) + speed(1) + flag(1)
  → Example: [0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x01]
SET_DIMENSION(13 bytes): rows(2) + cols(2) + copies(2) + cutHeight(2) + cutType(1) + zero(1) + sendAll(1) + partHeight(2)
  → sendAll=0x01 at byte 10
GET_PRINT_STATUS (fire-and-forget, before image data)
PrintBitmapRow (0x85) × N packets
END_PAGE_PRINT → [1] (success)
GET_PRINT_STATUS → 8-byte response, page count in bytes 6-7
END_PRINT → [1] (success)
```
**Result**: Commands succeed, printer beeps, blank labels

---

### 2. Image Encoding Variations Tested

#### 2.1 Standard Encoding (With Inversion)
```python
gray = image.convert("L")           # RGB → grayscale
inverted = ImageOps.invert(gray)    # black(0)→255, white(255)→0
img = inverted.convert("1")         # threshold: >127=1(white), ≤127=0(black)
line_data = img.tobytes()           # MSB-first packing
```
- Black pixels → grayscale 0 → invert → 255 → 1-bit → 1 → packed as 0xFF
- White pixels → grayscale 255 → invert → 0 → 1-bit → 0 → packed as 0x00
- **Result**: Blank

#### 2.2 No Inversion (Opposite Polarity Test)
```python
gray = image.convert("L")
inverted = gray  # Skip ImageOps.invert()
img = inverted.convert("1")
```
- Black pixels → grayscale 0 → 1-bit → 0 → packed as 0x00
- Debug log: `"Sent 100 image packets, 0 with non-zero content"`
- **Result**: Blank

#### 2.3 Bit Reversal (LSB-first Test)
```python
_BIT_REVERSE = bytes(int(f'{i:08b}'[::-1], 2) for i in range(256))
line_data = bytes(_BIT_REVERSE[b] for b in raw_line)
```
- Tested in case printer expects LSB-first bit order within bytes
- Note: 0xFF reversed = 0xFF, so no effect on solid rows
- **Result**: Blank

#### 2.4 Black Pixel Counts Variations
```python
# Calculated counts (split into 3 chunks)
chunk_size = byte_count // 3
count1 = sum(bin(b).count('1') for b in chunk1)  # e.g., 80 for 10 bytes
count2 = sum(bin(b).count('1') for b in chunk2)
count3 = sum(bin(b).count('1') for b in chunk3)
counts = (count1, count2, count3)  # e.g., (80, 80, 80) for 240px row

# Zero counts (per niimprint: "can always send zeros")
counts = (0, 0, 0)
```
- Both variations tested
- **Result**: Both blank

---

### 3. Packet Format Details

#### PrintBitmapRow (0x85) Structure
```
55 55 85 [len] [row_hi] [row_lo] [count1] [count2] [count3] [repeat] [bitmap...] [checksum] AA AA
│  │  │   │    └───────────────────────────────────────────────────────────────┘   │        │  │
│  │  │   │                              data payload                              │        │  │
│  │  │   └─ length of data payload                                                │        │  │
│  │  └─ command type (PrintBitmapRow)                                             │        │  │
│  └─ header byte 2                                                                │        │  │
└─ header byte 1                                                                   │        │  │
                                                          XOR of type+len+data ────┘        │  │
                                                                             footer bytes ──┴──┘
```

#### Verified Packet Example (240px width, Row 0)
```
55 55 85 24 00 00 00 00 00 01 ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff [checksum] aa aa
      │  │  └row─┘└counts─┘│  └──────────────────────────── 30 bytes bitmap data ────────────────────────────┘
      │  └─ len=36 (0x24) = 6 byte header + 30 bytes bitmap
      └─ type=0x85 (PrintBitmapRow)
```

#### Verified Packet Example (96px width, Row 0)
```
55 55 85 12 00 00 00 00 00 01 ff ff ff ff ff ff ff ff ff ff ff ff [checksum] aa aa
      │  │  └row─┘└counts─┘│  └──────── 12 bytes bitmap data ────────────────┘
      │  └─ len=18 (0x12) = 6 byte header + 12 bytes bitmap
      └─ type=0x85 (PrintBitmapRow)
```

---

### 4. BLE Write Modes Tested

| Mode | Method | Timing | Result |
|------|--------|--------|--------|
| Fire-and-forget | `response=False` | ~10ms per 10 packets with 0.01s delays | Blank |
| Write-with-response | `response=True` | ~180ms per packet | Blank |

---

### 5. Image Dimensions Tested

| Width | Height | Bytes/Row | SET_DIMENSION | Result |
|-------|--------|-----------|---------------|--------|
| 240px | 100px | 30 | [0, 100, 0, 240] | Blank |
| 240px | 20px | 30 | [0, 20, 0, 240] | Blank |
| 96px | 50px | 12 | [0, 50, 0, 96] | Blank (beeped) |
| 96px | 20px | 12 | [0, 20, 0, 96] | Blank (beeped) |

Note: NiimBlueLib specifies D110_M has 96px printhead width.

---

### 6. Label Types Tested

| Type | Description | Result |
|------|-------------|--------|
| 1 | WithGaps/Standard | Success response, blank output |
| 2 | Continuous | Timeout (page 0/1 stuck) |
| 3 | Transparent | Not tested |

RFID data showed `type: 1`, matching SET_LABEL_TYPE(1).

---

### 7. Rotation Tested

| Angle | CLI Flag | Original Size | Rotated Size | Result |
|-------|----------|---------------|--------------|--------|
| 0° | (default) | 96x50 | 96x50 | Blank |
| 90° | `-r 90` | 96x50 | 50x96 | Timeout |
| 180° | `-r 180` | 96x50 | 96x50 | Blank |
| 270° | `-r 270` | 96x50 | 50x96 | Blank |

---

### 8. Test Images Used

| Filename | Size | Description | Encoding Result |
|----------|------|-------------|-----------------|
| test_solid_black.png | 240x100 | All black pixels | All 0xFF bytes (with invert) |
| test_solid_white.png | 240x100 | All white pixels | All 0x00 bytes (with invert) |
| test_alternating.png | 240x20 | Alternating black/white rows | 0xFF/0x00 alternating |
| test_single_line.png | 240x10 | Single black line | Mix of 0xFF and 0x00 |
| test_96px.png | 96x50 | Alternating rows, printhead-width | 0xFF/0x00 alternating |
| test_bar.png | 96x20 | Solid black bar | All 0xFF bytes |
| test_checker.png | 96x20 | Checkerboard pattern | 0xAA/0x55 alternating |

---

### 9. RFID Data Retrieved

```python
await printer.get_rfid()
# Returns:
{
    'uuid': '881d7915b2181080',
    'barcode': '01222281',
    'serial': 'PZ1HA23529008505',
    'used_len': 75,
    'total_len': 186,
    'type': 1
}
```
- RFID reading works correctly
- Label type from RFID matches SET_LABEL_TYPE(1)

---

## Reference: NiimBlueLib Implementation

### D110MV4PrintTask Sequence
Per `src/print_tasks/D110MV4PrintTask.ts`:

1. **printInit()**:
   - `setDensity()`
   - `setLabelType()`
   - `printStart9b(totalPages, pageColor, speed)`

2. **printPage()**:
   - `printStatus()` — **one-way, no response expected** (device quirk)
   - `setPageSize13b(rows, cols, copies, cutHeight, cutType, sendAll, partHeight)`
   - `writeImageData()` — uses EncodedImage with printheadPixels config
   - `pageEnd()`

3. **waitForFinished()**:
   - `waitUntilPrintFinishedByStatusPoll()`
   - `heartbeat()` — **one-way** (device quirk)

### NiimBlueLib Notes
- "Device drops the first packet" after certain commands
- Status and heartbeat sent as one-way to prevent timeout errors
- `printStart9b()`: "First seen on D110M v4"
- `setPageSize13b()`: "First seen on D110M v4"
- D110_M printheadPixels = 96

### Image Encoding (image_encoder.ts)
```typescript
// Pixel is black if not pure white
isBlack = (r !== 255 || g !== 255 || b !== 255)

// MSB-first packing
pixelsOctet |= 1 << (7 - colBit)  // bit 7 = leftmost pixel

// No inversion - black pixel = bit set to 1
```

---

## Potential Next Steps

1. **BLE Traffic Capture**: Use nRF Connect or Wireshark to capture packets from official Niimbot app during a successful print
2. **Test NiimBlue Web App**: Try https://niim.blue with D110_M to verify if web implementation works
3. **Check writeImageData()**: NiimBlueLib's abstraction layer may have additional formatting
4. **PrintBitmapRowIndexed**: Maybe D110_M requires indexed format (for rows with ≤6 black pixels)
5. **Compression**: Check if D110_M firmware requires RLE or other compression
6. **Different Characteristic**: Verify we're writing to correct BLE characteristic for image data

---

## Files Modified During Debug

| File | Changes |
|------|---------|
| `NiimPrintX/nimmy/printer.py` | Added V4_MODELS, start_print_v4(), set_dimension_v4(), get_print_status_v4(), print_image_v4(), various encoding experiments |
| `NiimPrintX/cli/command.py` | Routes d110_m to V4 protocol |
| `tests/test_cli_command.py` | D110_M protocol routing tests |

---

## Current Code State (2026-04-14)

V4 protocol enabled for d110_m with corrected formats per NiimBlueLib:

```python
# V4_MODELS in printer.py
V4_MODELS = frozenset({"d110_m"})

# start_print_v4: 9 bytes
data = struct.pack(">H", quantity) + b"\x00\x00\x00\x00" + bytes([page_color, speed, 0x01])

# set_dimension_v4: 13 bytes with sendAll=1
data = struct.pack(">HHH", height, width, copies) + b"\x00\x00\x00\x00\x01\x00\x00"
```

Commands succeed, printer beeps, but output is still blank. The issue appears to be in:
- Image data format
- Some undocumented initialization sequence
- D110_M 2025 firmware (10.52) specific requirements
