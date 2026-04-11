# Upstream Open Pull Requests (labbots/NiimPrintX)

> Captured 2026-04-11 from https://github.com/labbots/NiimPrintX/pulls
> 9 open PRs total

---

## High Value — Bug Fixes

| # | Title | Author | Date | Branch | Fixes | Description |
|---|-------|--------|------|--------|-------|-------------|
| [#36](https://github.com/labbots/NiimPrintX/pull/36) | Support D11_H | @corpix | 2025-05-28 | `d11_h` | #8 | Adds support for D11_H (300dpi) printer — fixes the `unpack requires a buffer of 4 bytes` error |
| [#33](https://github.com/labbots/NiimPrintX/pull/33) | D110 connection issue | @teambob | 2025-02-17 | `D110_connect` | #13, #22 | D110 shows as two BT devices — picks the one with no services. Notes better heuristic needed long-term |
| [#30](https://github.com/labbots/NiimPrintX/pull/30) | Changing Device in UI doesn't change device in background | @uab2411 | 2025-02-03 | `fix-device-select-issue` | #11, #13 | UI device selection wasn't propagated everywhere in code |
| [#28](https://github.com/labbots/NiimPrintX/pull/28) | Resolve encoding issues on GUI mode | @kwon0408 | 2025-01-29 | `main` | #26 | Adds `encoding='utf8'` to subprocess.run for font listing — fixes Korean Windows crash |

## High Value — Features

| # | Title | Author | Date | Branch | Description |
|---|-------|--------|------|--------|-------------|
| [#6](https://github.com/labbots/NiimPrintX/pull/6) | Implement Support for B1 Printer | @LorisPolenz | 2024-07-22 | `main` | V2 protocol for B1: new `print_image`, `start_print`, `set_dimention` functions. Tested on 50x30mm and 40x30mm labels. Adds 2s timeout for reliability |
| [#39](https://github.com/labbots/NiimPrintX/pull/39) | Add support for multi line input box | @CMGeorge | 2025-10-27 | `main` | Addresses #21 (multi-line labels) |
| [#16](https://github.com/labbots/NiimPrintX/pull/16) | Add desktop and metainfo file for Linux distributions | @hadess | 2024-10-11 | `wip/hadess/add-desktop` | Desktop file + metainfo for Flatpak/Flathub distribution. Related to #15 |

## Dependency Updates

| # | Title | Author | Date | Branch | Description |
|---|-------|--------|------|--------|-------------|
| [#41](https://github.com/labbots/NiimPrintX/pull/41) | Update dependencies for Python 3.13 | @atanarro | 2025-12-25 | `main` | Adjusted package versions for bleak, pillow, pycairo. Updated Poetry lock. Fixes #31 |

## Questionable / Low Value

| # | Title | Author | Date | Branch | Description |
|---|-------|--------|------|--------|-------------|
| [#43](https://github.com/labbots/NiimPrintX/pull/43) | Update NiimPrintX.gif | @as0045675-commits | 2026-02-03 | `patch-1` | Body just contains clone instructions — likely spam or low-effort |

---

## Summary

| Category | Count |
|----------|-------|
| Bug Fixes | 4 |
| Features | 3 |
| Dependency Updates | 1 |
| Questionable | 1 |
| **Total** | **9** |

### PR → Issue Cross-Reference

| PR | Fixes Issues |
|----|-------------|
| #36 | #8 (D11_H unpack error) |
| #33 | #13, #22 (D110 connection) |
| #30 | #11, #13 (device selection bug) |
| #28 | #26 (Korean Windows encoding) |
| #41 | #31 (Python 3.13 support) |
| #39 | #21 (multi-line labels) |
| #6  | #5, #20 (B1 support) |
| #16 | #15 (Flatpak packaging) |

### Merge Priority Recommendation

1. **#28** (encoding fix) — Small, safe, fixes crash on non-English systems
2. **#30** (device selection fix) — Small bug fix, high impact
3. **#41** (Python 3.13 deps) — Unblocks modern Python installs
4. **#33** (D110 connection) — Fixes most common complaint
5. **#36** (D11_H support) — Fixes 300dpi models
6. **#6** (B1 support) — Larger change, V2 protocol, heavily requested
7. **#39** (multi-line) — Feature addition
8. **#16** (Linux desktop files) — Packaging metadata
9. **#43** (GIF update) — Review carefully, likely skip
