# Agent rules — Trigger Designer

- Config Dock UI must follow `docs/DESIGN_SYSTEM.md` §§1–7.
- Reference: `src/trigger_designer/qt/widgets/nodes/Preparation/select.py:134-259`.
- Reuse `qt/widgets/common/config_widgets.py`: `IconButton`, `TextButton`,
  `ConfigSection`, `ColumnChecklist`, `NoWheelComboBox`, `EmptyStateLabel`.
  No per-node rewrites.
- Icon-first: icon-only buttons by default; text allowed only in dialogs and in
  the paired `All` / `None` bulk toggles (`TextButton`). Mandatory tooltip +
  accessibleName; no `QIcon.fromTheme` (blank on Windows — use
  `IconButton.themed` with `:/qss_icons` fallback); no inline `setStyleSheet`
  (use `objectName` + `resources/qt/themes/base.qss` / `qss/_style.scss`).
- Hover/pressed must be restated per `objectName`: a `#objectName` selector
  outranks `QPushButton:hover`. Use `{background_hover}`/`{background_pressed}`
  for those states — `{button_hover}` is ~invisible against `{button_bg}`.
  Keep a constant 1px base border so hover does not shift layout.
- Layout tokens: main `spacing 2, margins 5`; toolbar `H40 margins 0`;
  controls `H30`; icon buttons `30x30 / 12px`.
- Live-by-default with ~300ms debounce on text/search; history entries
  `"Noun Verbed"` and only on real diff.

## Undo/redo — `src/trigger_designer/qt/undo/`

The timeline is a Qt `QUndoStack` (`UndoController`), not a list of scene
snapshots. The old design capped history at 32 full-scene serializations, so a
few minutes of typing evicted real edits.

- **Model is the only truth.** Widgets are a projection of it. A command
  mutates the model, then calls `sync_from_model()`; it never writes widgets.
- **Model -> widget never re-records.** Every write-back runs inside
  `syncing(content)`, and bindings check `is_syncing(content)`. Skip this and a
  restore records the change it is restoring, so the user can never undo past
  it.
- **The Config Dock is the editor.** Selecting a node calls `create_layout()`;
  deselecting destroys the widgets. After a restore the same node is still
  selected, so `ConfigDock.updateConfig` *would* short-circuit on
  `_current_key` - `onHistoryRestored` passes `force=True` to bypass it. Do not
  remove that.

### Recording a change

Prefer the helpers on `TriggerContentUndoMixin` (inherited via
`TriggerChangeHandler`, so every node already has them):

| Helper | Use for |
|---|---|
| `self.push_property_change(path, old, new, text, merge_key=...)` | one setting: a dtype, a filter operation, a selected column |
| `self.push_list_change(path, old, new, text)` | a collection that changes *size*: formula sections, join mapping rows. Rebuilds widgets on restore. |
| `self.registerInputWidget(w, text=..., merge_key=...)` | a Config Dock control. Handles debounce, diffing and the restore guard. |
| `self.history.storeHistory(...)` | fallback. Serializes the whole scene; correct but heavy. Prefer the above. |

`path` is dotted on the **content** widget and may cross from an attribute into
dict keys: `("changes", "rename_mapping")` sets `content.changes["rename_mapping"]`.

`merge_key` collapses a *burst* into one undo step while keeping the original
`old` value, so undo returns to where the burst began. Use one key per control.
Only pass it for continuous typing - five separate "add section" clicks are five
steps, and `merge_key=None` (the default) is correct there.

### Widget resync

Override the hooks a node needs; both are optional and default to no-ops:

- `_sync_widgets_from_model()` - refresh values in place, preserving widget
  identity so a focused editor is not torn down.
- `_rebuild_widgets()` - recreate structure. Required when the change alters
  how many widgets exist (see `FormulaContent._rebuild_widgets`).

Do **not** add a new `history_stamp_callback`. That path is only for legacy
snapshot restores; new code goes through `sync_from_model`.

### Every dock control is tracked by default

`ConfigDock.updateConfig` calls `registerUnboundDockWidgets()` after
`create_layout`, so a control is undoable even if the node never registered
it. Nodes that had no explicit registration at all - cleansing, groupby,
count_records, graph, dynamic_row_builder - previously had no undo path.

Two traversal details that silently lose controls, both now handled by
`TriggerChangeHandler.iter_dock_widgets`:

- **Scroll areas.** A node that wraps its panel in a `QScrollArea` keeps its
  controls under `scrollArea.widget()`, which no dock layout can reach. Use
  `QScrollArea`, *not* `QAbstractScrollArea` - the `widget()` accessor only
  exists on the former, and `QTextEdit`/`QTableView` share the latter base.
- **Composites.** Mark a widget `_undo_composite = True` when it emits its own
  change signal (`ColumnChecklist`, `SQLFormulaWidget`). Controls nested
  inside one are skipped, or the composite and its children both record the
  same edit.

### Selection is UI state, not document state

A snapshot restore also replays the selection recorded in the stamp, and the
stamp being reverted *to* may predate the node being picked - so the scene can
end up with nothing selected. `onHistoryRestored` therefore falls back to
`ConfigDock.currentNode()` rather than blanking the panel, which otherwise
makes an undo look like it did nothing.

### Guards

- Use `with self.history.restoring(is_undo=is_undo):` - never assign
  `is_restoring_history` directly. The flag is a depth counter, and the old
  assign-True/finally-False form let a nested restore re-enable recording
  part-way through an outer one.
- Never let an exception escape `undo()`/`redo()`. `QUndoStack` calls them from
  C++; a raise there aborts the process instead of propagating. `UndoableEdit`
  provides `_guard` for this.
- Do not implement `mergeWith`. Qt `delete`s the command it merges away, which
  leaves a dangling wrapper under PyQt. `UndoController.push` folds commands via
  `can_merge_with`/`absorb` instead.

- Verify: `uv run --project . ruff format <files>` then
  `uv run --project . ruff check <files>` then focused `pytest`.
