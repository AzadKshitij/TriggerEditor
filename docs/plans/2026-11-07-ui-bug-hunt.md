# Third-pass UI bug hunt — 2026-11-07

Scope: user-visible front-end behaviour of the Qt desktop app (canvas, dock,
config widgets, table viewer, dialogs, QSS). Core data-processing math, the
CLI/headless path and the vendor `nodeeditor` package are out of scope unless
the app's own code drives them wrongly.

Method: parallel read-only subagent sweeps plus direct code verification. No
finding here appears in `docs/internal/bugs.md`,
`docs/plans/2026-10-31-trigger-designer-bug-hunt.md`,
`docs/plans/2026-11-01-node-evaluation-and-laziness.md` or
`docs/plans/2026-11-04-second-pass-bug-hunt.md`.

Verification note: the local `.venv` trampoline cannot spawn Python
(`uv trampoline failed to spawn Python child process`), so every item below is
confirmed by reading the call path, not by running the app. Each entry names
the exact lines that implement the fault.

## Summary

| # | Severity | Area | Symptom |
|---|---|---|---|
| 1 | High | MDI windows | Closing one unsaved document can prompt for, and save, a different one |
| 2 | Medium | Window menu | Document entries never switch windows |
| 3 | Medium | Canvas | Fit View breaks Ctrl+wheel zoom (nothing happens, then a jump) |
| 4 | Medium | Config Dock | A node selected before its data arrives stays on "No incoming data available" forever |
| 5 | Medium | Union node | Switching Mode to Manual shows no mapping grid until reselect |
| 6 | Medium | Rows node | Changing Field type takes several undo steps; one Ctrl+Z leaves mixed values |
| 7 | Medium | Join node | The output list's "None" toggle cannot clear the selection |
| 8 | Medium | Canvas | Changing an edge style is not undoable and does not mark the document modified |
| 9 | Low | Filter node | The Operation combo can display a fallback the model did not adopt |
| 10 | Low | Table viewer | A replaced frame keeps the old sort arrow and search text |
| 11 | Low | Rule cards | Expand state is indexed by position and is not shifted on remove/duplicate |
| 12 | Low | Logs dock | Toggling technical details does not relayout expanded rows |
| 13 | Low | Data Profile | Detail pane can show a different column than the selected row |
| 14 | Low | Formula editor | Bracketed names inside `--` comments are flagged as unknown columns |
| 15 | Low | Table viewer | Copying a non-rectangular cell selection compresses out the gaps between columns |

## 1. Closing an unsaved document can save the wrong document (High)

**Files:** `src/trigger_designer/qt/main_window.py:626-644`,
`src/trigger_designer/qt/design_window.py:792-807`

**Symptom:** With two or more untitled documents open, closing one can leave the
other selected, so the "save your changes?" prompt and the Save that follows
belong to a different document. If the wrong document is unmodified, the
modified one closes with no prompt at all and its work is lost.

**Root cause:** `onSubWndClose` activates the window found by
`findMdiChild(widget.filename)` before calling `maybeSave()`. Every unsaved
window has `filename is None`, and `findMdiChild(None)` returns the first
sub-window whose filename is also `None` - not necessarily the window being
closed. `maybeSave()` then asks `getCurrentNodeEditorWidget()`, which is now
the wrongly activated window.

**Fix:** Pass the closing widget to `maybeSave`, or activate the QMdiSubWindow
that owns `widget` directly (walk `mdiArea.subWindowList()` and compare
`window.widget() is widget`) instead of matching on a nullable filename.

## 2. Window menu document entries never switch windows (Medium)

**Files:** `src/trigger_designer/qt/helpers/main_window_ui_mixin.py:185-197`,
`src/trigger_designer/qt/main_window.py:118`

**Symptom:** The Window menu lists each open document, but choosing one does
nothing. Only the dock toggles and layout commands in that menu work.

**Root cause:** Each action is wired as
`action.triggered.connect(self.windowMapper.map)` and registered with
`setMapping(action, window)`, but `QSignalMapper.mapped` is never connected to
`QMdiArea.setActiveSubWindow`. `QSignalMapper.map()` emits `mapped`; with no
receiver the emission is dropped.

**Fix:** Connect once at construction:
`self.windowMapper.mapped.connect(self.mdiArea.setActiveSubWindow)` (or drop
the mapper and use a `lambda _=False, w=window: self.mdiArea.setActiveSubWindow(w)`).

## 3. Fit View corrupts the zoom step counter (Medium)

**Files:** `src/trigger_designer/qt/design_window.py:270-273`,
`.venv/Lib/site-packages/nodeeditor/node_graphics_view.py:831-864`

**Symptom:** After pressing Fit View, Ctrl+wheel (or the zoom buttons) either
does nothing for many steps or jumps by a large factor. It works normally only
after enough steps to bring the internal counter back into range.

**Root cause:** `fitView()` stores the transform scale and then writes it into
the view's *step counter*: `self.view.zoom = self._last_scale * 10`. `zoom` is
not a scale - it is an index in `[0, 10]` that `zoomIn`/`zoomOut` increment and
that `applyZoom` clamps. A fit scale of e.g. 1.8 writes `zoom = 18`; the next
zoom-out becomes 17, still clamped, so no scaling is applied until the counter
falls to 10.

**Fix:** Do not write `view.zoom` in `fitView`. The counter's neutral point is
10 (scale 1.0), so convert the fitted scale back into steps:

```python
steps = math.log(self._last_scale) / math.log(self.view.zoomInFactor)
self.view.zoom = min(
    self.view.zoomRange[1],
    max(self.view.zoomRange[0], 10 + steps),
)
```

`applyZoom` then only needs to gate on a counter that is in range and the next
wheel step multiplies the fitted transform correctly.

## 4. Config Dock sticks on "No incoming data available" (Medium)

**Files:** `src/trigger_designer/qt/docks/node_config.py:122-126`,
`src/trigger_designer/qt/helpers/shaping_support.py:513-516`,
`src/trigger_designer/qt/node_runtime.py:236-246`,
`src/trigger_designer/qt/design_window.py:772-787`

**Symptom:** Select a shaping node before its input is connected (or before its
data has computed) and the dock shows only "No incoming data available". When
the node later becomes ready, the dock stays empty. Clicking another node and
back is the only way to get the real controls.

**Root cause:** `ShapingContent.create_layout` adds `EmptyStateLabel()` and
returns when `ready()` is false. When evaluation later succeeds,
`node_runtime.succeed()` calls `_refresh_selected_node_config()`, which calls
`refreshConfigDock(...)` with `force=False`. `ConfigDock.updateConfig` then
returns at `if id(content) == self._current_key and not force`, so the empty
layout is never replaced.

**Fix:** Make `updateConfig` also rebuild when the node's `ready()` state has
changed since the layout was built (store the state alongside `_current_key`),
or pass `force=True` from `_refresh_selected_node_config` when the node just
transitioned from unready to ready.

## 5. Union Manual mode shows no mapping grid until reselect (Medium)

**Files:** `src/trigger_designer/qt/widgets/nodes/Join/union.py:515-524`,
`741-745`, `608-624`

**Symptom:** Change a Union node from "By name" to "Manual" and the Column
Mapping section never appears. The mode chip and counts update, but there is no
grid to map inputs. Deselect and reselect the node and it appears.

**Root cause:** `_on_mode_changed` pushes a rebuild, which reaches
`_refresh_mapping_section()`. That method returns immediately when
`self._mapping_section is None` - which is exactly the state after starting in
"By name", because the section is only built by `create_layout` when the mode
is already manual. The rebuild path therefore never constructs the section.

**Fix:** In `_refresh_mapping_section`, when the mode is manual and
`_mapping_section` is `None`, call `_build_mapping_section_at(self._mapping_index)`
instead of returning.

## 6. Rows Field type change takes several undo steps (Medium)

**Files:** `src/trigger_designer/qt/widgets/nodes/Preparation/dynamic_row_builder.py:271-287`,
`src/trigger_designer/qt/helpers/shaping_support.py:396-414`

**Symptom:** Change Field type in a Rows node, then press Ctrl+Z once. Only the
last recorded setting reverts (usually `field_type`), while the converted
initial/max/increment values stay in their new types. The node is now in a state
the user never chose, and undoing the whole switch takes several more presses.

**Root cause:** `_commit_type` calls `set_setting` once per converted value and
once for `field_type`; each call pushes its own `PropertyChangeCommand`. There
is no shared merge key or grouping command, so one user action becomes N+1
history entries.

**Fix:** Record the whole type switch as one command. A shared `merge_key` is
not enough: `PropertyChangeCommand._merge_target_check`
(`qt/undo/commands.py:205-213`) requires `self.path == other.path`, so commands
for `("settings", "initial_value")` and `("settings", "field_type")` never
fold together. Use one command over the whole dict:

```python
before = copy.deepcopy(self.settings)
self.settings.update(changes)
self.settings["field_type"] = value
self._mark_scene_modified()
self._update_visibility()
self.after_change()
self.refresh_dock_context()
self.push_property_change(
    ("settings",), before, copy.deepcopy(self.settings),
    "Rows Field type Changed",
)
```

`_sync_widgets_from_model` already rebuilds the value editors when the dtype
changes, so undo restores both the values and the control set in one step.

## 7. Join output "None" cannot clear the selection (Medium)

**File:** `src/trigger_designer/qt/widgets/nodes/Join/join.py:258-288`

**Symptom:** Click the bulk "None" toggle in a Join node's Output columns list
and every box immediately re-checks itself. The user cannot express "no output
columns", and the history records changes the list immediately contradicts.

**Root cause:** `_checked_labels()` treats an empty `selected_columns` as "all":
`if not selected: return [label for every output item]`. `_on_output_changed`
stores `[]` for "None", then the post-change sync rebuilds the checklist from
`_checked_labels()`, which turns `[]` back into every label. If the stored list
was already empty, `_on_output_changed` returns before storing anything, so the
model and the visible checklist disagree until the next sync.

**Fix:** Distinguish "never configured" (`None`) from "nothing selected" (`[]`)
in `_checked_labels`, or disable the "None" toggle when an empty selection is
not meaningful (the core join treats `[]` as all columns).

## 8. Edge style changes are outside undo and the modified flag (Medium)

**File:** `src/trigger_designer/qt/helpers/context_menu_mixin.py:337-355`

**Symptom:** Change an edge to Bezier/Direct/Square. The path updates, but
Ctrl+Z does not revert it, Undo history does not show it, and the document is
not marked modified. Close the document without another edit and the style
change is silently discarded.

**Root cause:** `handleEdgeContextMenu` assigns `selected_edge.edge_type`
directly. The vendor setter only recalculates the graphics path; it does not
call `scene.history.storeHistory(...)` or set `scene.has_been_modified`.
`edge_type` is serialized (see `node_edge.py:456`), so the change can persist,
but only if something else causes a save.

**Fix:** Wrap the assignment in a small undoable command (or
`scene.history.storeHistory("Changed Edge Style")` plus `scene.has_been_modified = True`)
so the style participates in undo and in the close prompt.

## 9. Filter Operation combo can display a fallback the model did not adopt (Low)

**File:** `src/trigger_designer/qt/widgets/nodes/Preparation/filter.py:263-275`

**Symptom:** Open a saved Filter whose operation is not valid for the current
column dtype (for example "Greater Than" on a string column). The combo shows
"Equals" because that is the first offered item, but the node still evaluates
"Greater Than" and fails with "Unsupported filter operation". The visible
setting and the behaviour disagree.

**Root cause:** `_fill_operation_combo` uses `findData(value)` and then
`setCurrentIndex(max(0, index))`; when the saved operation is absent it silently
selects index 0 without writing that fallback back to the model. `_commit_column`
does normalize the operation, but this sync path (including initial dock build)
does not.

**Fix:** When `findData` returns -1, write the fallback with
`set_setting("operation", operations[0], ...)` before/after selecting it, or
insert the saved operation with a "(unsupported)" label so the UI tells the
truth.

## 10. Replaced frames keep the old sort arrow and search text (Low)

**Files:** `src/trigger_designer/qt/models/polars_table_viewer.py:1023-1048`,
`1008-1021`, `1114-1121`

**Symptom:** Sort a table, then load another file into the File Input preview
(or let a search produce a new frame). The header still shows the old sort
arrow even though the model has reset its sort, and the search box still shows
the old query while the full frame is displayed.

**Root cause:** `PolarsTableViewer.set_dataframe` resets the model (which clears
`_sort_column`) and rebuilds the column filter, but it never clears the header's
sort indicator, never clears `search_input`, and never calls `clear_search`.
`apply_search` likewise calls `model.set_dataframe(filtered)`, which drops the
model's sort while leaving the arrow in place.

**Fix:** At the end of `set_dataframe`, reset the header to the model's state
(`setSortIndicator(-1, Qt.AscendingOrder)`) and, when the viewer owns the search
controls, re-run the current query against the new frame instead of leaving the
text pointing at rows the model no longer filters:

```python
if self.search_input is not None and self.search_input.text().strip():
    self.apply_search(self.search_input.text(), self.column_filter.currentText())
```

The Data Preview panel keeps its query outside the viewer and re-applies it on
`_on_preview_ready`, so this does not change its behaviour. `apply_search` and
`clear_search` should also reset the sort indicator, because both replace the
model's frame (and therefore its sort) directly.

## 11. Rule-card expand state is not reindexed (Low)

**Files:** `src/trigger_designer/qt/helpers/shaping_support.py:766-775`,
`855-867`, `919-927`

**Symptom:** With several formula/rule cards, remove one in the middle. Cards
below it inherit the expand state of the position, not of themselves: the card
that was expanded may collapse, and the first card after deleting card 0 is
collapsed although card 0 is expanded by default. Duplicating has the mirror
problem.

**Root cause:** `_expanded_cards[key]` is a set of integer positions, and the
toggle lambdas capture the position at build time. Remove only discards the
removed index (`discard(index)`) and never shifts indices greater than it;
duplicate inserts a card without shifting either. `_remove_card_at` also does
not rebuild the remaining cards, so their captured indices are stale.

**Fix:** Reindex the set on remove/duplicate
(`{i - 1 if i > index else i ...}` / `{i + 1 if i >= index else i ...}`) and
rebuild the card widgets (or rebind their toggles) so captured indices match the
new positions.

## 12. Technical-details toggle does not relayout expanded rows (Low)

**Files:** `src/trigger_designer/qt/docks/logging_dock.py:731-734`,
`239-240`, `262-271`

**Symptom:** Expand a problem row, then toggle "Show technical details". The
extra technical line is added to the delegate's `sizeHint`, but the row keeps
its old height, so the line is clipped or missing until the tree relayouts
(scroll far enough, resize, or collapse/expand).

**Root cause:** `_on_technical_toggled` calls `delegate.set_technical(...)` and
`tree.viewport().update()`. A repaint does not recompute row heights; the tree
caches item rectangles until a layout invalidation. The dock already emits
`layoutAboutToBeChanged`/`layoutChanged` for `set_expanded` but not here.

**Fix:** After `set_technical`, trigger the same layout invalidation
(`model.layoutAboutToBeChanged.emit()` / `layoutChanged.emit()`), or
`tree.scheduleDelayedItemsLayout()` / `doItemsLayout()`.

## 13. Profile detail can show a different column than the selected row (Low)

**File:** `src/trigger_designer/qt/widgets/profile_view.py:447-451`, `487-493`

**Symptom:** Type a filter in the profile search, then let a new profile arrive
(or press Refresh). The table selects the first *visible* row, but the detail
pane shows the first *source* column. When the filter hides that column, the
detail and the highlighted row describe different columns.

**Root cause:** `set_profile` does `self.table.selectRow(0)` followed by
`self._show_detail(profile.columns[0])`. With the proxy filter active, proxy row
0 maps to a different source row; the explicit `_show_detail(columns[0])`
overrides the detail that `_on_row_changed` correctly set from the selected
row.

**Fix:** After `selectRow(0)`, read the current proxy index and show the column
it maps to (`_on_row_changed` already has that logic), and only fall back to
`columns[0]` when no row is visible.

## 14. Bracketed names inside `--` comments are flagged as unknown (Low)

**File:** `src/trigger_designer/qt/widgets/sql_formula_editor.py:839-865`
(compare the correct helper at `821-829`)

**Symptom:** A formula containing a line comment such as
`-- keep rows where [status] is set` gets an "Unknown column 'status'"
diagnostic underline, even though the comment is not part of the query.

**Root cause:** `validate_column_references` masks string literals with
`mask_string_literals(text)` only. `--` comments (and `/* */` blocks) are not
masked, so the bracket regex sees identifiers inside comments. The same module
already has `_mask_strings_and_comments` for this exact purpose and uses it in
`validate_single_expression` but not here.

**Fix:** Use `_mask_strings_and_comments(text)` in
`validate_column_references`, and extend that helper to mask block comments if
the editor accepts them.

## 15. Copying a gapped selection collapses the columns (Low)

**File:** `src/trigger_designer/qt/models/polars_table_viewer.py:783-819`
(selection mode is `SelectItems` at `:672-674`)

**Symptom:** Ctrl+click two cells in the same row, say column A and column C,
then Copy. The clipboard gets `A<TAB>C`, not `A<TAB><TAB>C`, so pasting into a
spreadsheet shifts column C left by one. The gaps the user saw on screen are
gone from the text.

**Root cause:** `copy_selected_to_clipboard` collects only the selected column
indices per row and joins those with `\t`
(`row_text = "\t".join(row_data.get(col, "") for col in cols)`). It never spans
from the first to the last selected column, so unselected columns between them
contribute no empty field.

**Fix:** Per row, emit fields for every column in
`range(min(cols), max(cols) + 1)` (empty string when the cell was not
selected), preserving the visual layout instead of packing the selection.

## Not reported

- `except A, B:` was raised by several sweeps as a syntax error across dozens of
  files. It is valid Python 3.14 (PEP 758) and is not a bug.
- Dead `QLabel#JoinSource*` selectors in `base.qss` (the Join output list now
  uses `ColumnPicker`) are styling leftovers, not a user-visible defect.
- Vendor `nodeeditor` internals are reported only where the app's own code
  feeds them the wrong contract (item 3).
