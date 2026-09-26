# Trigger Designer — Design System (Config Dock)

> Source of truth for consistent Config Dock UI/UX.
> Reference implementation: `src/trigger_designer/qt/widgets/nodes/Preparation/select.py:134-259` (Select tool).
> Status: Select is inspiration, not mandate. Two patterns allowed (§2).

## 0. Principles

1. Dense over spacious. One row does the work of three.
2. Live over Apply. Evaluate on change, debounce heavy ops (§6).
3. Icons over text for all repeated actions (§4).
4. No inline QSS. `objectName` + `resources/qt/themes/base.qss` only.
5. Reuse `widgets/common/config_widgets.py` before inventing widgets.

## 1. Layout tokens

| Token | Value | Notes |
|---|---|---|
| Dock min width | `300` | set in `qt/docks/node_config.py:21` |
| Main `QVBoxLayout` | `spacing 2, margins 5,5,5,5` | ref `transpose.py:77`, `cleansing.py:173` |
| Toolbar `QWidget + QHBoxLayout` | `fixedHeight 40, margins 0,0,0,0` | ref `select.py:158-161` |
| Control height | `30` min (`QLineEdit`, `QPushButton`, `QComboBox`) | ref `select.py:168,175,205` |
| Icon button | `30x30`, icon `12x12` (`16x16` max for primary) | ref `select.py:172-180` |
| Checkbox col width | `50` (`header.resizeSection(0, 50)`) | ref `select.py:249` |
| Scroll threshold | `ColumnChecklist max_height 150-220` | ref `config_widgets.py:71`, `cleansing.py:173` |
| End layout | `addStretch()` last, never empty `HBox` after stretch | `filter.py:104` violates this |

Docks must `dock_layout.addWidget(toolbar)` then `dock_layout.addWidget(view, 1)` — stretch factor `1` on the main view. No `dock.setContentsMargins(0,0,0,0)` (see `file_output.py:71` violation).

## 2. Two allowed patterns

### A. Toolbar + Table (Select, preferred for column/row lists)

```
QVBoxLayout (dock_layout)
├─ QWidget toolbar [fixedH 40, QHBox margins 0]
│   ├─ QLineEdit search ("Search columns...", clear button, minH 30)
│   ├─ IconButton up / down
│   └─ IconButton options (menu)
└─ QTableView [stretch 1] via QSortFilterProxyModel
    ├─ CaseInsensitive, FilterKeyColumn -1
    ├─ ExtendedSelection + SelectRows
    └─ ComboBoxDelegate for dtype col (single-click edit)
```

Use for: Select, GroupBy, Join mappings, Unique lists.
Do not use `ConfigSection` here — toolbar is the section.

### B. Form stack (for06111353 settings)

```
QVBoxLayout [spacing 2, margins 5]
├─ ConfigSection("Title", info="one-line hint") [spacing 2, no overrides]
│   ├─ NoWheelComboBox / QLineEdit / QSpinBox
│   └─ ColumnChecklist(columns, checked)
└─ addStretch()
```

Use for: Filter, Sort, Split, Transpose, Formula sections, File In/Out.
Reference: `transpose.py:77`, `running_total.py:99`. Never raw `QComboBox` (wheel-steal bug) — use `NoWheelComboBox`.

## 3. Shared widgets (must reuse)

Import from `qt/widgets/common/__init__.py`:

- `EmptyStateLabel` — only empty state. Centered gray, default text `"No incoming data available"`. Gate at top of `create_layout`: `if incom_data is None: dock.addWidget(EmptyStateLabel()); return`.
- `ConfigSection(title, info)` — `QGroupBox#ConfigSection` + `QLabel#ConfigSectionInfo` (wordWrap). Never `layout().setSpacing(10)` / `setMargins(15)` — see `unique.py:87` violation.
- `ColumnChecklist(columns, checked, max_height)` — scrollable checkboxes, `changed(list)` signal. Never hand-rolled `QListWidget` checkboxes (`unique.py`, `join.py` violations).
- `NoWheelComboBox` — drops wheel events unless popup open. Use everywhere a combo sits in a scrollable dock.

Table helpers: `SelectTableWidget`, `RowData`, `ComboBoxDelegate` in `qt/widgets/select_table_widget.py` — reuse delegate painting (`QStyleOptionComboBox`) for any dtype/option column.

## 4. Icon-first buttons (mandatory)

Rule: icon-only `QPushButton()` + `setIcon` + `setToolTip` + `setAccessibleName`. No `setText` except dialogs (§4.3).

### 4.1 Sizes

```python
btn = QPushButton()
btn.setIcon(QIcon(rsm.get("icon_add")))  # never QIcon.fromTheme on Windows
btn.setIconSize(QSize(12, 12))
btn.setFixedSize(QSize(30, 30))
btn.setToolTip("Add mapping")  # mandatory
btn.setAccessibleName("Add mapping")  # mandatory, screen reader
btn.setObjectName("IconButton")
```

### 4.2 Action → icon map

| Action | `resources.json` id (add if missing) | Fallback `:/qss_icons/dark/rc/` |
|---|---|---|
| Move up / down | `icon_move_up` / `icon_move_down` — ADD (replaces `fromTheme go-up/go-down`, blank on Windows) | `arrow_up.png` / `arrow_down.png` |
| Add / Remove | `icon_add` / `icon_remove` — EXISTS | — |
| Options menu | `icon_options` — ADD (sliders/gear) | `arrow_down.png` (current `select.py:189`, keep arrow only as menu indicator, drop `"Options"` text) |
| Check all / Uncheck all | `icon_check_all` / `icon_uncheck_all` — ADD | — |
| Apply / Evaluate / Run | `icon_apply` (check/play) — ADD | `media-playback-start` theme equivalent |
| Load / Save file | `icon_folder_open` / `icon_save` — ADD | — |
| Refresh / Clear filter | `icon_refresh` / `icon_clear` — ADD | — |
| Export CSV / Excel | `icon_export` — ADD (one icon, menu picks format) | — |
| Open in window | `icon_external` — ADD | — |

Until ids are added, use `QIcon(":/qss_icons/dark/rc/<name>.png")` directly — never `fromTheme`.

### 4.3 Exceptions (text allowed)

- `QDialogButtonBox` / `QMessageBox`: `Save / Cancel / Close` text stays (`settings_panel.py:79`, `about.py:164`).
- Destructive confirmations keep text.
- **Paired bulk toggles** use `TextButton` with the labels `All` / `None`. Two near-identical
  checkbox glyphs cannot be told apart at a glance, so these keep their words.
  Used in `Preparation/cleansing.py` and `Preparation/unique.py`.
  `TextButton` is `H30`, `objectName="TextButton"`, and inherits the same
  hover/pressed treatment as `IconButton` (see §4.5).
- Nothing else. These stay icons: `join.py` bulk L/R actions (folded into the
  Options menu), `Evaluate`, `groupby.py` Add/Remove/Apply, `formula.py` add/remove,
  `file_input.py`/`file_output.py` browse, `graph.py` open-in-window.

### 4.4 Bulk toggles

No `All / None` *icon* rows. Either fold them into the toolbar `Options` `QMenu`
(Join's four L/R actions) or use the `All` / `None` `TextButton` pair when the
action pair is genuinely ambiguous.

### 4.5 Hover / pressed states are mandatory

Qt gives an `objectName` selector (`QPushButton#IconButton`) higher specificity
than a pseudo-state (`QPushButton:hover`). Any widget that sets its own
`background-color`/`border` via `objectName` **must restate** `:hover`,
`:pressed` and `:disabled`, or hover silently does nothing.

- Base `QPushButton` / `QToolButton` use a constant `1px solid {button_bg}` border
  so recolouring the border on hover does not shift the button by a pixel.
- Hover fill is `{background_hover}` (a real contrast step). Do **not** use
  `{button_hover}` for hover: in the shipped themes it is within 1–2 RGB points
  of `{button_bg}`, so the state is invisible.
- Restated for `#IconButton`, `#OptionsButton`, `#TextButton`.
- A button that carries its own glyph **and** has a `QMenu` must suppress the
  menu indicator, otherwise Qt stacks a second down arrow next to the icon:

  ```css
  QPushButton#OptionsButton::menu-indicator {{
    width: 0px; height: 0px; border: none; image: none;
    subcontrol-origin: padding; subcontrol-position: center; }}
  ```

  Do not achieve this with inline `setStyleSheet`, and do not use
  `setLayoutDirection(Qt.RightToLeft)` as a substitute — it moves the glyph
  instead of removing the arrow.

## 5. Empty / loading / error

- No data: `EmptyStateLabel()` only. Delete custom variants (`count_records.py:61` italic label, `file_input.py` `_hide_all_options`).
- Join/Append need both inputs: `if left is None or right is None: EmptyState` (fix `join.py` `and`-logic, `Append.py:74` inverted gate).
- Never connect signals outside the `if data is not None` branch (fix `filter.py:104` crash).
- Node errors surface via `grNode.setToolTip(...)`, not red inline labels (fix `sort.py:94`).
- Loading spinners / error cards: not specced yet — use `EmptyStateLabel("Loading…")` as placeholder, do not invent.

## 6. Interaction: live-by-default

Every `setData / move / check / sort` → `data_processed → handleDataChanged → process_data_changes + apply_changes + evaluate.emit`, as in `select.py:255`, `groupby` equivalent.

- Debounce: `300ms` for text search / rename edits; immediate for check/move/combo.
- Heavy nodes (Join, GroupBy, Formula) still live — debounce, don't add Apply buttons. `groupby.py:278` Apply and `join.py:197` Evaluate are migration targets, not patterns.
- History: store diff only (`old != new`), verb format `"Noun Verbed"` e.g. `"Column Selection/Rename/Type Changed"`.
- Dock preservation: `ConfigDock.updateConfig` (`node_config.py:30`) skips wipe when `id(content) == _current_key`, suspends `_suspend_input_tracking/_suspend_node_evaluation` during `create_layout`. Do not rebuild widgets on every keystroke.

## 7. QSS / theming

- Zero inline `setStyleSheet` in node files.
- Required objectNames: `ConfigSection`, `ConfigSectionInfo`, `EmptyStateLabel`,
  `ColumnChecklist`, `IconButton`, `OptionsButton`, `TextButton`, `DataTypeCombo`,
  `JoinSourceLeft`/`JoinSourceRight`, `JoinSourceHeaderLeft`/`Right`, `JoinDtypeLabel`.
  Hooks live in `resources/qt/themes/base.qss` (runtime) and `qss/_style.scss` (source).
- `base.qss` is a `str.format` template: only keys present in
  `resources/qt/themes/*.json` may be used. Available: `background_hover`,
  `background_pressed`, `button_bg`, `accent_primary`/`_secondary`, `card_border`,
  `editor_background`, `error_text`, `text_primary`/`secondary`/`inactive`/`disabled`.
  A missing key raises at startup, so verify after editing.
- Same rule in `_style.scss`, using the `$COLOR_*` names from `_variable.scss`:
  `$COLOR_BACKGROUND_1..6`, `$COLOR_TEXT_1..4`, `$COLOR_DISABLED`,
  `$COLOR_ACCENT_1..4`, `$SIZE_BORDER_RADIUS`, `$BORDER_1..3`.
- Never hand-edit generated QSS in one place only; keep `base.qss` and
  `_style.scss` in agreement.

### Custom view delegates

Never hand a bare `QStyleOptionComboBox` to `drawComplexControl` — with no
`palette` set, Qt falls back to the application default (light grey in Fusion)
and the cell clashes with the themed surface. `ComboBoxDelegate.paint` in
`select_table_widget.py` therefore paints from `option.palette`/`option.font`
directly. If you add a delegate, copy the palette and font, and keep
`setAutoFillBackground(True)` off editors that have a themed `objectName`.

## 8. Anti-patterns (do not copy)

1. Inline QSS per button (`groupby.py:219`, `select.py:191`).
2. `QIcon.fromTheme` on Windows — invisible icons.
3. Text `All/None` rows (`join.py:162`, `cleansing.py:198`).
4. Custom spacing `10/15` on sections (`unique.py:87`, `split.py:92`).
5. Raw `QComboBox` in docks, raw `QListWidget` checkboxes.
6. Signals connected when data is `None` (`filter.py`).
7. `dock.setContentsMargins(0,0,0,0)` wiping dock padding (`file_output.py:71`).
8. Stub nodes with no `create_layout` (`union.py`, `find_replace.py`) — add `EmptyStateLabel` gate at minimum.

## 9. Migration checklist

- [ ] Add `IconButton` to `widgets/common/config_widgets.py` + export; add missing ids to `qt/resources.json`.
- [ ] `select.py`: drop `"Options"` text → `icon_options`, swap `fromTheme go-up/go-down` → bundled arrows.
- [ ] `join.py`: icon-ify All/None→Options menu, Evaluate→apply icon, `QListWidget`→`ColumnChecklist`, fix empty gate to `or`.
- [ ] `groupby.py`: kill blue-pill QSS, Add/Remove/Apply→icons, bold labels→`ConfigSectionInfo`.
- [ ] `formula.py`: `+ Add formula`→icon, remove→`icon_remove` (already ok), adopt `NoWheelComboBox` (already only adopter — propagate).
- [ ] `filter/sort/split/unique/cleansing`: adopt Pattern B tokens, `NoWheelComboBox`, fix `filter.py` signal crash, `unique.py` spacing.
- [ ] `file_input/output`: Load/Save→icons, remove `setContentsMargins(0)`, add `EmptyStateLabel` path.
- [ ] `graph.py`, `count_records.py`, `union.py`, `find_replace.py`: add empty gates + sections.
- [ ] Move all inline QSS to `base.qss` + `_style.scss`.

## 10. References

- Select dock: `src/trigger_designer/qt/widgets/nodes/Preparation/select.py:134-280`
- Table model/delegate: `src/trigger_designer/qt/widgets/select_table_widget.py:36-771`
- Dock host: `src/trigger_designer/qt/docks/node_config.py:10-129`
- Shared widgets: `src/trigger_designer/qt/widgets/common/config_widgets.py:1-139`
- Good Form-stack refs: `Transform/transpose.py:77`, `Transform/running_total.py:99`
- Theme hooks: `src/trigger_designer/resources/qt/themes/base.qss:1721,1725`, `src/trigger_designer/qss/_style.scss`
- Icons: `src/trigger_designer/qt/resources.json:98-105`
