# NiimPrintX review — 2026-09-29

Local review, fixes, and verification are complete for this change set. The requested full fleet review remains incomplete because the M1 MCP transport closed. No release was made. The starting tracked/staged/untracked workspace was clean.

## Scope and evidence

Read `.stargazer-context.json`, the runtime source across BLE/protocol, CLI, canvas/editor, file handling, fonts, startup/shutdown, and the existing test/CI configuration. The context file is useful but stale in several places: custom CLI models and v2 library validation already exist, disconnect polling guards already exist, and Ruff selects explicit rule families rather than `ALL`. Those were not reimplemented.

Baseline: 367 passing tests, 91.09% coverage, clean Ruff lint. The ImageMagick runtime hook was the only file failing the repository-wide format check. The baseline also emitted an unawaited `_info` coroutine warning from a test mocking `asyncio.run`.

Final: **419 passing tests**, including **28 real GUI cases**, **91.07% configured coverage**, clean Ruff lint/format, clean configured mypy checks over 34 source files, and clean `git diff --check`. Added 52 cases across the focused GUI, printer, rotation, and resource regression modules.

The configured coverage denominator still excludes most GUI modules, and mypy still ignores UI errors. The coverage percentage must not be read as whole-app GUI coverage. The new GUI cases run real Tk widgets, Cairo export, Wand text, and Pillow rasters under Xvfb rather than relying solely on mocks.

Final review environment: Python 3.12.3; Pillow 12.3.0, Pycairo 1.26.0, Wand 0.6.13, Ruff 0.15.10, and mypy 1.20.0, matching the repository lock entries for these packages. Temporary environment: `/tmp/niimprintx-review-venv`.

## Confirmed findings addressed

| Priority | Trigger and former consequence | Change / evidence |
| --- | --- | --- |
| High | Connect to D110, select B21, then print: the old BLE client could receive a B21 v2 job. A heartbeat could also restore a stale connected flag. | `PrinterOperation` tracks the connected model, disconnects before replacing clients, and rejects stale-model heartbeat state. Regression tests verify which client receives the job. |
| High | Open a file with valid top-level metadata but a corrupt raster: the old canvas was cleared before item validation failed. JSON `null`/number roots could also raise uncaught type errors. | `FileMenu.load_from_file` validates object roots and prepares every image/text item before clearing the design; replacement asks for confirmation. Tests cover corrupt images, malformed roots/order, and declined replacement. |
| Medium | Add text: it was created at `(0, 0)` although the label begins at `(75, 75)` in the default layout. Newly added text could be absent from the print area. | `TextOperation.add_text_to_canvas` places new text inside the label, centering text that fits. Real Wand/Tk multiline test verifies its bounds. |
| Medium | Change rotation in the print dialog: only the transmitted raster rotated; the preview stayed unchanged. | `PrintOption.update_preview` renders the same clockwise rotation as the print payload. Pixel comparisons cover 0/90/180/270 degrees. |
| Medium | Configure rotation for a built-in printer: the setting was ignored. | `merge_label_sizes` permits validated built-in rotation overrides, preserving hardware DPI/density defaults. Tests cover supported, negative, invalid, and boolean values. README documents GUI versus explicit CLI rotation. |
| Medium | Export a 240×120 label: Tk's border-expanded `bbox` produced a 242×122 PNG. Odd label dimensions also lost a pixel from symmetric integer-halves. | Export uses rectangle coordinates; selector sets right/bottom from left/top plus exact dimensions. Tests verify 240×120 and odd 101×51 geometry. |
| Medium | Place an image above text on the canvas: PNG export always drew all images before all text, changing the visible layering. Saving/loading also lost mixed ordering. | Export follows `canvas.find_all()`; new `.niim` files store item order and validate it on load. Older files without order remain readable. Pixel tests cover both orders and file roundtrip. |
| Medium | Export when the canvas widget is smaller than the full label, or shift content toward an edge: content clipped to the widget, and padding could become transparent. | Render directly into a label-sized white surface. Positive horizontal/vertical offsets move content right/down. Tests verify visible content and opaque white padding. This corrects the former crop-based inverse offset behavior. |
| Medium | Import a JPEG with camera EXIF orientation: the displayed raster used the stored pixel orientation. | Import applies Pillow EXIF transpose before converting to RGBA. A real JPEG orientation test verifies swapped dimensions. |
| Medium | Import a very thin/tall image: integer scaling could yield zero width. Extreme resize gestures could distort aspect ratio or allocate enormous rasters. | Import guarantees dimensions of at least one pixel; resize limits both axes to 4096 while scaling from the original. Extreme-aspect regression passes. |
| Medium | Pass invalid quantity/density/offset types or oversized dimensions to the library: validation could occur after hardware setup had started. | `_print_job` validates these constraints before BLE commands. Tests assert no setup/write for invalid quantity and excessive width. |
| Medium | Polling commands respond slowly: retry counts and sleep intervals did not actually enforce the stated 10/60-second bounds. A negative final `end_print` acknowledgement was also ignored. | Polling uses total elapsed-time `asyncio.timeout` bounds; final acknowledgement rejection raises `PrinterException`. Deadline tests include time spent awaiting a command and check cleanup. |
| Medium | Image preparation or icon loading fails, or an icon frame is destroyed before completion: decoded images could remain open. | File preparation uses image contexts and explicit ownership cleanup; icon rasters close on aborted callback, destroyed frame, and PhotoImage conversion failure. Confirmed worker findings; tested destroyed-frame/callback cases. |
| Medium | Shutdown clears editor dictionaries on the asyncio thread: Tk PhotoImage destructors can run off the Tk thread. | Editor image/reference cleanup now runs in `on_close` on the Tk thread. Full-app startup/text/export/preview/shutdown smoke test completed. |
| Low | Non-frozen startup constructs the splash path from the wrong directory. | `resource_path` walks up to the containing package directory correctly; test checks the actual shipped splash image exists. |
| Low | A font cache contains valid JSON with a non-object structure: the cache could reach Tk callbacks as a list/null and break dropdown setup. | Invalid cache structures are treated as misses. Four regression cases cover malformed structures. |
| Low | Re-select the current device/label size, or change selection while printing: an unnecessary reset could clear the design or alter job state. | Same-value selection is a no-op; changes/open/disconnect are guarded during active printing. Tests cover selector identity and file-open guard. |
| Low | Saving more than 100 items produces a file the loader refuses, or loading a replacement counts old items against the incoming limit. | Save rejects an over-limit design before replacing an existing file; load counts only incoming items. Tests verify both. |

Additional cleanup: close intermediate palette-conversion and export rasters, cap text resize at the existing 500-point file limit, release rotated job images on scheduling/shutdown failure, keep connect-button text aligned with status, prevent duplicate preview windows, handle Tk shutdown `RuntimeError` in callbacks, reset completed text-debounce IDs, format the runtime hook, and mock `_info` directly to eliminate the test's leaked coroutine.

`Save Image` now saves the design PNG without opening a print-settings popup. Saved PNGs retain the editor orientation; print rotation is applied in the print dialog. A new `GUI regressions` CI job installs GUI extras/system libraries and runs the real GUI suite under Xvfb. The workflow YAML parsed locally; the GitHub job itself has not run for this uncommitted change.

## Fleet work actually performed

All selected boxes were unclaimed at selection time, then claimed for the wave. macbook4 was claimed by another session and was untouched. Models actually loaded: **Qwen3.8-27B-8bit**, fleet model `27b-38`, role `coder-38`, on macbook1, macbook2, and macbook3. Thinking was disabled as required for these dense models. Scheduling normalized this model to Symphony's `27b/coder` capability class and used one generation per box.

| Task | Box | Outcome |
| --- | --- | --- |
| `render-review`, attempt 1 | macbook1 | Rejected: empty reply, zero completion tokens. Read-only host logs show the idle reaper stopped the model at 19:19:12 EDT while its log was still recording prompt processing. |
| `protocol-review`, attempt 1 | macbook2 | Incomplete: MCP returned `Transport closed`; no response file available. |
| `workspace-review`, attempt 1 | macbook3 | Completed with 2,136 completion tokens; parsed through `taskctl result`. Accepted only independently confirmed resource-cleanup findings. |
| `render-review`, attempt 2 | macbook1 planned | Narrowed prompt prepared, but role-load call failed with `Transport closed`; this attempt was never dispatched. |

Worker inputs, baselines, and the completed/raw replies remain under ignored `.m1-orchestrator/`. Workers only read supplied excerpts and returned findings; every repository edit and verification command was performed by the coordinator. No worker patch was applied.

The workspace reviewer labelled a speculative Wand text-save problem “critical,” then repeatedly contradicted itself. Its assertion that `ImageTk.PhotoImage` subclasses `tk.PhotoImage` was also incorrect. The real Wand text save/load roundtrip passes; that claimed crash was **rejected**. Several other “findings” described already-correct code and were rejected. `AppConfig` remains as a compatibility wrapper because removal would affect public imports and its existing tests without fixing a user-visible bug.

MCP release calls also failed after transport closure. The server's automatic exit cleanup released the claims; read-only `ai-role claim --status` over SSH verified `claim: null` on macbook1–3.

## Verification commands

```bash
xvfb-run -a /tmp/niimprintx-review-venv/bin/python -m pytest tests/ -q --cov=NiimPrintX --cov-report=term-missing
/tmp/niimprintx-review-venv/bin/ruff check .
/tmp/niimprintx-review-venv/bin/ruff format --check .
/tmp/niimprintx-review-venv/bin/mypy NiimPrintX/
git diff --check
```

Also exercised the real `LabelPrinterApp` under Xvfb: load resources, add multiline text, export (240×120), open print preview (120×240 at the device rotation), change rotation, and shut down cleanly. No physical label was printed.

One baseline warning remains: the intentionally oversized CLI test image emits Pillow's `DecompressionBombWarning`. It does not fail the suite. The former unawaited-coroutine warning is gone.

## Remaining limitations and follow-up

- The original report of text being sideways is not reproduced on physical hardware. Preview/payload parity and ignored rotation overrides are fixed, but the correct rotation for a particular model, firmware, and feed direction still needs an actual label check.
- Two fleet review tasks remain outstanding; resume them in smaller bounded chunks after the M1 MCP connection is restored. Do not describe this as three completed Qwen reviews.
- BLE notification handling still assumes one complete notification per command and does not correlate unsolicited response types. Changing that safely needs protocol evidence, especially around fragmented/coalesced notifications and reconnection during row upload.
- The total status deadline is 60 seconds, matching the existing intended limit. Very large copy batches may need a quantity-aware timeout policy and hardware measurements.
- Linux GUI behavior was verified. macOS/Windows UI behavior, packaged executable startup, and PyInstaller release builds were not exercised.
- Text/icon workers still use Tk's cross-thread `after` bridge. Shutdown failures are handled more carefully, but a future larger UI refactor should use an explicit main-thread queue and centrally owned lifecycle.
- Old `.niim` files did not record mixed stacking order; that missing information cannot be recovered. New files retain it.

Reference checked for rotation/EXIF semantics: [Pillow Image API](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.rotate), [Pillow ImageOps API](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose). No third-party code was copied.
