# AppConfig God Object Split Plan

**Status:** Planning  
**Date:** 2026-04-12  
**Scope:** Split `AppConfig` (131 lines) into 3 focused classes: `ImmutableConfig`, `CanvasState`, `PrinterState`

---

## 1. Current State Analysis

### All AppConfig Attributes (from `__init__` + method)

| Attribute | Type | Mutated After Init? | Description |
|---|---|---|---|
| `os_system` | `str` | No | `platform.system()` result |
| `current_dir` | `str` | No | Directory of `AppConfig.py` |
| `icon_folder` | `str` | No | `current_dir/icons` |
| `cache_dir` | `str` | No | `platformdirs.user_cache_dir("NiimPrintX")` |
| `label_sizes` | `dict` | At init only | Device configs (8 built-in + user config merge) |
| `canvas` | `tk.Canvas | None` | Yes | Recreated on every label size change |
| `bounding_box` | `int | None` | Yes | Canvas rectangle ID, recreated with canvas |
| `text_items` | `dict` | Yes | `{canvas_id: {font_image, font_props, content, handle, bbox}}` |
| `image_items` | `dict` | Yes | `{canvas_id: {image, original_image, bbox, handle}}` |
| `current_selected` | `int | None` | Yes | Currently selected text item canvas ID |
| `current_selected_image` | `int | None` | Yes | Currently selected image item canvas ID |
| `frames` | `dict` | Yes | `{top_frame, bottom_frame, status_frame}` - Tk frame refs |
| `device` | `str` | Yes | Current device model name (e.g., "d110") |
| `current_label_size` | `str | None` | Yes | Current label size string (e.g., "30mm x 15mm") |
| `printer_connected` | `bool` | Yes | Set from async heartbeat thread + UI thread |
| `print_job` | `bool` | Yes | True while print job is active |
| `mm_to_pixels()` | method | N/A | Depends on `device` and `label_sizes` |

### The Core Problem

`AppConfig` is:
1. **A platform config holder** (os_system, paths) - immutable after construction
2. **A canvas/editor state bag** (canvas, items, selections) - mutated constantly during editing
3. **A printer state bag** (device, connected, print_job) - mutated from async threads
4. **A frame registry** (frames dict) - only used by `main.py` for layout

These four concerns have different lifecycles, thread-safety requirements, and consumer sets.

---

## 2. Proposed Architecture

### 2.1 `ImmutableConfig`

Frozen after construction. No thread-safety concerns.

```python
class ImmutableConfig:
    def __init__(self) -> None:
        self.os_system: str = platform.system()
        self.current_dir: str = os.path.dirname(os.path.realpath(__file__))
        self.icon_folder: str = os.path.join(self.current_dir, "icons")
        self.cache_dir: str = platformdirs.user_cache_dir("NiimPrintX")
        self.label_sizes: dict = { ... }  # built-in + user config merge
        # Note: label_sizes is "immutable" in that no runtime code adds/removes
        # entries. It's populated once at init from device configs + user config.
```

**Key decision:** `label_sizes` goes here because it's populated once at init and never mutated at runtime. All device configs are static data. Consumer code only reads `label_sizes[device]` — it never writes to it.

### 2.2 `CanvasState`

All editor/canvas state. Only accessed from the Tk main thread.

```python
class CanvasState:
    def __init__(self) -> None:
        self.canvas: tk.Canvas | None = None
        self.bounding_box: int | None = None
        self.text_items: dict = {}
        self.image_items: dict = {}
        self.current_selected: int | None = None
        self.current_selected_image: int | None = None
        self.frames: dict = {}
```

**Key decision:** `frames` lives here because it's a UI layout concern. Only `main.py` writes to `frames`, and it's a canvas-adjacent concern (top_frame hosts the canvas).

### 2.3 `PrinterState`

Device selection and printer connection state. Written from both the Tk thread and the asyncio thread.

```python
class PrinterState:
    def __init__(self, default_device: str) -> None:
        self.device: str = default_device
        self.current_label_size: str | None = None
        self.printer_connected: bool = False
        self.print_job: bool = False
```

**Key decision:** `device` and `current_label_size` go here rather than in `ImmutableConfig` because they're mutable — the user changes them via CanvasSelector dropdowns. They represent "which printer model is selected" which is logically printer state.

### 2.4 `mm_to_pixels()` — Where Does It Live?

This method reads `self.device` (PrinterState) and `self.label_sizes` (ImmutableConfig). Options:

- **Option A (recommended):** Make it a standalone function: `mm_to_pixels(mm, dpi)` — callers pass the DPI from `immutable_config.label_sizes[printer_state.device]["print_dpi"]`. Simplest, no cross-object coupling.
- **Option B:** Put it on `ImmutableConfig` with a device parameter: `immutable_config.mm_to_pixels(mm, device)`.
- **Option C:** Put it on `PrinterState` with a label_sizes reference. Creates coupling.

**Recommendation:** Option A. The callers (CanvasSelector, PrintOption) already have both objects. A free function is easiest to test and has zero coupling.

---

## 3. Attribute-to-Class Mapping

| Attribute | Current Home | New Home | Rationale |
|---|---|---|---|
| `os_system` | AppConfig | ImmutableConfig | Read-only platform detection |
| `current_dir` | AppConfig | ImmutableConfig | Read-only path |
| `icon_folder` | AppConfig | ImmutableConfig | Read-only path |
| `cache_dir` | AppConfig | ImmutableConfig | Read-only path |
| `label_sizes` | AppConfig | ImmutableConfig | Static device config data |
| `canvas` | AppConfig | CanvasState | Mutable UI widget |
| `bounding_box` | AppConfig | CanvasState | Mutable canvas item ID |
| `text_items` | AppConfig | CanvasState | Mutable editor state |
| `image_items` | AppConfig | CanvasState | Mutable editor state |
| `current_selected` | AppConfig | CanvasState | Mutable selection state |
| `current_selected_image` | AppConfig | CanvasState | Mutable selection state |
| `frames` | AppConfig | CanvasState | Mutable UI layout refs |
| `device` | AppConfig | PrinterState | Mutable device selection |
| `current_label_size` | AppConfig | PrinterState | Mutable label selection |
| `printer_connected` | AppConfig | PrinterState | Mutable connection state |
| `print_job` | AppConfig | PrinterState | Mutable job state |
| `mm_to_pixels()` | AppConfig | Free function | Depends on 2 objects; decouple |

---

## 4. Consumer Mapping

For each file, which of the 3 new objects it needs:

| File | ImmutableConfig | CanvasState | PrinterState | Specific Attributes Used |
|---|---|---|---|---|
| **main.py** | Yes | Yes | Yes | `os_system`, `current_selected`, `current_selected_image`, `canvas` (tag_bind), `frames` (creates 3), `image_items` (shutdown cleanup), `text_items` (shutdown cleanup), `print_job` (quit dialog) |
| **PrintOption.py** | Yes | Yes | Yes | `printer_connected` (R/W), `print_job` (R/W), `device`, `label_sizes` (density/rotation/DPI), `canvas`, `bounding_box`, `image_items`, `text_items`, `os_system`, `mm_to_pixels()` |
| **PrinterOperation.py** | Yes | - | Yes | `printer_connected`, `device`, `label_sizes` (V2_MODELS check uses device) |
| **FileMenu.py** | Yes | Yes | Yes | `device` (R/W), `current_label_size` (R/W), `label_sizes`, `text_items` (R/W), `image_items` (R/W), `canvas` (create_image, coords) |
| **CanvasSelector.py** | Yes | Yes | Yes | `device` (R/W), `label_sizes`, `canvas` (R/W, destroy+create), `bounding_box` (R/W), `text_items` (R/W clear), `image_items` (R/W clear), `current_selected` (R/W), `current_selected_image` (R/W), `frames`, `mm_to_pixels()`, `current_label_size` (W), `printer_connected` (W) |
| **CanvasOperation.py** | - | Yes | - | `current_selected`, `current_selected_image`, `text_items`, `image_items`, `canvas` |
| **TextOperation.py** | - | Yes | - | `canvas`, `text_items`, `current_selected` |
| **ImageOperation.py** | - | Yes | - | `canvas`, `image_items`, `current_selected_image`, `bounding_box` |
| **TextTab.py** | Yes | Yes | - | `os_system`, `current_selected` (read in `update_text_properties`) |
| **IconTab.py** | Yes | - | - | `os_system`, `icon_folder` |
| **StatusBar.py** | - | - | - | None directly (receives `connection` bool via method call) |
| **TabbedIconGrid.py** | - | - | - | None (receives `base_folder` string, not config) |

### Summary of Object Dependencies

| Object | Consumers |
|---|---|
| ImmutableConfig | main.py, PrintOption.py, PrinterOperation.py, FileMenu.py, CanvasSelector.py, TextTab.py, IconTab.py |
| CanvasState | main.py, PrintOption.py, FileMenu.py, CanvasSelector.py, CanvasOperation.py, TextOperation.py, ImageOperation.py, TextTab.py |
| PrinterState | main.py, PrintOption.py, PrinterOperation.py, FileMenu.py, CanvasSelector.py |

**StatusBar** and **TabbedIconGrid** need no config objects at all. StatusBar already receives data via `update_status(bool)`. TabbedIconGrid receives `base_folder` as a constructor arg.

---

## 5. Migration Strategy

### Phase 1: Create New Classes, AppConfig Delegates (LOW RISK)

1. Create `ImmutableConfig`, `CanvasState`, `PrinterState` in new file `NiimPrintX/ui/config.py` (or one file per class in `NiimPrintX/ui/config/`).
2. `AppConfig.__init__` creates all three internally:
   ```python
   class AppConfig:
       def __init__(self):
           self._immutable = ImmutableConfig()
           self._canvas = CanvasState()
           self._printer = PrinterState(default_device=...)
   ```
3. Add `@property` delegators on `AppConfig` for every attribute so all existing code continues to work unchanged:
   ```python
   @property
   def os_system(self): return self._immutable.os_system
   @property
   def canvas(self): return self._canvas.canvas
   @canvas.setter
   def canvas(self, val): self._canvas.canvas = val
   # ... etc for all 16 attributes
   ```
4. Add accessor properties to expose the sub-objects:
   ```python
   @property
   def immutable(self) -> ImmutableConfig: return self._immutable
   @property
   def canvas_state(self) -> CanvasState: return self._canvas
   @property
   def printer_state(self) -> PrinterState: return self._printer
   ```
5. Run full test suite. Every test should pass unchanged.

**Outcome:** Zero behavioral change. All 112 tests pass. New classes exist and are tested independently.

### Phase 2: Migrate Consumers File by File (MEDIUM RISK)

Migrate one file at a time in order of least coupling:

**Wave 1 — Simple consumers (1 object needed):**
1. `CanvasOperation.py` — change `config` param to `canvas_state: CanvasState`
2. `TextOperation.py` — change `config` param to `canvas_state: CanvasState`
3. `ImageOperation.py` — change `config` param to `canvas_state: CanvasState`
4. `PrinterOperation.py` — change `config` param to `(immutable: ImmutableConfig, printer: PrinterState)`
5. `StatusBar.py` — already decoupled (takes no config attributes directly)
6. `TabbedIconGrid.py` — already decoupled

**Wave 2 — Two-object consumers:**
7. `TextTab.py` — needs `ImmutableConfig` (os_system) + `CanvasState` (current_selected via TextOperation)
8. `IconTab.py` — needs `ImmutableConfig` (os_system, icon_folder)

**Wave 3 — Three-object consumers (most complex):**
9. `CanvasSelector.py` — needs all 3 objects + `mm_to_pixels` free function
10. `FileMenu.py` — needs all 3 objects
11. `PrintOption.py` — needs all 3 objects + `mm_to_pixels` free function
12. `main.py` — orchestrator; passes individual objects to each widget

Each file migration:
- Update constructor signature to accept individual state objects instead of `config: AppConfig`
- Replace `self.config.X` with `self.canvas_state.X` / `self.printer_state.X` / `self.immutable.X`
- Update the caller in `main.py` (or parent widget) to pass the right objects
- Run tests after each file

### Phase 3: Remove AppConfig (LOW RISK)

1. Delete `AppConfig` class
2. Delete `AppConfig.py` file
3. Update `main.py` to construct the 3 objects directly:
   ```python
   self.immutable = ImmutableConfig()
   self.canvas_state = CanvasState()
   self.printer_state = PrinterState(default_device=next(iter(self.immutable.label_sizes)))
   ```
4. Remove all `from .AppConfig import AppConfig` imports
5. Final test run

---

## 6. File-by-File Changes

### New files

| File | Contents |
|---|---|
| `NiimPrintX/ui/config.py` | `ImmutableConfig`, `CanvasState`, `PrinterState` classes + `mm_to_pixels(mm, dpi)` free function |

### Modified files (12 total)

#### `NiimPrintX/ui/AppConfig.py`
- **Phase 1:** Refactor to delegate to 3 sub-objects via properties. Add `.immutable`, `.canvas_state`, `.printer_state` accessors.
- **Phase 3:** Delete this file.

#### `NiimPrintX/ui/main.py`
- **Phase 2 (Wave 3):** Replace `self.app_config = AppConfig()` with 3 separate object constructions. Pass appropriate objects to each widget constructor. Update `on_close` to reference `self.canvas_state.image_items`, `self.printer_state.print_job`, etc.
- Specific changes:
  - `self.app_config.os_system` -> `self.immutable.os_system`
  - `self.app_config.current_selected` -> `self.canvas_state.current_selected`
  - `self.app_config.canvas.tag_bind(...)` -> `self.canvas_state.canvas.tag_bind(...)`
  - `self.app_config.frames[...]` -> `self.canvas_state.frames[...]`
  - `self.app_config.image_items` -> `self.canvas_state.image_items`
  - `self.app_config.text_items` -> `self.canvas_state.text_items`
  - `self.app_config.print_job` -> `self.printer_state.print_job`

#### `NiimPrintX/ui/widget/CanvasOperation.py`
- **Phase 2 (Wave 1):** Constructor: `config: AppConfig` -> `canvas_state: CanvasState`
- Replace all `self.config.` with `self.canvas_state.`
- Attributes used: `current_selected`, `current_selected_image`, `text_items`, `image_items`, `canvas`

#### `NiimPrintX/ui/widget/TextOperation.py`
- **Phase 2 (Wave 1):** Constructor: `config` -> `canvas_state: CanvasState`
- Replace all `self.config.` with `self.canvas_state.`
- Attributes used: `canvas`, `text_items`, `current_selected`

#### `NiimPrintX/ui/widget/ImageOperation.py`
- **Phase 2 (Wave 1):** Constructor: `config` -> `canvas_state: CanvasState`
- Replace all `self.config.` with `self.canvas_state.`
- Attributes used: `canvas`, `image_items`, `current_selected_image`, `bounding_box`

#### `NiimPrintX/ui/widget/PrinterOperation.py`
- **Phase 2 (Wave 1):** Constructor: `config` -> `(immutable: ImmutableConfig, printer: PrinterState)`
- `self.config.printer_connected` -> `self.printer.printer_connected`
- `self.config.device` -> `self.printer.device`
- `self.config.device in V2_MODELS` -> `self.printer.device in V2_MODELS`

#### `NiimPrintX/ui/widget/TextTab.py`
- **Phase 2 (Wave 2):** Constructor: `config` -> `(immutable: ImmutableConfig, canvas_state: CanvasState)`
- `self.config.os_system` -> `self.immutable.os_system`
- `self.config.current_selected` -> `self.canvas_state.current_selected`
- Pass `canvas_state` to `TextOperation(self, canvas_state)`

#### `NiimPrintX/ui/widget/IconTab.py`
- **Phase 2 (Wave 2):** Constructor: `config` -> `(immutable: ImmutableConfig, canvas_state: CanvasState)`
- `self.config.os_system` -> `self.immutable.os_system`
- `self.config.icon_folder` -> `self.immutable.icon_folder`
- Pass `canvas_state` to `ImageOperation(canvas_state)`

#### `NiimPrintX/ui/widget/CanvasSelector.py`
- **Phase 2 (Wave 3):** Constructor: `config: AppConfig` -> `(immutable: ImmutableConfig, canvas_state: CanvasState, printer: PrinterState)`
- Heaviest refactor — uses all 3 objects extensively
- `self.config.label_sizes` -> `self.immutable.label_sizes`
- `self.config.device` -> `self.printer.device`
- `self.config.canvas` -> `self.canvas_state.canvas`
- `self.config.bounding_box` -> `self.canvas_state.bounding_box`
- `self.config.mm_to_pixels(x)` -> `mm_to_pixels(x, self.immutable.label_sizes[self.printer.device]["print_dpi"])`
- `self.config.printer_connected = False` -> `self.printer.printer_connected = False`
- `self.config.frames["top_frame"]` -> `self.canvas_state.frames["top_frame"]`
- `self.config.text_items = {}` -> `self.canvas_state.text_items = {}`
- `self.config.current_selected = None` -> `self.canvas_state.current_selected = None`
- `self.config.current_label_size = label_size` -> `self.printer.current_label_size = label_size`

#### `NiimPrintX/ui/widget/FileMenu.py`
- **Phase 2 (Wave 3):** Constructor: `config: AppConfig` -> `(immutable: ImmutableConfig, canvas_state: CanvasState, printer: PrinterState)`
- Save: `self.config.device` -> `self.printer.device`, `self.config.text_items` -> `self.canvas_state.text_items`, etc.
- Load: `self.config.label_sizes` -> `self.immutable.label_sizes`

#### `NiimPrintX/ui/widget/PrintOption.py`
- **Phase 2 (Wave 3):** Constructor: `config: AppConfig` -> `(immutable: ImmutableConfig, canvas_state: CanvasState, printer: PrinterState)`
- Many replacements throughout the file (most attribute-heavy consumer)
- `self.config.printer_connected` -> `self.printer.printer_connected`
- `self.config.print_job` -> `self.printer.print_job`
- `self.config.canvas` -> `self.canvas_state.canvas`
- `self.config.label_sizes[self.config.device]` -> `self.immutable.label_sizes[self.printer.device]`
- `self.config.mm_to_pixels(x)` -> `mm_to_pixels(x, self.immutable.label_sizes[self.printer.device]["print_dpi"])`
- Pass `(immutable, printer)` to `PrinterOperation`

#### `NiimPrintX/ui/widget/StatusBar.py`
- **No changes needed.** Already receives data via `update_status(connection: bool)` calls. The `config` parameter in its constructor is stored but never accessed for any attribute. Can be removed in Phase 2 for cleanliness.

### Test files that may need updates

Any test that constructs `AppConfig()` or mocks it will need updating. During Phase 1 this is zero changes (delegation preserves the interface). During Phase 2, tests for individual widgets will need to construct the appropriate sub-objects.

---

## 7. Risk Assessment

### Thread Safety (HIGH priority)

**`printer_connected`** is the most dangerous attribute:
- **Written** from the asyncio thread (via `update_status` callback in `PrintOption._heartbeat_loop`)
- **Written** from the Tk thread (via `_update_device_status`, `CanvasSelector.update_device_label_size`)
- **Read** from both threads

Currently this is a plain `bool` attribute with no synchronization. Python's GIL makes individual attribute reads/writes atomic for simple types, so this works by accident. The refactor should **not** introduce any new thread-safety bugs since we're just moving the attribute to a different object — the access pattern remains identical.

**Future improvement (out of scope for this refactor):** Consider using `threading.Event` or a proper lock for `printer_connected` and `print_job`.

**`print_job`** has the same cross-thread pattern but is less dangerous (only toggled at print start/end with clear sequencing).

### Circular Dependencies (LOW risk)

The new classes have zero circular dependencies:
- `ImmutableConfig` depends on nothing
- `CanvasState` depends on nothing (stores tk objects but doesn't import the config classes)
- `PrinterState` depends on nothing
- `mm_to_pixels()` is a pure function with no dependencies

Widgets depend on 1-3 of these classes but never depend on each other through the config layer.

### Regression Risk (MEDIUM)

The biggest risk is **typos in attribute access paths** during Phase 2. Every `self.config.X` must be mapped to the right `self.{object}.X`. Mitigation:
- mypy / pyright will catch attribute errors on typed objects
- The existing 112 test suite covers most code paths
- Phase 1 delegation layer means we can fall back if Phase 2 breaks anything

### `mm_to_pixels()` Calling Complexity (LOW)

Currently: `self.config.mm_to_pixels(mm)` (1 arg, reads device internally)
After: `mm_to_pixels(mm, self.immutable.label_sizes[self.printer.device]["print_dpi"])` (verbose)

Mitigation: Add a convenience wrapper on `PrinterState`:
```python
def get_dpi(self, label_sizes: dict) -> int:
    return label_sizes[self.device]["print_dpi"]
```
Then callers become: `mm_to_pixels(mm, self.printer.get_dpi(self.immutable.label_sizes))`

Or create a helper that takes both objects:
```python
def mm_to_pixels_for_device(mm: float, immutable: ImmutableConfig, printer: PrinterState) -> int:
    dpi = immutable.label_sizes[printer.device]["print_dpi"]
    return round((mm / 25.4) * dpi)
```

---

## 8. Testing Strategy

### Phase 1 Tests

1. **Unit tests for new classes:**
   - `ImmutableConfig`: Verify all paths resolve, label_sizes structure is correct, user config merge works
   - `CanvasState`: Verify default values (None/empty)
   - `PrinterState`: Verify default values (False/None)
   - `mm_to_pixels()`: Test with known DPI values (203 DPI, 300 DPI)

2. **AppConfig delegation tests:**
   - Verify every property on `AppConfig` correctly delegates to sub-object
   - Verify setters work (e.g., `config.canvas = x` sets `config._canvas.canvas`)

3. **Existing test suite:** All 112 tests must pass unchanged

### Phase 2 Tests

For each migrated file:
1. Run existing tests that exercise that widget
2. Verify the widget can be constructed with the new parameter signature
3. Spot-check that attribute access works (e.g., `widget.canvas_state.canvas is not None`)

Key integration tests to run after each wave:
- File save/load round-trip (exercises FileMenu + CanvasState + PrinterState)
- Text add/select/move/resize/delete cycle (TextTab + TextOperation + CanvasOperation)
- Image add/select/move/resize/delete cycle (IconTab + ImageOperation + CanvasOperation)
- Printer connect/disconnect cycle (PrintOption + PrinterOperation + PrinterState)
- Canvas size change (CanvasSelector + all state clearing)

### Phase 3 Tests

- Full test suite pass
- Manual smoke test of the GUI: open app, add text, add image, change device, save/load file, print preview

---

## 9. Backwards Compatibility

### Incremental Approach (No Big-Bang)

The 3-phase design ensures the codebase is never broken between commits:

1. **Phase 1 is fully backwards-compatible.** Every consumer still uses `config.X` and it works through property delegation. This can be merged and deployed independently.

2. **Phase 2 can be done one file per commit.** Each file migration is self-contained:
   - Update the widget's constructor + internal references
   - Update the single caller that creates the widget (usually `main.py`)
   - All other files still work through the delegation layer

3. **Phase 3 is the only "breaking" change** and it's trivial by that point — just delete `AppConfig.py` and its imports.

### Branch Strategy

- Phase 1: Single PR, merges to main
- Phase 2: Could be one PR per wave (3 PRs) or one big PR. Per-wave is safer.
- Phase 3: Single small PR after all Phase 2 work is merged

### Rollback

At any point during Phase 2, if a file migration causes problems:
- Revert that one file's changes
- The delegation layer in AppConfig catches it
- No other files are affected

---

## 10. Estimated Effort

| Phase | Files Changed | Estimated Lines | Risk |
|---|---|---|---|
| Phase 1 | 2 (new config.py + refactored AppConfig.py) | ~120 new, ~50 modified | Low |
| Phase 2 Wave 1 | 4 files + main.py | ~80 modified | Low |
| Phase 2 Wave 2 | 2 files + main.py | ~40 modified | Low |
| Phase 2 Wave 3 | 4 files + main.py | ~200 modified | Medium |
| Phase 3 | 2 deleted, 1 modified | ~150 deleted | Low |
| **Total** | 13 files touched | ~440 lines changed | Medium overall |
