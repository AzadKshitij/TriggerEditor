# Signal — Trigger Designer Design System

> Source of truth for the application UI.
> Visual reference: [`design_system_preview.html`](design_system_preview.html) — self-contained, no network required.
> Config Dock contract: **§§1–7** (the sections `AGENTS.md` points at).
> Reference implementations: the Data Preview strip (`qt/widgets/data_preview_panel.py`) and the Select tool (`qt/widgets/nodes/Preparation/select.py:134-259`).
> Status: Signal 1.0 is the target contract. The Preview strip is the reference implementation; tokens and states marked **target** below are not in `base.qss` yet. The migration order is in §19.

---

## 0. Foundations

### 0.1 Principles

1. **Dense over spacious.** One row does the work of three. A panel earns its air; a control does not.
2. **Live over Apply.** Evaluate on change. Debounce heavy text work (§6); never add an Apply button to avoid wiring a signal.
3. **Icons over text.** Every repeated action is an icon-only `IconButton`. Text survives only in dialogs and the paired `All` / `None` toggles.
4. **One chrome strip.** Identity left, search flexible, counts before actions. No second toolbar, no footer repeating the strip.
5. **Semantic tokens over hex.** A widget asks for `surface.raised` or `text.tertiary`; it never owns a colour.
6. **Borders over shadows.** Depth comes from four surfaces and one hairline. Shadows are reserved for floating things: menus, dialogs, canvas nodes.
7. **Accent is state.** Selection, focus, checked, active tab, active path. Accent is never decoration.
8. **Status by exception.** `limited`, `failed`, `running`, `pinned` — a badge or a dot appears only when the normal state does not apply.

### 0.2 Color

The palette is intentionally narrow. Surfaces carry hierarchy; type carries emphasis; status carries meaning.

#### Surfaces

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg.canvas` | `#0E1115` | `#F3F5F7` | Node canvas behind the grid |
| `bg.base` | `#14171B` | `#FFFFFF` | Window, dock body, editor body, table background |
| `bg.raised` | `#191E22` | `#F7F8FA` | Chrome strips, toolbars, tab bars, palette, status bar |
| `bg.overlay` | `#1E242A` | `#FFFFFF` | Menus, popups, dialogs |
| `bg.inset` | `#101418` | `#F1F3F5` | Fields, chips, code panes, log panes, checkboxes |
| `bg.hover` | `#22282E` | `#EDF0F3` | Hover fill for buttons and rows |
| `bg.pressed` | `#2C333A` | `#E1E6EB` | Pressed fill |

**Rule:** `bg.hover` must be a visible step from the surface it sits on. The old `button_hover` (`#1A1F23`) was within 1–2 RGB points of `button_bg` (`#191E21`), so hover was invisible. Do not reintroduce that pair.

#### Text

| Token | Dark | Light | Use |
|---|---|---|---|
| `text.primary` | `#F5F7F9` | `#10151A` | Titles, active values, selected rows |
| `text.secondary` | `#C6CDD5` | `#39434D` | Body, labels, chips |
| `text.tertiary` | `#919BA6` | `#68737F` | Meta, counts, placeholders, table headers |
| `text.disabled` | `#5C6672` | `#9AA5B1` | Disabled controls only |

#### Accent and borders

| Token | Dark | Light | Use |
|---|---|---|---|
| `accent` | `#5680C2` | `#2F6FB5` | Selection, focus border, checked pin, active tab |
| `accent.hover` | `#6A96D7` | `#3D82CE` | Hover on accent-filled controls |
| `accent.pressed` | `#3A76BA` | `#245A96` | Pressed / active path |
| `border.subtle` | `#242A30` | `#E8EBEE` | Chip edges, row separators, internal hairlines |
| `border.default` | `#2F363D` | `#D6DBE0` | Field, panel and toolbar edges |
| `border.strong` | `#3E4750` | `#BCC5CD` | Menus, dialogs, table outer edge |

#### Status

| Token | Dark | Light | Use |
|---|---|---|---|
| `success` | `#48A878` | `#2E8B5F` | Executed node, paid state, success badge |
| `warning` | `#D9A441` | `#A9751A` | Limited preview, refund, non-fatal warning |
| `danger` | `#E0686C` | `#C1484D` | Failed node, validation error, destructive action |
| `info` | `#5BA8D6` | `#2A7DAE` | Neutral informational badge |
| `activity` | `#9B7BD4` | `#7452B4` | Running / executing state |
| `node.selection` | `#FFA637` | `#B26700` | Canvas selection ring only |

#### Node categories

| Token | Dark | Light |
|---|---|---|
| `node.input` | `#C4574F` | `#B84E47` |
| `node.prepare` | `#3F9E63` | `#34875A` |
| `node.join` | `#4F7FD1` | `#3F6FBF` |
| `node.transform` | `#7C5CBF` | `#7452B4` |
| `node.report` | `#C99A3C` | `#A87C22` |

Node colour identifies the **category**, never the state. State lives in the ring and the status dot (§13).

#### Current theme keys → Signal tokens

`base.qss` is a `str.format` template. Every `{token}` must exist in **both** `dark.json` and `light.json`, or startup raises. During migration, keep the existing keys as aliases.

| Signal token | Theme JSON key today | Action |
|---|---|---|
| `bg.base` | `background_primary` | keep |
| `bg.raised` | `background_secondary` | keep |
| `bg.overlay` | `menu_background` | keep |
| `bg.inset` | `editor_background` | keep |
| `bg.hover` | `background_hover` | keep, retune to `#22282E` |
| `bg.pressed` | `background_pressed` | keep, retune to `#2C333A` |
| `text.primary` | `text_primary` | keep |
| `text.secondary` | `text_secondary` | keep |
| `text.tertiary` | `text_inactive` | alias |
| `text.disabled` | `text_disabled` | keep |
| `accent` | `accent_primary` | keep |
| `accent.hover` | `accent_secondary` | keep |
| `accent.pressed` | `accent_tertiary` | keep |
| `border.subtle` | `border_primary` | alias |
| `border.default` | `card_border` | keep |
| `border.strong` | `border_light` | alias |
| `danger` | `error_text` | alias |
| `warning` | `background_warning` | add a foreground token too |
| `success`, `info`, `activity`, `node.*` | — | add to both JSONs |

### 0.3 Typography

| Role | Size / weight | Line | Use |
|---|---|---|---|
| Display | 20 / 600 | 24 | Splash, about, empty application state |
| Title | 16 / 600 | 20 | Dialog and window titles |
| Heading | 13 / 600 | 18 | Dock titles, section titles |
| Body | 12 / 400 | 18 | Default UI text, values, descriptions |
| Label | 11 / 500 | 16 | Chips, buttons, tabs, table headers, meta |
| Micro | 10 / 600 | 14 | Overlines, config info, dtypes, `letter-spacing .06em`, uppercase |
| Mono | 11 / 400 | 16 | Logs, SQL, formulas, counts where alignment matters |

- UI face: **Segoe UI Variable Text**, falling back to **Segoe UI**. Data face: **Cascadia Mono**, falling back to **Consolas**.
- No webfonts. No per-widget font sizes. Table headers use Micro; numeric cells use Mono with tabular figures.
- Body text is 12px, not 13px. Header text in the old `QHeaderView` was 13px; the table header is now 11px Micro.

### 0.4 Spacing, size and radius

| Token | Value | Use |
|---|---|---|
| Space hairline | 2 | Inside a chip, icon/label gap |
| Space chrome | 4 | Strip gaps, button groups |
| Space strip | 6 | Strip horizontal padding, `QHBoxLayout` spacing |
| Space panel | 8 | Dock/panel padding, card padding |
| Space group | 12 | Gap between sections |
| Space dialog | 16 | Dialog body padding |
| Space section | 24 | Page/section separation |
| Chrome strip | 36 | `PreviewStrip` and all shared chrome rows |
| Toolbar | 40 | Config Dock `Pattern A` toolbar |
| Control | 30 | `QLineEdit`, `QPushButton`, `QComboBox` |
| Chip | 24 | Node, socket, scope and counts chips |
| Dense row | 24 | Read-only preview tables |
| Default row | 28 | Editable/data tables |
| Icon | 12 | Dock actions; 16 maximum for a primary action |
| Radius badge | 3 | Status badges |
| Radius control | 4 | Buttons, fields, chips, tables |
| Radius panel | 6 | Cards, menus, dialogs |
| Radius node | 10 | Canvas node tiles |
| Node scene body | 120 | Graphics item units; unchanged by this system |
| Node tile | 120 | The visible tile at 100% zoom; palette tiles scale down from it |

**Density rule:** 2 / 4 / 6 inside a panel; 8 / 12 only between groups. If a panel feels tight, remove a control or split the panel — do not grow the controls.

### 0.5 Depth and motion

- Four surfaces (`canvas`, `base`, `raised`, `overlay`) plus `inset` for controls. One 1px border marks each edge.
- No shadows on docks, strips, panels or chips. Shadows are allowed only on floating nodes, menus and dialogs.
- Hover is an instant fill change. Do not animate QSS colours or add fades; Qt stylesheets do not transition reliably.
- The only timed behaviour in the UI is the 300ms debounce on text input (§6) and the 300ms preview coalescing.

### 0.6 App shell

```
QMainWindow
├─ Menu bar
├─ NodesDock (top, max height 105)
├─ ConfigDock (left, min width 300)
├─ QMdiArea / node canvas
├─ LoggingDock + DataPreviewDock (bottom, tabbed)
└─ Status bar (20)
```

- The Config Dock spans the main work area; the bottom docks span the full width.
- The preview and logs share one bottom dock area as tabs. The Preview panel owns its own 36px strip; the dock adds no second header.
- The canvas is the only surface that fills remaining space. Everything else is fixed-height chrome.
- Window and dock titles are context, not decoration: `Node Configuration (Select)`, `Logs - monthly_sales.tds`, `Data Preview`.

---

## 1. Layout tokens

| Token | Value | Notes |
|---|---|---|
| Dock min width | `300` | `qt/docks/node_config.py` |
| Main `QVBoxLayout` | `spacing 2, margins 5,5,5,5` | `transpose.py:77`, `cleansing.py:173` |
| Toolbar `QWidget + QHBoxLayout` | `fixedHeight 40, margins 0,0,0,0` | `select.py:158-161` |
| Control height | `30` min (`QLineEdit`, `QPushButton`, `QComboBox`) | `select.py:168,175,205` |
| Icon button | `30x30`, icon `12x12` (`16x16` max for primary) | `select.py:172-180` |
| Chrome strip | `36` high; chip `24`; search `26`; action `30` | `data_preview_panel.py` |
| Checkbox column width | `50` (`header.resizeSection(0, 50)`) | `select.py:249` |
| Scroll threshold | `ColumnChecklist max_height 150-220` | `config_widgets.py:71`, `cleansing.py:173` |
| Default table row | `28` (`24` for dense read-only previews) | `polars_table_viewer.py` |
| End layout | `addStretch()` last, never an empty `HBox` after stretch | `filter.py:104` violates this |

Docks must `dock_layout.addWidget(toolbar)` then `dock_layout.addWidget(view, 1)` — stretch factor `1` on the main view. No `dock.setContentsMargins(0,0,0,0)` (see `file_output.py:71` violation).

---

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
Do not use `ConfigSection` here — the toolbar is the section.

### B. Form stack (for settings)

```
QVBoxLayout [spacing 2, margins 5]
├─ ConfigSection("Title", info="one-line hint") [spacing 2, no overrides]
│   ├─ NoWheelComboBox / QLineEdit / QSpinBox
│   └─ ColumnChecklist(columns, checked)
└─ addStretch()
```

Use for: Filter, Sort, Split, Transpose, Formula sections, File In/Out.
Reference: `transpose.py:77`, `running_total.py:99`. Never raw `QComboBox` (wheel-steal bug) — use `NoWheelComboBox`.

Pattern C — the chrome strip — is for shared docks, not a third Config Dock layout. See §8.

---

## 3. Shared widgets (must reuse)

Import from `qt/widgets/common/__init__.py`:

- `EmptyStateLabel` — only empty state. Centered gray, default text `"No incoming data available"`. Gate at top of `create_layout`: `if incom_data is None: dock.addWidget(EmptyStateLabel()); return`.
- `ConfigSection(title, info)` — `QGroupBox#ConfigSection` + `QLabel#ConfigSectionInfo` (wordWrap). Never `layout().setSpacing(10)` / `setMargins(15)` — see `unique.py:87` violation. **Target:** flatten the group-box border; the heading + hairline is the section.
- `ColumnChecklist(columns, checked, max_height)` — scrollable checkboxes, `changed(list)` signal. Never hand-rolled `QListWidget` checkboxes (`unique.py`, `join.py` violations).
- `NoWheelComboBox` — drops wheel events unless popup open. Use everywhere a combo sits in a scrollable dock.
- `IconButton` / `TextButton` — see §4.

Table helpers: `SelectTableWidget`, `RowData`, `ComboBoxDelegate` in `qt/widgets/select_table_widget.py` — reuse delegate painting (`QStyleOptionComboBox`) for any dtype/option column.

**Target shared primitives:** `Chip`, `StatusBadge` and `ToolbarStrip` belong in `config_widgets.py`, not in a node. Do not fork them per dock.

---

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

Use `IconButton.themed(...)` when the icon comes from `ResourceManager`, with a `:/qss_icons` fallback. `QIcon.fromTheme` is last resort and is blank on Windows.

### 4.2 Action → icon map

| Action | `resources.json` id | Fallback `:/qss_icons/dark/rc/` |
|---|---|---|
| Move up / down | `icon_move_up` / `icon_move_down` — ADD | `arrow_up.png` / `arrow_down.png` |
| Add / Remove | `icon_add` / `icon_remove` — EXISTS | — |
| Options menu | `icon_options` — EXISTS (sliders) | `arrow_down.png` |
| Check all / Uncheck all | `icon_check_all` / `icon_uncheck_all` — ADD | — |
| Apply / Evaluate / Run | `icon_apply` — EXISTS | `media-playback-start` theme equivalent |
| Load / Save file | `icon_folder_open` / `icon_save` — EXISTS | — |
| Refresh | `icon_refresh` — EXISTS | — |
| Clear filter | `icon_clear` — ADD | — |
| Export CSV / Excel | `icon_export` — ADD (one icon, menu picks format) | — |
| Open in window | `icon_external` — EXISTS | — |
| Pin / Unpin | `icon_pin` / `icon_unpin` — EXISTS | — |
| Search | `icon_search` — EXISTS | — |

Until ids are added, use `QIcon(":/qss_icons/dark/rc/<name>.png")` directly — never `fromTheme`.

### 4.3 Exceptions (text allowed)

- `QDialogButtonBox` / `QMessageBox`: `Save / Cancel / Close` text stays (`settings_panel.py:79`, `about.py:164`).
- Destructive confirmations keep text.
- **Paired bulk toggles** use `TextButton` with the labels `All` / `None`. Two near-identical checkbox glyphs cannot be told apart at a glance, so these keep their words. Used in `Preparation/cleansing.py` and `Preparation/unique.py`. `TextButton` is `H30`, `objectName="TextButton"`, and inherits the same hover/pressed treatment as `IconButton` (§4.5).
- Nothing else. These stay icons: `join.py` bulk L/R actions (folded into the Options menu), `Evaluate`, `groupby.py` Add/Remove/Apply, `formula.py` add/remove, `file_input.py`/`file_output.py` browse, `graph.py` open-in-window.

### 4.4 Bulk toggles

No `All / None` *icon* rows. Either fold them into the toolbar `Options` `QMenu` (Join's four L/R actions) or use the `All` / `None` `TextButton` pair when the action pair is genuinely ambiguous.

### 4.5 Hover / pressed states are mandatory

Qt gives an `objectName` selector (`QPushButton#IconButton`) higher specificity than a pseudo-state (`QPushButton:hover`). Any widget that sets its own `background-color`/`border` via `objectName` **must restate** `:hover`, `:pressed` and `:disabled`, or hover silently does nothing.

- Base `QPushButton` / `QToolButton` use a constant `1px solid {button_bg}` border so recolouring the border on hover does not shift the button by a pixel.
- Hover fill is `{background_hover}` (a real contrast step). Do **not** use `{button_hover}` for hover: in the shipped themes it is within 1–2 RGB points of `{button_bg}`, so the state is invisible.
- Restated for `#IconButton`, `#OptionsButton`, `#TextButton`, `#PreviewPinButton`.
- A button that carries its own glyph **and** has a `QMenu` must suppress the menu indicator, otherwise Qt stacks a second down arrow next to the icon:

  ```css
  QPushButton#OptionsButton::menu-indicator {{
    width: 0px; height: 0px; border: none; image: none;
    subcontrol-origin: padding; subcontrol-position: center; }}
  ```

  Do not achieve this with inline `setStyleSheet`, and do not use `setLayoutDirection(Qt.RightToLeft)` as a substitute — it moves the glyph instead of removing the arrow.

---

## 5. Empty / loading / error

- No data: `EmptyStateLabel()` only. Delete custom variants (`count_records.py:61` italic label, `file_input.py` `_hide_all_options`). The label is one quiet line; if a hint is needed, a second 10px line is allowed, nothing else.
- Join/Append need both inputs: `if left is None or right is None: EmptyState` (fix `join.py` `and`-logic, `Append.py:74` inverted gate).
- Never connect signals outside the `if data is not None` branch (fix `filter.py:104` crash).
- Node errors surface via `grNode.setToolTip(...)`, not red inline labels (fix `sort.py:94`).
- Loading: use `EmptyStateLabel("Loading...")` as the placeholder. Do not invent spinners or skeleton cards until they are specified.
- Error: a failed preview or workflow uses one sentence plus the underlying message, in `text.secondary`; the failure colour appears in the badge or node ring, not across the panel.

---

## 6. Interaction: live-by-default

Every `setData / move / check / sort` → `data_processed → handleDataChanged → process_data_changes + apply_changes + evaluate.emit`, as in `select.py:255`, `groupby` equivalent.

- Debounce: `300ms` for text search / rename edits; immediate for check/move/combo.
- Heavy nodes (Join, GroupBy, Formula) still live — debounce, don't add Apply buttons. `groupby.py:278` Apply and `join.py:197` Evaluate are migration targets, not patterns.
- History: store diff only (`old != new`), verb format `"Noun Verbed"` e.g. `"Column Selection/Rename/Type Changed"`.
- Dock preservation: `ConfigDock.updateConfig` (`node_config.py:30`) skips wipe when `id(content) == _current_key`, suspends `_suspend_input_tracking/_suspend_node_evaluation` during `create_layout`. Do not rebuild widgets on every keystroke.

---

## 7. QSS / theming

- Zero inline `setStyleSheet` in node files and shared dock chrome. Use `objectName` + `resources/qt/themes/base.qss` / `qss/_style.scss`.
- Required Config Dock objectNames: `ConfigSection`, `ConfigSectionInfo`, `EmptyStateLabel`, `ColumnChecklist`, `IconButton`, `OptionsButton`, `TextButton`, `DataTypeCombo`, `JoinSourceLeft`/`JoinSourceRight`, `JoinSourceHeaderLeft`/`Right`, `JoinDtypeLabel`.
- Dock chrome objectNames: `PreviewStrip`, `PreviewNodeChip`, `PreviewNodeLabel`, `PreviewPinDot`, `PreviewSocketChip`, `PreviewSocketCombo`, `PreviewSearchEdit`, `PreviewScopeCombo`, `PreviewCountsChip`, `PreviewStatusLabel`, `PreviewLimitedBadge`, `PreviewSourceBadge`, `PreviewPinButton`.
- The dock-chrome boundary is explicit: §§1–7 govern node config docks; shared dock chrome follows §7 and the new §§8–14. Both use `objectName` + `base.qss`/`_style.scss`, restate hover/pressed per `objectName`, and use no inline QSS.
- `base.qss` is a `str.format` template: only keys present in the theme JSONs may be used. The full key set is grouped in `qt/theme_manager.py` (`TOKEN_GROUPS`): **Surfaces, Text, Accent, Status, Borders, Controls, Canvas, Code, Nodes**. `tests/unit/test_theme_tokens.py` asserts every `{token}` exists in both built-in themes and that every colour token is exposed in the editor — run it after editing either file.
- Same rule in `_style.scss`, using the `$COLOR_*` names from `_variable.scss`: `$COLOR_BACKGROUND_1..6`, `$COLOR_TEXT_1..4`, `$COLOR_DISABLED`, `$COLOR_ACCENT_1..4`, `$SIZE_BORDER_RADIUS`, `$BORDER_1..3`.
- Never hand-edit generated QSS in one place only; keep `base.qss` and `_style.scss` in agreement. The generated `runtime_theme.qss` is gone: `ThemeManager` renders `base.qss` from the active theme at runtime, so there is nothing to regenerate by hand.
- **Target** hooks to add: `ChromeStrip`, `Chip`, `ChipDot`, `StatusBadge`, `CountsChip`, `PrimaryButton`, `DangerButton`, `DialogSurface`, `MenuSurface`, `TableHeader`, `TableRow`. Add them to both QSS sources and to the objectName registry in §17.

### Custom view delegates

Never hand a bare `QStyleOptionComboBox` to `drawComplexControl` — with no `palette` set, Qt falls back to the application default (light grey in Fusion) and the cell clashes with the themed surface. `ComboBoxDelegate.paint` in `select_table_widget.py` therefore paints from `option.palette`/`option.font` directly. If you add a delegate, copy the palette and font, and keep `setAutoFillBackground(True)` off editors that have a themed `objectName`.

### Themes, user themes and preferences

- `qt/theme_manager.py` is the **only** owner of `QApplication.setStyleSheet()`; every other surface listens to `ThemeManager.themeChanged` (`TriggerWindow.apply_appearance`, `LoggingDock.apply_theme`, `SQLFormulaEditor.apply_theme`, `NodeBase.apply_theme`). Never call `setStyleSheet` on the application or a window directly.
- Theme files are schema 2 — a flat token dictionary is still read, but new files use:

  ```json
  {"schema": 2, "id": "dark", "name": "Dark", "appearance": "dark", "extends": null,
   "tokens": {"background_primary": "#14171b"}}
  ```

  `extends` inherits a parent's tokens; a token missing from a user theme falls back to built-in dark with a warning. `appearance` (`dark`/`light`) drives System mode and the title-bar contrast, not the tokens.
- Built-ins live in `src/trigger_designer/resources/qt/themes/`; user themes live in `%APPDATA%\Trigger Designer\themes` (env override `TRIGGER_DESIGNER_DATA_DIR`) and shadow a built-in with the same id. `duplicate_theme` is the supported way to fork a built-in; a shadowing theme must not `extends` the id it shadows (that resolves to itself and is reported as circular).
- Everything the editor exposes is a **colour** token. Geometry, spacing, control heights and radius are design-system-owned (§§1, 4.1) and intentionally not themeable.
- Preferences are one INI at `%APPDATA%\Trigger Designer\preferences.ini` (`qt/preferences.py`); the first run migrates the legacy `QSettings` scopes (`Blue Octa/Trigger Designer`, `Trigger/Trigger Designer`, `Trigger/NodeEditor`). Do not add new `QSettings` scopes.
- Layout is one auto-saved record (`qt/layout_state.py`): `saveGeometry()` plus `saveState(1)` over stable dock objectNames (`NodesDock`, `ConfigDock`, `LoggingDock`, `DataPreviewDock`), with Window ▸ Save Current Layout / Reset Layout. There are no layout presets and no named workspaces.
- The last session's file list is captured on close but only reopened when `layout/session` is on; it defaults off ("layout on, files off").
- `QMdiArea` paints its own `background` brush, which no stylesheet rule reaches: `TriggerWindow._theme_mdi_background()` sets it from `canvas_background`.

---

## 8. Chrome strip (signature component)

The Preview strip is the only app chrome pattern. Generalise it; do not clone it with per-dock styling.

```
QFrame#ChromeStrip [fixedH 36, bg raised, bottom hairline]
└─ QHBoxLayout [spacing 4, margins 6,3,6,3]
    ├─ node chip       [24]  identity, optional pin dot
    ├─ socket chip     [24]  only when the host has several outputs
    ├─ search field    [26]  the only flexible element
    ├─ scope combo     [24]  search scope
    ├─ stretch
    ├─ counts chip     [24]  "1,284 rows · 12 cols", optional "limited" badge
    ├─ pin action      [30]  checkable
    ├─ refresh action  [30]
    └─ options action  [30]  QMenu, indicator suppressed
```

Rules:

- The strip is **36px**. Chips are **24px**, fields **26px**, actions **30×30 / 12px**.
- Order is fixed: identity → search → scope → counts → actions. Counts sit immediately before actions; they are not a footer.
- Only the search field flexes. It has `min-width 110`, `max-width 200`, a leading search glyph and a clear button.
- The strip owns no title. The dock/window title identifies the host; the strip identifies the node and data.
- No pager footer. The whole collected frame is one page; the table scrolls.
- Standalone hosts (Data Preview window) hide node, socket and pin. They are not disabled or replaced with placeholders; they are absent.
- Collapse order on a narrow host: socket → scope → counts → node label. Keep identity, search and actions longest.
- A `limited` badge appears only when collection stopped at the size limit. It is not a permanent status.

Target objectNames: `ChromeStrip`, `ChromeChip`, `ChromeChipDot`, `ChromeSearch`, `ChromeScope`, `ChromeCounts`, `ChromeBadge`, `ChromeAction`. `Preview*` names remain as aliases until migration.

---

## 9. Chips and badges

### Chips — identity and counts

- 24px high, `bg.base` on `bg.raised`, `1px border.subtle`, `radius 4`, 11px Label text, 6px dot.
- Use for node identity, socket, search scope and counts.
- Truncate a long node title with `Qt.ElideMiddle` and keep the full title in the tooltip.
- Counts format: `1,284 rows · 12 cols`. When filtered: `48 / 1,284 rows · 12 cols`. When counting: `1,284 rows · counting…`.

### Badges — status by exception

- 18px high, `radius 3`, 10px Micro/600, horizontal padding 5.
- `limited` → `warning` background (`background_warning` / `warn_text`), text primary.
- `Executed` → success soft; `Failed` → danger soft; `Pending` → info soft.
- A badge is not a chip. Do not use it for counts or identity.

---

## 10. Fields, combos and focus

- Field height **30px** (26px inside a chrome strip), `bg.inset`, `border.default`, `radius 4`, 12px Body.
- Hover: `border.accent`. Focus: `border.accent` + a 2px `accent-soft` ring. Never remove the ring; never use a native 3px dotted outline.
- Placeholder is `text.tertiary`; disabled text is `text.disabled`; selection is `accent` with white text.
- **Always** `NoWheelComboBox` in a scrollable dock. A raw combo steals wheel events from the panel.
- Search fields: leading search glyph, clear button, debounce 300ms. Enter does not submit; the field is the truth.
- Checkboxes stay native in size and painting; theme via `QCheckBox::indicator`, not a custom widget.

---

## 11. Tables

| Property | Default | Dense preview |
|---|---|---|
| Row height | 28 | 24 |
| Header | 11px Micro, uppercase, `text.tertiary`, `bg.base` | same |
| Grid | horizontal hairline only | horizontal hairline only |
| Selection | `accent` at 18% + `text.primary` | same |
| Hover row | `bg.hover` | same |
| Numeric cells | Mono, right-aligned, tabular figures | same |
| Dtype | 10px Micro after the column name | same |
| Sort indicator | small chevron, accent | same |

- Do not draw vertical grid lines. The row separator is enough.
- `QHeaderView::section` must use the theme tokens; no default Fusion header.
- Delegates must paint from `option.palette`/`option.font`; never hand a bare `QStyleOptionComboBox` to `drawComplexControl`.
- The Preview table is dense (24px); editable tables are 28px. Do not mix densities in one view.
- Copy/export menus stay in the strip's Options menu; no table footer.

---

## 12. Menus and dialogs

### Menus

- `bg.overlay`, `1px border.default`, `radius 6`, shadow allowed.
- Items **27–28px** high, 8px horizontal padding, 4px radius, 12px Body.
- Hover/selected: `accent-soft` fill + `text.primary`. No accent bar.
- Separators: 1px `border.subtle`, 4px vertical margin.
- Shortcut text: 10px Mono, `text.tertiary`; only for real shortcuts.
- Dialog-opening items end in `…`; immediate commands do not.

### Dialogs

- `bg.base`, `1px border.strong`, `radius 8`, shadow allowed.
- Header **34px**, Title 16/600, close icon 22×22.
- Body padding **16px**, one column, 8px gap.
- Footer **42–48px**, right-aligned buttons, 6px gap. `QDialogButtonBox` text stays.
- Exactly one primary action per dialog. Destructive confirmations use `DangerButton` + explicit noun.
- No custom title bar, no illustration headers, no multi-column forms unless the dialog is a dedicated manager.

---

## 13. Canvas: nodes, states and edges

### Node body

- 120×120 scene units, radius 10, category fill, white glyph.
- Node title: 11px Label, `text.secondary`, centred under the tile; elide middle, full text in tooltip.
- Palette tiles scale the same artwork to 22–32px; they are not a second icon set.

### State matrix

| State | Ring | Status dot | Notes |
|---|---|---|---|
| Idle | none | none | Category fill is the only signal |
| Hover | 1px `rgba(255,255,255,.30)` | none | Must not shift layout |
| Selected | 2px `node.selection` (`#FFA637`) | optional success | Selection outranks hover |
| Running | 2px `activity` | spinner/dot optional | No pulsing fill on the whole tile |
| Executed | 2px `success` | success check, bottom-right | Clears when the node is dirtied |
| Error | 2px `danger` | danger glyph, bottom-right | Tooltip carries the message |

- State is never colour alone: the ring plus dot/glyph plus tooltip.
- The ring is drawn outside the tile and must not change the node's hit area.

### Edges and grid

- Grid: 22px minor, 110px major, `rgba(255,255,255,.035)` / `.06` in dark; dark ink at equivalent alpha in light.
- Edge default: `#454D57` (light: `#AAB4BE`), 1.4px screen width, `vector-effect: non-scaling-stroke`.
- Edge active/selected: `accent`, 1.8px. No magenta/tan defaults; those are legacy and belong to the old editor skin.
- Edge hover: lighten one step, do not change width.
- No animated dashes or particles by default; execution state belongs to the node ring.
- Canvas and grid colours are tokens — `canvas_background`, `canvas_grid_light`, `canvas_grid_dark` — applied by `apply_theme_to_scene()`; state rings read `node_selection` / `activity` / `success` / `danger` through `NodeBase._pen_role`. Keep paint methods token-driven; a literal `QColor("#...")` in a `paint()` is a bug.
- The workspace frame behind the sub-windows is `canvas_background` too (`TriggerWindow._theme_mdi_background`), so the graph and the frame read as one surface. Edge and socket colours are user settings, not theme tokens (`qt/node_editor_colors.py`).

### Canvas chrome

- Floating toolbar top-left, 30px actions, no background plate beyond their own buttons.
- No minimap, no floating legend, no permanent help text. The status bar carries hints.

---

## 14. Logs and status bar

### Logs

- 11px Mono, row 22, timestamp `text.tertiary`, level badge 10px Micro, message `text.secondary`.
- Level is the only colour: `INFO` info, `WARN` warning, `ERROR` danger, `CRITICAL` danger + bold, `DEBUG` tertiary.
- No card per line. The log pane is one `bg.inset` surface with hairline separators.
- Auto-scroll is a checkbox in the dock controls, not a footer button.
- Colours come from the theme (`text_*`, `info`, `warning`, `danger`) via `LoggingDock.apply_theme()` / `LogsTextEdit`; the SQL editor's syntax colours are the `Code` token group (`syntax_*`, `editor_line_number_*`, `editor_current_line`). No hardcoded log or syntax colours.

### Status bar

- 20px high, `bg.raised`, top hairline, 10px Label, `text.tertiary`.
- Left: file path or current action. Right: `Ready`, encoding, column count. Truncate the path, never the state.

---

## 15. Accessibility

- Minimum interactive target: **30×30**. A 24px chip is not a button; do not make it clickable without a 30px hit area.
- Every icon-only control has a tooltip **and** `setAccessibleName`. The two strings match.
- Focus is always visible: 1px accent + 2px soft ring. No `outline: none` without a replacement.
- Status is not colour-only: pair the colour with a word, glyph or dot.
- Contrast: `text.secondary` on `bg.base` ≥ 4.5:1; `text.tertiary` is for meta only, never body copy; disabled text is exempt.
- Keyboard: `Ctrl+F` focuses preview search, `Ctrl+R` refreshes, `Esc` closes overlays, `Tab` reaches every control in visual order.
- No motion that cannot be disabled. QSS transitions are not used; debounce is not a visual animation.

---

## 16. Content and copy

- Sentence case for labels, menu items and tooltips. Title Case for window and dialog titles.
- Menu items that open a dialog end in `…`; immediate commands do not.
- Counts: `1,284 rows · 12 cols`; use a thin middot and thousands separators.
- History: `"Noun Verbed"` — `Column Selection Changed`, `Node Label Changed`, `Dtype Changed`.
- Empty: one sentence plus, at most, one hint line. No exclamation marks, no jokes.
- Tooltips: sentence case, no trailing period, describe the action not the icon (`Refresh preview`, not `Refresh`).
- Errors: what failed, on what, and the next action. Keep the raw exception out of the badge; put it in the tooltip or log.
- Numbers in tables: right-aligned, tabular, consistent decimals.

---

## 17. Implementation map

### Tokens

1. Add the token to **both** `resources/qt/themes/dark.json` and `light.json` (schema 2, under `tokens`), and to the matching `TOKEN_GROUPS` group in `qt/theme_manager.py` so the editor exposes it.
2. Add the matching `$COLOR_*` values to `qss/_variable.scss` and the selectors to `qss/_style.scss`.
3. Add the same selectors to `resources/qt/themes/base.qss`; write `{{` / `}}` for QSS blocks, `{token}` for values.
4. Run `tests/unit/test_theme_tokens.py` — it collects every `{token}` in `base.qss` and fails if either theme (or the editor's group list) is missing one.

### Python-painted surfaces

`qt/theme_manager.py` is the single accessor: `ThemeManager.color(token)` returns a `QColor`, `token()` the raw value, both cached per theme. `ResourceManager.get_theme_color` delegates to it, so older call sites keep working.

Route these through it:

- node category fills and state rings (`node_base.py`)
- table row parity (`polars_table_viewer.py`)
- canvas grid and background (`apply_theme_to_scene`)
- log levels and the SQL editor's syntax colours (`apply_theme`)
- the workspace frame (`TriggerWindow._theme_mdi_background`)

Missing tokens fall back to the built-in dark value, and a user theme that omits one gets it filled with a warning. No widget should call `QColor("#...")` in a `paint()` method. Edge and socket colours are a **user setting**, not a token (`qt/node_editor_colors.py`).

### Shared widget constants

`qt/widgets/common/config_widgets.py` owns:

```python
STRIP_H = 36
TOOLBAR_H = 40
CONTROL_H = 30
CHIP_H = 24
ROW_H = 28
DENSE_ROW_H = 24
ICON_SIZE = 12
```

`IconButton`, `TextButton`, `Chip` and `StatusBadge` use these constants. Do not repeat the numbers in node files.

### ObjectName registry

| objectName | Owner | States to restate |
|---|---|---|
| `IconButton` | shared | hover, pressed, disabled, checked |
| `OptionsButton` | shared | hover, pressed, disabled, menu-indicator |
| `TextButton` | shared | hover, pressed, disabled |
| `ConfigSection` | shared | — |
| `ConfigSectionInfo` | shared | — |
| `ColumnChecklist` | shared | — |
| `EmptyStateLabel` | shared | — |
| `PreviewStrip` → `ChromeStrip` | Preview / shared chrome | — |
| `PreviewNodeChip` → `ChromeChip` | Preview / shared chrome | — |
| `PreviewSearchEdit` → `ChromeSearch` | Preview / shared chrome | hover, focus, disabled |
| `PreviewScopeCombo` → `ChromeScope` | Preview / shared chrome | hover, focus, disabled |
| `PreviewCountsChip` → `ChromeCounts` | Preview / shared chrome | — |
| `PreviewLimitedBadge` → `ChromeBadge` | Preview / shared chrome | — |
| `PreviewSourceBadge` → `ChromeBadge` | Preview / shared chrome | `[source="run"]` tone |
| `PreviewPinButton` | Preview | hover, pressed, disabled, checked |
| `PrimaryButton` | dialogs | hover, pressed, disabled |
| `DangerButton` | dialogs | hover, pressed, disabled |
| `MenuSurface` | menus | — |
| `DialogSurface` | dialogs | — |
| `PreferencesDialog`, `ThemeEditorDialog` | preferences / theme editor | — |
| `PreferencesSidebar`, `PreferencesPages`, `PreferencesPage` | preferences | item hover, selected |
| `ThemeList`, `ThemePreview` | preferences | item hover, selected |
| `ThemeEditorScroll`, `ThemeEditorContent` | theme editor | — |
| `ThemeNameEdit`, `ThemeAppearanceCombo`, `GridSizeSpin`, `RecentLimitSpin` | preferences / theme editor | hover, focus, disabled |
| `ColorHexEdit`, `ColorSwatch`, `ThemeTokenRow`, `ContrastLabel` | theme editor | hover, focus |
| `FieldLabel`, `FieldHint`, `SectionTitleText` | preferences / theme editor | — |
| `LogsTextEdit` | logs | — |
| `FormulaCompleterPopup` | SQL editor | hover, selected |

### Guards

Tests that fail fast, all under `tests/` (the shared fixtures live in `tests/conftest.py` and keep the preference store in a temp dir):

- **Theme parity:** parse `base.qss`, collect every `{token}`, assert it exists in both theme JSONs, and assert every colour token is exposed by `TOKEN_GROUPS` (`test_theme_tokens.py`).
- **Theme manager:** schema 2, `extends`, missing-token fallback, invalid colours, accent variants, preview/commit/cancel, save/import/export/delete (`test_theme_manager.py`).
- **Preferences:** defaults, typed coercion, legacy migration, reset (`test_preferences.py`).
- **Layout:** geometry and dock-state round trip, session gating and filtering, off-screen guard (`test_layout_state.py`).

Target guards still to add:

- **No inline QSS:** no `setStyleSheet` in `qt/widgets/nodes/**` or the shared dock chrome.
- **Accessible actions:** every `QPushButton` with an empty `text()` has a non-empty `toolTip()` and `accessibleName()`.
- **No `fromTheme` in nodes:** a grep test for `QIcon.fromTheme` outside the documented fallback helper.

### References

- Preview strip: `qt/widgets/data_preview_panel.py`
- Preview dock host: `qt/docks/data_preview.py`
- Config dock host: `qt/docks/node_config.py`
- Shared widgets: `qt/widgets/common/config_widgets.py`
- Table: `qt/models/polars_table_viewer.py`, `qt/widgets/select_table_widget.py`
- Canvas: `qt/node_base.py`, `qt/node_editor_colors.py`
- Theme: `resources/qt/themes/base.qss`, `resources/qt/themes/dark.json`, `resources/qt/themes/light.json`, `qss/_variable.scss`, `qss/_style.scss`
- Theme engine: `qt/theme_manager.py`, theme editor `qt/dialogs/theme_editor_dialog.py`, swatches `qt/widgets/common/theme_widgets.py`
- Preferences: `qt/preferences.py`, dialog `qt/dialogs/preferences_dialog.py`, host window `qt/main_window.py`
- Layout and session: `qt/layout_state.py`, `qt/helpers/preview_dock_state.py` (legacy migration only)
- Visual preview: [`design_system_preview.html`](design_system_preview.html)

---

## 18. Anti-patterns (do not copy)

1. Inline QSS per button (`groupby.py:219`, `select.py:191`).
2. `QIcon.fromTheme` on Windows — invisible icons.
3. Text `All/None` rows (`join.py:162`, `cleansing.py:198`) unless they are the paired `TextButton` exception.
4. Custom spacing `10/15` on sections (`unique.py:87`, `split.py:92`).
5. Raw `QComboBox` in docks, raw `QListWidget` checkboxes.
6. Signals connected when data is `None` (`filter.py`).
7. `dock.setContentsMargins(0,0,0,0)` wiping dock padding (`file_output.py:71`).
8. Stub nodes with no `create_layout` (`union.py`, `find_replace.py`) — add `EmptyStateLabel` gate at minimum.
9. A second toolbar or a footer that repeats the strip.
10. Accent used as decoration or category colour.
11. Status communicated by colour alone, or a whole dock repainted for one error.
12. Shadows on panels, strips, chips or table cells.
13. 44px controls or 16px gaps inside a dock.
14. Per-node forks of `Chip`, `StatusBadge`, `IconButton` or `ConfigSection`.

---

## 19. Migration checklist

### Phase 1 — tokens and guards

- [ ] Add Signal keys to `dark.json` and `light.json` (schema 2; `TOKEN_GROUPS` in `qt/theme_manager.py` is the authoritative list).
- [ ] Route Python-painted colours through `ThemeManager.color()` — `qt/style_tokens.py` turned out to be unnecessary, the manager is the accessor.
- [ ] Add theme-parity, inline-QSS, accessible-action and `fromTheme` tests.

### Phase 2 — QSS foundation

- [ ] Add surface, text, accent, status and node tokens to `base.qss` and `_style.scss`.
- [ ] Add `ChromeStrip`, `Chip`, `StatusBadge`, `PrimaryButton`, `DangerButton` hooks.
- [ ] Restate hover/pressed/disabled per `objectName`; keep a constant 1px base border.
- [ ] Verify the light theme, not just dark.

### Phase 3 — shared chrome

- [ ] Move the Preview strip to the shared `ChromeStrip` composition; keep `Preview*` aliases.
- [ ] Apply the strip rhythm to the Logs dock and Config Dock header.
- [ ] Align the status bar and tab bars to 20 / 24px.
- [ ] Update the standalone Preview window to hide node, socket and pin.

### Phase 4 — Config Dock

- [ ] Flatten `ConfigSection`: heading + hairline, 4px gaps, no group-box border.
- [ ] Normalise toolbars to 40px, controls to 30px, icons to 12px.
- [ ] Replace hand-rolled checklists with `ColumnChecklist`; use `TextButton` only for All/None.
- [ ] Gate every dock on `EmptyStateLabel`; remove custom empty variants.
- [ ] Align tables to 28px rows and the 11px header.

### Phase 5 — canvas

- [ ] Move node category colours to `node.*` tokens.
- [ ] Add 2px state rings and status dots; selected ring uses `node.selection`.
- [ ] Replace tan/magenta edge defaults with neutral + accent.
- [ ] Set the 22 / 110px grid and canvas surface.
- [ ] Keep the 120-unit node body; do not shrink the scene without a separate decision.

### Phase 6 — polish and proof

- [ ] Menus and dialogs: 6/8px radius, 27px items, one primary action.
- [ ] Add a light-theme screenshot for each surface.
- [ ] Delete ad-hoc colours and spacing that now have tokens.
- [ ] Re-run the Select, Join, GroupBy, Filter, Preview and Logs smoke tests.

### Config Dock backlog (from the original contract)

- [x] `IconButton` exists in `widgets/common/config_widgets.py` and is exported.
- [ ] Add the missing icon ids (move up/down, check all/uncheck all, clear, export) to `qt/resources.json`.
- [x] `select.py`: drop `"Options"` text → `icon_options`, swap `fromTheme go-up/go-down` → bundled arrows.
- [ ] `join.py`: icon-ify All/None→Options menu, Evaluate→apply icon, `QListWidget`→`ColumnChecklist`, fix empty gate to `or`.
- [ ] `groupby.py`: kill blue-pill QSS, Add/Remove/Apply→icons, bold labels→`ConfigSectionInfo`.
- [ ] `formula.py`: `+ Add formula`→icon, remove→`icon_remove`, adopt `NoWheelComboBox`.
- [ ] `filter/sort/split/unique/cleansing`: adopt Pattern B tokens, `NoWheelComboBox`, fix `filter.py` signal crash, `unique.py` spacing.
- [ ] `file_input/output`: Load/Save→icons, remove `setContentsMargins(0)`, add `EmptyStateLabel` path.
- [ ] `graph.py`, `count_records.py`, `union.py`, `find_replace.py`: add empty gates + sections.
- [ ] Move all inline QSS to `base.qss` + `_style.scss`.

---

## 20. References

- Select dock: `src/trigger_designer/qt/widgets/nodes/Preparation/select.py:134-280`
- Table model/delegate: `src/trigger_designer/qt/widgets/select_table_widget.py:36-771`
- Dock host: `src/trigger_designer/qt/docks/node_config.py:10-129`
- Shared widgets: `src/trigger_designer/qt/widgets/common/config_widgets.py:1-139`
- Preview panel: `src/trigger_designer/qt/widgets/data_preview_panel.py`
- Preview dock: `src/trigger_designer/qt/docks/data_preview.py`
- Polars viewer: `src/trigger_designer/qt/models/polars_table_viewer.py`
- Canvas: `src/trigger_designer/qt/node_base.py`, `src/trigger_designer/qt/node_editor_colors.py`
- Theme hooks: `src/trigger_designer/resources/qt/themes/base.qss`, `src/trigger_designer/qss/_style.scss`
- Icons: `src/trigger_designer/qt/resources.json:98-105`
- Visual preview: [`design_system_preview.html`](design_system_preview.html)
