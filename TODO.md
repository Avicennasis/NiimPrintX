# NiimPrintX TODO

## Remaining Upstream Issues (Need Hardware/Research)

- [ ] **#37 — B21S support** — May be similar to B21; needs hardware to verify protocol
- [ ] **#34 — K3 support** — Unknown protocol; needs hardware research
- [ ] **#23 — B3S support** — Unknown protocol; needs hardware research
- [ ] **#18 — macOS CoreBluetooth "Event loop is closed" crash** — bleak async lifecycle bug on macOS Big Sur; may be fixed by bleak 0.22.3 upgrade (needs macOS testing)
- [ ] **#10 — Phomemo printer support** — Different brand/protocol; likely out of scope

## Upstream Issues to Close (No Code Needed)

- [ ] **#44** — "Is project alive?" — Comment: fork is actively maintained
- [ ] **#27** — French user wants Excel VBA printing — Point to CLI docs
- [ ] **#35** — Xubuntu printer setup — Documentation/FAQ (Bluetooth pairing guide)
- [ ] **#25** — D101 Windows pairing — D101 now supported; ask user to retry with latest

## Future Improvements

- [ ] **CI/CD pipeline** — Add GitHub Actions workflow for linting + pytest on push
- [ ] **Expand test suite** — Add async BLE mock tests for printer communication
- [ ] **User config documentation** — Document TOML config format in README
- [ ] **Rotation UI control** (#38) — Add rotation slider/dropdown to the GUI for user-adjustable rotation
- [ ] **Update Flatpak metadata** — Change developer_name from "labbots" to fork maintainer
- [ ] **Screenshot for metainfo** — Add main-window.png (missing from PR #16 binary cherry-pick)

## Completed This Session (2026-04-11)

### Upstream PRs Merged (8)
- [x] #28 — Encoding fix (Korean Windows crash)
- [x] #30 — Device selection propagation
- [x] #36 — D11_H 300dpi support + per-device DPI
- [x] #33 — D110 BLE connection heuristic
- [x] #6 — B1 V2 protocol (with 3 bug fixes)
- [x] #39 — Multi-line text labels
- [x] #16 — Linux desktop/metainfo files
- [x] #41 — Python 3.13 support + bleak bump

### Quick Wins (Tier 1)
- [x] Added d101, B21, D110-M device configs
- [x] Removed devtools imports from 11 files
- [x] Fixed print_label lambda capture bug
- [x] Added None guard to update_canvas_size()

### Feature Work (Tier 2-3)
- [x] Hardened send_command() — raises PrinterException instead of returning None
- [x] Per-device rotation configuration
- [x] Open .niim files from command-line
- [x] User config file (TOML at ~/.config/NiimPrintX/)
- [x] Modern Linux theming (sv-ttk Sun Valley)
- [x] Test suite foundation (13 tests, all passing)
