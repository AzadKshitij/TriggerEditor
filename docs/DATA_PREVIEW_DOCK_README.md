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
- The surface is one 36px strip over the table. The collected frame is shown
  whole as a single page, so there is no paging footer and the table gets
  nearly all of the dock's height (9 rows at 340px, 16 at 520px on the sample
  file, where the old chrome left 1-3).

## The strip

| Element | Behaviour |
| --- | --- |
| Node chip | `PreviewNodeChip` over `PreviewNodeLabel`; names the node on screen, middle-elided with the full title in a tooltip. A dot (`PreviewPinDot`) marks a pinned preview. Hidden when nothing is followed |
| Socket chip | `PreviewSocketChip` over `PreviewSocketCombo`; shown only for nodes with more than one output. Changing it re-targets the preview (and a pin) to that socket |
| Search | `PreviewSearchEdit`, live with a 300ms debounce; `Ctrl+F` focuses it. The field is the truth: its text is re-applied whenever a new frame arrives, so switching nodes keeps the query |
| Scope | `PreviewScopeCombo`: `All Columns` or one column. Resets to `All Columns` when the chosen column is not in the new frame |
| Counts chip | `PreviewCountsChip` over `PreviewStatusLabel` and `PreviewLimitedBadge`: `shown / collected rows · N cols`, or `collected / total rows · N cols` when the collect was truncated; the tooltip explains the numbers, `counting...` shows while the lazy count runs, and `limited` marks a frame that hit a size cap |
| Pin | `PreviewPinButton` freezes the current node: selection changes stop moving the preview until it is unpinned |
| Refresh | Re-collects the shown node/socket; `Ctrl+R` inside the dock does the same. Disabled while a collect is in flight |
| Options | `OptionsButton`: `Copy as TSV` (header row plus every loaded row), `Export CSV...`, `Export Excel...`, then the dock's own `Open in standalone window` and `Unpin` |

The table is the shared `PolarsTableViewer` with every built-in control off
(`show_controls=False`, `show_info=False`), 24px rows and one-line
`name (dtype)` headers. The strip drives its filter through the viewer's
programmatic API (`search_columns()` / `apply_search()` / `clear_search()`),
so the dock never touches the viewer's own widgets.

## States

- Nothing selected: "Select a node to preview its output".
- Node without previewable output: "No previewable data on this socket" (the
  node chip still names the node).
- Collect in flight: "Loading...".
- Empty result: "No rows" (the counts chip still reports the columns).
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
- A frame that hits a cap is `limited`: the counts chip then names the
  collected rows and, once the count worker finishes, the total row count.
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
  design window closes, and the dock blanks and hides its node chip if that
  window was the one it followed.

## Standalone window

`Alt+click` a node's output socket opens the same panel in a standalone
`DataPreviewWindow` (the pre-existing behaviour). `Options > Open in standalone
window` does the same for the node currently shown in the dock. The standalone
host only calls `set_source()`: its node chip, socket chip and pin stay hidden.

## Design-window close now prompts

The close path was revived along with this dock, so:

- Closing a design window with unsaved changes asks to save first; `Cancel`
  keeps the window open.
- Closing the app asks per modified design window.
- A successful close drops that window's Logs and Data Preview state.

## Manual smoke checklist

With the app open on `savedfiles/Example_2_Retail_Ledger/app_workflow/1 - Copy.tds`
and `Window > Data Preview` shown:

- [ ] Click **Cleansing** once: the chip names it, the counts read
      `1,000 / 40,800 rows · 15 cols` with a `limited` badge, and the header
      band shows one-line `order_id (String)` labels.
- [ ] Resize the dock short and tall: the table keeps the space, there is no
      second scrollbar, and rows stay 24px.
- [ ] Type in the search field: rows narrow about 300ms after the last key,
      the counts switch to `N / 1,000 rows`, and clearing restores all rows.
- [ ] Pick one column in the scope combo: the same query matches only that
      column; selecting another node resets the scope to `All Columns`.
- [ ] Pin, then click another node: the chip keeps the pinned node and shows
      the dot. Unpin and the preview follows the new selection.
- [ ] `Ctrl+F` focuses the search, `Ctrl+R` re-collects, `Alt+click` on a
      socket opens the standalone window.
- [ ] `⋯ > Copy as TSV` and paste into a spreadsheet: header row plus the
      loaded rows.
- [ ] On a node with several outputs (a Join): the socket chip appears and
      switching sockets changes the frame.
- [ ] Deselect everything: the node and socket chips hide, the search
      disables, and the empty state returns.

## Files

- Dock: `src/trigger_designer/qt/docks/data_preview.py`
- Panel (strip, search, counts, states): `src/trigger_designer/qt/widgets/data_preview_panel.py`
- Collect logic: `src/trigger_designer/qt/models/preview_sampling.py`
- Workers / request controller: `src/trigger_designer/qt/models/preview_worker.py`
- Table: `src/trigger_designer/qt/models/polars_table_viewer.py`
- Visibility flag: `src/trigger_designer/qt/helpers/preview_dock_state.py`
- Wiring: `qt/main_window.py`, `qt/helpers/main_window_ui_mixin.py`,
  `qt/design_window.py`, `qt/node_base.py`, `qt/performance_scene.py`
- Theme hooks: `resources/qt/themes/base.qss`, `qss/_style.scss`

## Tests

`tests/unit/test_data_preview_dock.py` (dock behaviour),
`test_data_preview_panel.py` (strip, states, search, counts),
`test_preview_worker.py` (controller id/staleness rules, worker lifecycle),
`test_preview_sampling.py` (bounded collect),
`test_data_preview_wiring.py` (main-window wiring, menu, persisted flag) and
`test_polars_table_viewer.py` (the underlying table, headers, search API).
