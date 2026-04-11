# Upstream PR Merge & Review Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge all viable upstream PRs from labbots/NiimPrintX into a `dev` branch, reviewing each for bugs, security issues, and conflicts — keeping `main` as a pure upstream clone.

**Architecture:** Cherry-pick/apply each PR's diff onto a `dev` branch created from `main`. PRs are ordered to minimize conflicts. Each merge gets a code review pass (LSP + manual) before committing. Conflicting changes in AppConfig.py, CanvasSelector.py, and printer.py are resolved by merging in dependency order.

**Tech Stack:** Python 3.12+, bleak (BLE), Tkinter, Click, Pillow, pycairo, wand

---

## Conflict Map

These PRs touch overlapping files and must be merged in order:

```
PR #30 (CanvasSelector.py) ──┐
                              ├──> PR #36 touches same file + extends the fix
PR #36 (AppConfig.py,        │
        CanvasSelector.py,   ├──> PR #6 touches same files, adds B1 to same structures
        PrintOption.py,      │
        printer.py,          │
        command.py)  ────────┘
                              
PR #6  (AppConfig.py,
        printer.py,
        command.py,
        PrintOption.py,
        PrinterOperation.py,
        main.py)
```

**Safe (no conflicts):** #28, #33, #16
**Dependency chain:** #30 → #36 → #6
**Separate concern:** #39 (multi-line text), #41 (deps)
**Skip:** #43 (spam)

## Merge Order (conflict-aware)

1. **#28** — Encoding fix (FontList.py, requirements.txt)
2. **#30** — Device selection fix (CanvasSelector.py — 1 line)
3. **#36** — D11_H support (AppConfig, CanvasSelector, PrintOption, printer, command, README)
4. **#33** — D110 connection heuristic (bluetooth.py — 1 line, needs safety check)
5. **#6** — B1 V2 protocol (printer.py, command.py, AppConfig, PrintOption, PrinterOperation — needs fixes)
6. **#39** — Multi-line text (TextTab, TextOperation — cherry-pick code only, skip CI/copilot files)
7. **#16** — Linux desktop files (new files only, no conflicts)
8. **#41** — Python 3.13 deps (pyproject.toml + poetry.lock — do last, regenerate lock)

## Known Issues in PRs (fix during merge)

| PR | Issue | Fix |
|----|-------|-----|
| #6 | Rotation hardcoded to 0 — breaks all non-B1 printers | Make rotation conditional per model |
| #6 | Debug logging force-enabled (`logger.enable`) | Revert to `logger.disable` |
| #6 | B1 max_width changed from 384 to 400 with no explanation | Verify correct value, likely keep 384 |
| #33 | `device.metadata['uuids']` may KeyError on some platforms | Add `.get('uuids', [])` safety |
| #36 | Removes global `print_dpi` but doesn't add `self.print_dpi` fallback | Verify all code paths use per-device DPI |
| #39 | Includes unrelated files (copilot-instructions.md, CI workflow) | Cherry-pick only TextTab/TextOperation changes |

---

### Task 1: Create dev branch and set up upstream remote

**Files:**
- No file changes — git operations only

- [ ] **Step 1: Add upstream remote**

```bash
cd ~/github/NiimPrintX
git remote add upstream https://github.com/labbots/NiimPrintX.git
git fetch upstream
```

- [ ] **Step 2: Create dev branch from main**

```bash
git checkout -b dev main
```

- [ ] **Step 3: Verify clean state**

```bash
git log --oneline -3
git status
```

Expected: On branch `dev`, clean working tree, HEAD matches main.

---

### Task 2: Merge PR #28 — Encoding fix (Korean Windows crash)

**Fixes:** Issue #26
**Risk:** Low — single line change + dependency bumps
**Files:**
- Modify: `NiimPrintX/ui/component/FontList.py:30`
- Modify: `requirements.txt`

- [ ] **Step 1: Apply the encoding fix**

In `FontList.py` line 30, add `encoding='utf8'` to the `subprocess.run` call:

```python
result = subprocess.run([magick_path, '-list', 'font'], stdout=subprocess.PIPE, text=True, encoding='utf8')
```

- [ ] **Step 2: Apply requirements.txt bumps**

Update `setuptools` from `69.5.1` to `70.0.0` and `wheel` from `0.37.1` to `0.38.1`.

- [ ] **Step 3: Code review**

- Verify `encoding='utf8'` doesn't conflict with `text=True` (it doesn't — encoding overrides the default locale codec)
- Check if any other subprocess calls have the same issue (grep for `subprocess.run`)
- Security: no concerns

- [ ] **Step 4: Commit**

```bash
git add NiimPrintX/ui/component/FontList.py requirements.txt
git commit -m "fix: resolve encoding crash on non-ASCII font names (#28)

Adds explicit UTF-8 encoding to ImageMagick font list subprocess call.
Fixes GUI crash on Korean Windows (and any non-ASCII locale).
Upstream: labbots/NiimPrintX#28 by @kwon0408

Closes #26"
```

---

### Task 3: Merge PR #30 — Device selection propagation fix

**Fixes:** Issues #11, #13 (partially)
**Risk:** Low — single line addition
**Files:**
- Modify: `NiimPrintX/ui/widget/CanvasSelector.py:42`

- [ ] **Step 1: Apply the fix**

In `CanvasSelector.py`, inside `update_device_label_size()`, after the `if device:` block sets `label_sizes`, add:

```python
self.config.device = device
```

- [ ] **Step 2: Code review**

- Verify `self.config.device` is used elsewhere (printer.py, PrintOption.py, PrinterOperation.py all reference it)
- This was the root cause: changing the dropdown didn't update the config singleton, so print always used the initial device
- Security: no concerns

- [ ] **Step 3: Commit**

```bash
git add NiimPrintX/ui/widget/CanvasSelector.py
git commit -m "fix: propagate device selection from UI dropdown to config (#30)

Changing the device in the GUI dropdown now actually updates config.device.
Previously, the printer always connected as the initial default device.
Upstream: labbots/NiimPrintX#30 by @uab2411

Partially addresses #11, #13"
```

---

### Task 4: Merge PR #36 — D11_H (300dpi) support

**Fixes:** Issue #8, partially #4, #32
**Risk:** Medium — touches 6 files, changes DPI architecture from global to per-device
**Files:**
- Modify: `NiimPrintX/ui/AppConfig.py` (add d11_h device, move print_dpi to per-device)
- Modify: `NiimPrintX/ui/widget/CanvasSelector.py:111` (use per-device DPI)
- Modify: `NiimPrintX/ui/widget/PrintOption.py:114` (use per-device DPI)
- Modify: `NiimPrintX/nimmy/printer.py:297` (truncate packet data to 4 bytes)
- Modify: `NiimPrintX/cli/command.py` (add d11_h to model choices)
- Modify: `README.md` (update CLI help text)

- [ ] **Step 1: Apply AppConfig.py changes**

Remove global `self.print_dpi = 203`. Add `"print_dpi": 203` to each existing device dict. Add new `d11_h` device entry with `"print_dpi": 300`. See PR diff for exact structure.

- [ ] **Step 2: Apply CanvasSelector.py DPI change**

Change `mm_to_pixels` to use per-device DPI:

```python
def mm_to_pixels(self, mm):
    inches = mm / 25.4
    return int(inches * self.config.label_sizes[self.config.device]["print_dpi"])
```

Also add `self.update_canvas_size()` call in `update_device_label_size()` after setting label sizes.

- [ ] **Step 3: Apply PrintOption.py DPI change**

Same pattern — change `mm_to_pixels`:

```python
def mm_to_pixels(self, mm):
    inches = mm / 25.4
    return int(inches * self.config.label_sizes[self.config.device]["print_dpi"])
```

- [ ] **Step 4: Apply printer.py packet fix**

Line 297 — truncate to 4 bytes:

```python
page, progress1, progress2 = struct.unpack(">HBB", packet.data[:4])
```

This fixes the `unpack requires a buffer of 4 bytes` error for printers returning 8-byte status packets.

- [ ] **Step 5: Apply command.py CLI model addition**

Add `"d11_h"` to both Click model choice lists and to the width/density conditionals.

- [ ] **Step 6: Apply README.md update**

Update the CLI help text to show d11_h in the model list.

- [ ] **Step 7: Code review**

- **Critical:** Verify all `mm_to_pixels` callers now have access to `self.config.device` — if device is not set yet, `self.config.label_sizes[self.config.device]` will KeyError. Task 3 (PR #30) fixes device propagation, so merging in order is essential.
- **Critical:** `packet.data[:4]` is safe — takes first 4 bytes regardless of actual length, works for both 4-byte and 8-byte responses.
- Verify no other code references the removed `self.print_dpi` (grep for `print_dpi`)
- Security: no concerns

- [ ] **Step 8: Commit**

```bash
git add NiimPrintX/ui/AppConfig.py NiimPrintX/ui/widget/CanvasSelector.py \
  NiimPrintX/ui/widget/PrintOption.py NiimPrintX/nimmy/printer.py \
  NiimPrintX/cli/command.py README.md
git commit -m "feat: add D11_H (300dpi) support with per-device DPI (#36)

Moves print_dpi from global config to per-device setting.
Adds D11_H model (300dpi) to CLI and GUI.
Fixes 'unpack requires a buffer of 4 bytes' by truncating status packets.
Upstream: labbots/NiimPrintX#36 by @corpix

Fixes #8, partially addresses #4, #32"
```

---

### Task 5: Merge PR #33 — D110 BLE connection heuristic

**Fixes:** Issues #13, #22 (partially)
**Risk:** Medium — changes device discovery logic for ALL models
**Files:**
- Modify: `NiimPrintX/nimmy/bluetooth.py:13`

- [ ] **Step 1: Apply the fix with safety improvement**

The PR filters BLE devices by checking `len(device.metadata['uuids'])==0`. The D110 shows as two BT devices — the correct one has no service UUIDs.

Apply with a safety guard for platforms where metadata might not have 'uuids':

```python
if device.name and device.name.lower().startswith(device_name_prefix.lower()) and len(device.metadata.get('uuids', [])) == 0:
```

- [ ] **Step 2: Code review**

- **Risk:** This heuristic may break OTHER printers that DO expose UUIDs. The PR author acknowledges "In the longer term the user should be able to choose the device in the UI or we should find a better heuristic."
- **Decision:** Apply it — the D110 connection issue is the #1 complaint, and other models that expose UUIDs would fail to connect (which they may already). The fallback `raise BLEException` still fires if no matching device is found.
- **Safety:** Added `.get('uuids', [])` to prevent KeyError on platforms with different metadata structures.
- Security: no concerns

- [ ] **Step 3: Commit**

```bash
git add NiimPrintX/nimmy/bluetooth.py
git commit -m "fix: improve D110 BLE device discovery heuristic (#33)

D110 appears as two Bluetooth devices. Filters for the one with no
service UUIDs, which is the correct one for printing.
Added .get() safety for cross-platform metadata compatibility.
Upstream: labbots/NiimPrintX#33 by @teambob

Partially addresses #13, #22"
```

---

### Task 6: Merge PR #6 — B1 V2 protocol support (with fixes)

**Fixes:** Issues #5, #20, partially #40, #42
**Risk:** High — largest PR, adds new protocol, has bugs that need fixing
**Files:**
- Modify: `NiimPrintX/nimmy/printer.py` (add V2 methods: print_imageV2, start_printV2, set_dimensionV2, enhanced debug logging)
- Modify: `NiimPrintX/cli/command.py` (B1 routing to V2, max_width change)
- Modify: `NiimPrintX/ui/AppConfig.py` (add B1 device with label sizes)
- Modify: `NiimPrintX/ui/widget/PrintOption.py` (conditional rotation per model)
- Modify: `NiimPrintX/ui/widget/PrinterOperation.py` (B1 routing to V2)
- **DO NOT** modify: `NiimPrintX/ui/main.py` (PR enables debug logging — revert this)

- [ ] **Step 1: Apply printer.py V2 methods**

Add the three new async methods to PrinterClient:
- `print_imageV2()` — V2 print flow (no end_print, uses set_dimensionV2, line-by-line with 10ms delay, 2s final sleep)
- `start_printV2(quantity)` — Sends quantity as 2-byte LE packed with padding
- `set_dimensionV2(w, h, copies)` — Sends width, height, copies as 3x big-endian shorts

Also add the enhanced debug logging to `send_command()` (request code + response data + byte count).

- [ ] **Step 2: Apply command.py B1 routing**

In `_print()`, add conditional for B1:

```python
if model == "b1":
    print_info("Printing with B1 model")
    await printer.print_imageV2(image, density=density, quantity=quantity)
else:
    print_info("Printing with D model")
    await printer.print_image(image, density=density, quantity=quantity, ...)
```

**FIX:** Keep `max_width_px = 384` for B1 (PR changes it to 400 with no justification — 384 is the established value).

- [ ] **Step 3: Apply AppConfig.py B1 device**

Add B1 to label_sizes dict. Since Task 4 (PR #36) already added per-device `print_dpi`, include it:

```python
"b1": {
    "size": {
        "50mm x 30mm": (50, 30),
        "50mm x 15mm": (50, 14),
        "60mm x 40mm": (60, 40),
        "40mm x 30mm": (40, 30),
    },
    "density": 3,
    "print_dpi": 203
}
```

- [ ] **Step 4: Apply PrintOption.py rotation fix**

**FIX:** The PR hardcodes rotation to 0 for ALL printers. This must be conditional:

```python
if self.config.device == "b1":
    image = image.rotate(0, PIL.Image.NEAREST, expand=True)
else:
    image = image.rotate(-90, PIL.Image.NEAREST, expand=True)
```

- [ ] **Step 5: Apply PrinterOperation.py B1 routing**

In the `print()` method, route B1 to V2:

```python
if self.config.device == "b1":
    await self.printer.print_imageV2(image, density, quantity)
else:
    await self.printer.print_image(image, density, quantity)
```

- [ ] **Step 6: DO NOT apply main.py debug logging change**

The PR uncomments `logger.enable('NiimPrintX.nimmy')` — this should stay disabled in production. Skip this change entirely.

- [ ] **Step 7: Code review**

- **V2 Protocol:** The `start_printV2` uses little-endian `struct.pack('H', quantity)` while other methods use big-endian `>H`. Verify this is intentional (it is — the B1 firmware expects LE for this command, per niimblue reference implementation).
- **sleep(0.01) per line:** Necessary for B1 buffer management. The 2s final sleep is crude but functional. Both are documented in the PR.
- **assert 0 <= quantity <= 65535:** This will raise AssertionError in production if assertions are enabled. Consider changing to a proper ValueError, but don't gold-plate — leave as-is for now.
- **Security:** `write_raw()` sends raw bytes to BLE — no injection risk since data is locally generated from PIL image encoding.

- [ ] **Step 8: Commit**

```bash
git add NiimPrintX/nimmy/printer.py NiimPrintX/cli/command.py \
  NiimPrintX/ui/AppConfig.py NiimPrintX/ui/widget/PrintOption.py \
  NiimPrintX/ui/widget/PrinterOperation.py
git commit -m "feat: add B1 printer support via V2 protocol (#6)

Adds print_imageV2, start_printV2, set_dimensionV2 for B1's different
command set. Routes B1 through V2 in both CLI and GUI.
Fixes: rotation made conditional per model (B1=0, others=90).
Fix: kept max_width at 384 (PR changed to 400 without justification).
Fix: debug logging NOT force-enabled in production.
Upstream: labbots/NiimPrintX#6 by @LorisPolenz

Fixes #5, #20, partially addresses #40, #42"
```

---

### Task 7: Merge PR #39 — Multi-line text support (cherry-pick)

**Fixes:** Issue #21
**Risk:** Medium — changes Text widget type from Entry to Text, affects all text operations
**Files:**
- Modify: `NiimPrintX/ui/widget/TextTab.py` (Entry → Text widget with scrollbar)
- Modify: `NiimPrintX/ui/widget/TextOperation.py` (multiline=True for font metrics, Text widget API)
- **DO NOT** add: `.github/copilot-instructions.md` (unrelated)
- **DO NOT** add: `.github/workflows/python-app.yml` (unrelated CI — evaluate separately)
- **DO NOT** add: `requirements-ci.txt` (unrelated — evaluate separately)

- [ ] **Step 1: Apply TextTab.py changes**

Replace the single-line `tk.Entry` with a multi-line `tk.Text` widget inside a frame with scrollbar. Update all `.get()` and `.insert()` calls to use Text widget API (`"1.0"`, `"end-1c"`). See PR diff for exact widget construction.

- [ ] **Step 2: Apply TextOperation.py changes**

- Change `multiline=False` to `multiline=True` in `get_font_metrics()`
- Update text positioning: `y=int(metrics.ascender)` for proper multi-line rendering
- Change all `content_entry.get()` to `content_entry.get("1.0", "end-1c")`
- Change all `content_entry.delete(0, tk.END)` to `content_entry.delete("1.0", tk.END)`
- Change all `content_entry.insert(0, ...)` to `content_entry.insert("1.0", ...)`

- [ ] **Step 3: Code review**

- The Entry→Text migration is clean. Text widget uses `"1.0"` (line 1, char 0) as start index and `"end-1c"` (end minus trailing newline) for reading.
- `multiline=True` in wand's `get_font_metrics` correctly measures multi-line text dimensions.
- The y-position change from `text_height / 2 + ascender / 2` to just `ascender` is correct for top-aligned multi-line rendering.
- Scrollbar addition is appropriate for the Text widget.
- Security: no concerns

- [ ] **Step 4: Commit**

```bash
git add NiimPrintX/ui/widget/TextTab.py NiimPrintX/ui/widget/TextOperation.py
git commit -m "feat: support multi-line text labels (#39)

Replaces single-line Entry with multi-line Text widget with scrollbar.
Updates font metrics to use multiline=True for proper text measurement.
Upstream: labbots/NiimPrintX#39 by @CMGeorge (cherry-picked, code only)

Fixes #21"
```

---

### Task 8: Merge PR #16 — Linux desktop/metainfo files

**Fixes:** Issue #15 (Flatpak packaging)
**Risk:** Low — new files only, no code changes
**Files:**
- Create: `assets/linux/io.github.labbots.NiimPrintX.desktop`
- Create: `assets/linux/io.github.labbots.NiimPrintX.metainfo.xml`
- Create: `assets/linux/io.github.labbots.NiimPrintX.mime.xml`
- Create: `assets/linux/main-window.png`
- Create: `assets/linux/niimprintx` (launcher script)

- [ ] **Step 1: Fetch and apply PR #16 files**

Since these are new files, fetch the PR branch and cherry-pick:

```bash
git fetch upstream refs/pull/16/head:pr-16
git cherry-pick --no-commit pr-16
```

Or manually create the files from the diff content.

- [ ] **Step 2: Code review**

- Desktop file: standard freedesktop format, categories=Office, MimeType for .niim files. Clean.
- Metainfo: references `labbots` as developer — may want to update later when project ownership changes.
- Launcher script: simple `exec python -m NiimPrintX.ui "$@"` — correct.
- MIME XML: registers `application/x-niim` for `.niim` files — matches FileMenu save format.
- Security: no concerns. The launcher script has proper exec to replace the shell process.

- [ ] **Step 3: Commit**

```bash
git add assets/linux/
git commit -m "feat: add Linux desktop and metainfo files for Flatpak (#16)

Adds .desktop file, metainfo XML, MIME type registration,
launcher script, and screenshot for Linux distribution packaging.
Upstream: labbots/NiimPrintX#16 by @hadess

Addresses #15"
```

---

### Task 9: Merge PR #41 — Python 3.13 dependency update

**Fixes:** Issue #31
**Risk:** Medium — changes version constraints and lock file
**Files:**
- Modify: `pyproject.toml` (Python version constraint, package versions)
- Modify: `poetry.lock` (regenerated)

- [ ] **Step 1: Update pyproject.toml**

Change Python constraint from `>=3.12,<3.13` to `>=3.12,<3.14` (or `>=3.12`).
Update package version constraints as needed for 3.13 compatibility:
- `bleak` version range
- `pillow` version range  
- `pycairo` version range

- [ ] **Step 2: Regenerate poetry.lock**

Rather than applying the PR's lock file (generated with Poetry 2.1.2 which may differ from local Poetry version):

```bash
poetry lock --no-update  # Or poetry lock if version bumps are needed
```

- [ ] **Step 3: Code review**

- Verify the Python version constraint allows 3.13 but doesn't allow 3.14+ (untested)
- Check that bleak, pillow, pycairo versions are compatible with 3.13
- Security: check for any known vulnerabilities in updated package versions

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "build: update dependencies for Python 3.13 support (#41)

Widens Python version constraint and updates bleak, pillow, pycairo
for Python 3.13 compatibility.
Upstream: labbots/NiimPrintX#41 by @atanarro

Fixes #31"
```

---

### Task 10: Final review and issue cross-reference

- [ ] **Step 1: Verify all files are consistent**

```bash
cd ~/github/NiimPrintX
python -m py_compile NiimPrintX/nimmy/printer.py
python -m py_compile NiimPrintX/ui/AppConfig.py
python -m py_compile NiimPrintX/ui/widget/CanvasSelector.py
python -m py_compile NiimPrintX/ui/widget/PrintOption.py
python -m py_compile NiimPrintX/ui/widget/TextTab.py
python -m py_compile NiimPrintX/ui/widget/TextOperation.py
python -m py_compile NiimPrintX/cli/command.py
python -m py_compile NiimPrintX/nimmy/bluetooth.py
python -m py_compile NiimPrintX/ui/component/FontList.py
```

- [ ] **Step 2: Run flake8 lint check**

```bash
flake8 NiimPrintX/ --count --select=E9,F63,F7,F82 --show-source --statistics
```

- [ ] **Step 3: Grep for broken references**

```bash
# Verify no code still references the removed global print_dpi
grep -rn "self\.print_dpi" NiimPrintX/ --include="*.py"
# Should only find per-device references via label_sizes dict

# Verify all Entry→Text API calls were updated
grep -rn "content_entry\.get()" NiimPrintX/ --include="*.py"
# Should return zero results (all should be .get("1.0", "end-1c"))
```

- [ ] **Step 4: Document resolved issues**

After all merges, update UPSTREAM_ISSUES.md (on the issues branch) to mark which issues are addressed:

| Issue | Status |
|-------|--------|
| #1 | Fixed by PR #36 (packet truncation) |
| #4 | Partially fixed by PR #36 (D11-H DPI) |
| #5 | Fixed by PR #6 (B1 label sizes) |
| #8 | Fixed by PR #36 (D11_H + packet fix) |
| #11 | Partially fixed by PR #30 (device selection) |
| #13 | Partially fixed by PR #30 + #33 |
| #15 | Addressed by PR #16 (Linux packaging files) |
| #20 | Fixed by PR #6 (B1 V2 protocol) |
| #21 | Fixed by PR #39 (multi-line text) |
| #22 | Partially fixed by PR #33 (D110 heuristic) |
| #26 | Fixed by PR #28 (UTF-8 encoding) |
| #31 | Fixed by PR #41 (Python 3.13 deps) |
| #32 | Partially fixed by PR #36 (packet truncation) |
| #40 | Partially addressed by PR #6 (B1 support) |
| #42 | Partially addressed by PR #6 (B1 support) |

**15 of 31 issues addressed by these 8 PRs.**

- [ ] **Step 5: Push dev branch**

```bash
git push -u origin dev
```
