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
- Verify: `uv run --project . ruff format <files>` then
  `uv run --project . ruff check <files>` then focused `pytest`.
