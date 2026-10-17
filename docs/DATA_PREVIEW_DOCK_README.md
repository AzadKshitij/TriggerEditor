# Data Preview Dock

A shared, selection-driven preview of a node's output. The dock lives in the
bottom area of the main window, tabified behind the Logs dock, and follows the
active design window.

## Overview

- One dock for every design window, like the Logging Dock: switching windows
  switches context, and each window keeps its own pin and socket choice.
- The preview follows the Config Dock's node; with no Config Dock selection it
  falls back to the first selected logic node in the scene.
- Data comes from the node's evaluated `value`, or from the run results
  (`execution_results`) when a Run produced them.
- Collects are bounded (1000 rows / 2 MB) and run off the GUI thread, so a
  preview never freezes a design window.

## Feature guide

| Element | Behaviour |
| --- | --- |
| Title | `Data Preview - <design window title>`; plain `Data Preview` when no window is followed |
| Output socket combo | Shown only for nodes with more than one output; changing it re-targets the preview (and a pin) to that socket |
| Pin | Freezes the current node (`PreviewPinButton`); selection changes stop moving the preview until it is unpinned |
| Refresh | Re-collects the shown node/socket; `Ctrl+R` inside the dock does the same. Disabled while a collect is in flight |
| Options | `Export CSV...`, `Export Excel...`, `Open in standalone window`, `Unpin` (`OptionsButton`, icon-only) |
| Info line | `N rows collected - T total - C columns`; the total appears when the collect was truncated and the lazy count finished |
| Footer | First / previous / next / last page over the loaded frame, a page-size combo (100 / 250 / 500 / 1000) and `Rows a-b of n` |

The table itself is the shared `PolarsTableViewer`: sortable headers, in-frame
search, and theme colours.

## States

- Nothing selected: "Select a node to preview its output".
- Node without previewable output: "No previewable data on this socket".
- Collect in flight: "Loading...".
- Empty result: "No rows".
- Collect failed: "Preview failed: <reason>".
- Pinned node deleted from the canvas: the pin is released and the dock says
  "Pinned node is no longer in the scene".

## Where the data comes from

Payload resolution, in order:

1. `node.value[index]`, when it is the `{"data", "variable_name"}` envelope for
   the chosen output socket. `is_previewable()` in
   `qt/models/preview_sampling.py` is the single validity rule, and a value it
   rejects counts as "no output" rather than a collect failure.
2. `window.getSocketData(node, index)` when a Run stored results - a run writes
   `execution_results`, not `node.value`.

## Bounded collect semantics

- Every collect is capped at 1000 rows and 2 MB
  (`preview_sampling.collect_preview`).
- A frame that hits a cap is `limited`: the info line then names the collected
  rows and, once the count worker finishes, the total row count.
- Counting runs on its own thread and only for truncated lazy collects. A failed
  count is not an error - the total is simply left out.
- One collect runs at a time; the newest request wins, superseded results are
  dropped by request id, and only the newest pending payload waits behind the
  running one. A running Polars scan cannot be cancelled - the contract is
  drop-on-stale, never block the GUI.
- A hidden dock does not keep collecting: requests only come from selection,
  evaluation, Run and refresh.

## Persistence and shortcuts

- The dock is hidden on first launch. `Window > Data Preview` toggles it and
  `Ctrl+Shift+D` is the shortcut.
- Visibility (only) is remembered across restarts through
  `QSettings("Blue Octa", "Trigger Designer")`, key
  `data_preview_dock/visible` (`qt/helpers/preview_dock_state.py`). Tab order,
  floating state and geometry are not restored.
- Per-window state (pin, socket, shown node, loaded payload) is dropped when the
  design window closes, and the dock blanks and resets its title if that window
  was the one it followed.

## Standalone window

`Alt+click` a node's output socket opens the same panel in a standalone
`DataPreviewWindow` (the pre-existing behaviour). `Options > Open in standalone
window` does the same for the node currently shown in the dock.

## Design-window close now prompts

The close path was revived along with this dock, so:

- Closing a design window with unsaved changes asks to save first; `Cancel`
  keeps the window open.
- Closing the app asks per modified design window.
- A successful close drops that window's Logs and Data Preview state.

## Files

- Dock: `src/trigger_designer/qt/docks/data_preview.py`
- Panel: `src/trigger_designer/qt/widgets/data_preview_panel.py`
- Collect logic: `src/trigger_designer/qt/models/preview_sampling.py`
- Workers / request controller: `src/trigger_designer/qt/models/preview_worker.py`
- Visibility flag: `src/trigger_designer/qt/helpers/preview_dock_state.py`
- Wiring: `qt/main_window.py`, `qt/helpers/main_window_ui_mixin.py`,
  `qt/design_window.py`, `qt/node_base.py`, `qt/performance_scene.py`
- Theme hooks: `resources/qt/themes/base.qss`, `qss/_style.scss`

## Tests

`tests/unit/test_data_preview_dock.py` (dock behaviour),
`test_data_preview_panel.py` (panel states and paging),
`test_preview_worker.py` (controller id/staleness rules, worker lifecycle),
`test_preview_sampling.py` (bounded collect),
`test_data_preview_wiring.py` (main-window wiring, menu, persisted flag) and
`test_polars_table_viewer.py` (the underlying table).
