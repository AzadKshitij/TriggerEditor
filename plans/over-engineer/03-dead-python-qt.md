# 03 — Dead Python in qt/ (excluding nodes/)

Paths relative to `src/trigger_designer/qt/`. Evidence method: `git grep -w -- <name> -- src tests scripts`; signals/connect targets and `rsm.__getattr__` checked by the auditor. Re-run the grep before each deletion.

## Batch A — whole files with 0 importers (~420 lines) — risk none

1. `delete:` `helpers/file_opener.py` (154). Imports `tagstudio...` and `structlog`, neither a dependency, so it cannot import. If ever needed: `QDesktopServices.openUrl(QUrl.fromLocalFile(p))`.
2. `delete:` `flowlayout.py` (156). Only self-references.
3. `delete:` `models/settings_panel.py` (20, deprecated re-export of PreferencesDialog), `models/model_file_dialogue.py` (13, uses `QFileDialog.Options()` which does not exist in PyQt6/PySide6), `widgets/clickable_label.py` (20), `tr_qt.py` (0 bytes), `translations.py` (0 bytes). `trigger.spec:166` matches a `/translations/` `.qm` path, not these files.

## Batch B — select_table_widget legacy cluster (~330 lines) — risk medium-low

`widgets/select_table_widget.py` (`SelectTableWidget(QAbstractTableModel)`): QTableWidget-era code, lines ~221-380, 447-480, 549-600, 654-668, 785-789. Methods: `swapRows, setupOptionsMenu, setupConnections, populateTable, onDataChanged, toggleRowSelection, get_renamed_columns, sortColumns, onSelectAllChanged, filterRows, moveRow, onColumnMoved`. `setupConnections`/`populateTable` dereference `self.table`, which a model does not have (`:308-318`), so they could never run; remaining callers are inside the cluster. Also drop ~147 commented-out lines and signals `data_processed`, `selectionChanged`, `moveRowRequested` if grep shows no emitters/connectors.
Live API to keep: `DATA_TYPES`, ctor, `moveSelectedRow` (+`_move_data`, `_restore_move_selection`), `checkSelected`, `uncheckSelected`, `set_all_checked`, `getData`, `rows`, `set_rows`, `update_from_changes`.
Steps: delete one method at a time, run after each. Tests: `tests/ui/test_select_move_rows.py`, `tests/ui/test_select_bulk_ops.py`, `tests/ui/test_select_*`.

## Batch C — design_window dead block (~75 lines) — risk low

`design_window.py`: `test_execution_visuals`, `_process_next_node`, `_test_executed_state`, `_transition_to_executed`, `_test_cleanup` (~845-897, animation demo, 0 callers), `getNodeConnections` (~812-835), deprecated `topologicalSort` wrapper (callers only `tests/unit/test_graph_ordering.py:69,81`; retarget the two assertions at `tests/unit/test_graph_ordering.py:69,81` to `nodeeditor.node_graph.topological_order`, or drop them if they only test the library; decide when editing and say which in the commit), `onDragEnter` (~730-735), `logTrace` (661-663), `logCritical` (681-683; only a manual demo). Verify `_load_with_dialog` and `cancel_pending_config_edits` (1 mention each) before cutting. Keep `logDebug/Info/Warning/Error` (called).
Tests: `tests/unit/test_graph_ordering.py`.

## Batch D — small dead surfaces (~230 lines) — risk low

- `widgets/common/config_widgets.py`: `set_status` (265-278), `add_header_action` (433-448), `full_text` property (824-825). `widgets/common/column_picker.py`: `set_selected_quiet` (742-746), `_set_all` (847-852). Tests: `tests/ui/test_column_picker.py`, `tests/ui/test_config_widgets*.py`.
- `widgets/polars_table_viewer.py`: `get_selected_data` (1219-1239), `get_table_view` (1249-1256). Verify chunk helpers (`_get_chunk_key/_load_chunk/_cache_cleanup`, 271-338) still have a live path before touching. Tests: `tests/ui/test_polars_table_viewer.py`, `tests/unit/test_polars_table_model.py`.
- Misc 0-caller methods: `helpers/context_menu_mixin.py` `determine_target_socket_of_node` (359-367), `finish_new_node_state` (369-372); `node_base.py` `getSocketValue` (766-781), `evalOperation` (938-939); `performance_scene.py` `getGraphicsEdgeClass` override (80-81, confirm it only calls super); `helpers/shaping_support.py` `flush_pending` (690-697, **check first**: 04 finding 8 may want to promote it to `ConfigContent`, in which case keep); `node_searchable_menu.py` `filterNodes` (149-152) and duplicate `_filter_nodes` (63-67); `theme_icons.py` `themed_icon` (224-231).
- Test-only hooks with 0 callers even in tests: `preferences.reset_preferences_instance` (275-278), `theme_manager.reset_theme_manager_instance` (780-782), `node_editor_colors.default_node_editor_colors` (41-45).
- `layout_state.py`: `clear_session` (215-217), `open_files`/`active_file` properties (182-201). **Keep** `_restore_legacy_geometry` and `_restore_preview_fallback` (user-data migration). Tests: `tests/unit/test_layout_state*.py`.

## Batch E — undo package unused surface (~45 lines) — risk low-medium

Respects AGENTS.md design; only zero-caller pieces.
- `undo/protocol.py:29-36` `SyncableContent` Protocol (0 refs); inline `get_sync_depth` (39-44) into `is_syncing` and `_is_restoring` (single callers).
- `undo/history.py:54-70` `history_stack`, `baseline_stamp`, `history_current_step` (0 callers, "kept for compatibility").
- `TriggerSceneHistory.macro` (174-175) and `UndoController.begin_macro/end_macro/macro/in_macro` (151-187): no caller (`git grep "\.macro(\|begin_macro\|in_macro"`). YAGNI until a multi-step command exists; `QUndoStack.beginMacro` is native.
- **Keep:** `push_edit` (used by `tests/e2e/test_undo_integration.py:160,205,246,294`), `history_stamp_callback` (nodeeditor snapshot restore calls it), the passthroughs on `TriggerSceneHistory` (nodeeditor API), `get_in` in `commands.py`.
Never let an exception escape `undo()`/`redo()` (AGENTS.md): keep the `_guard` wrapper intact when editing `controller.py`.
Tests: `tests/e2e/test_undo_integration.py`, `tests/unit/test_undo*.py`.

## Batch F — main.py logging sink (60-80 lines) — risk medium, verify first

`main.py:25-148`: `_strip_ansi_escape_sequences`, isatty shim, `_LogFileSink`, `_log_dir`, `_configure_logging` hand-roll a rotating file sink; loguru offers `logger.add(path, rotation=..., retention=..., colorize=False)`. Check redaction/ANSI-strip behaviour and `crash_capture` integration first. Tests: `tests/unit/test_crash_capture.py` and any `_LogFileSink` test. Do only if behaviour is provably identical.
