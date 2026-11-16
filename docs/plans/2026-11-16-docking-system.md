# Plan: A free-form docking system (drag anywhere, with drop indicators)

Status: proposed (plan only, nothing implemented) · Branch: `docks` · Date: 2026-11-16

## Implementation status (2026-11-16)

Done: Phase 0 gates 1, 2, 5 (API-level), Phases 1-3, theme part of Phase 4, docs. Full suite green (4081 passed).
Deviation: panels are placed from a `LayoutSpec` placement list and persisted as QtAds' own state blob (not a JSON tree); on startup the default layout is applied first and the saved blob restored over it, because QtAds `restoreState` on a never-placed host reports success but places nothing.
Also done: Config's 300px minimum is enforced by the splitters (`MinimumSizeHintFromContentMinimumSize`), dragged panel sizes persist across restarts (tested), off-screen floating panels are pulled back (`screen_guard.py`, on restore and when a screen is removed), tab chrome (close buttons only while floating, no title eliding, thin separators, active/hover states), `trigger.spec` lists `PySide6QtAds` (a PyInstaller build contains the extension and the executable starts offscreen). Floating panels were confirmed working outside the window by hand.
Not done / not verified: "Classic" preset in the Window menu, tab context menu "Move to", double-click-to-maximize, per-panel shortcuts, macOS/Linux (see the OS-support notes).

## 1. Goal

Every panel except the Nodes palette can be dragged to any place in the window, split against any other panel, tabbed with any other panel, floated, closed and reopened. While a panel is dragged, the app shows where it can land, as VS Code, Blender and Alteryx do.

**Acceptance scenario (the one that fails today).** The user can build this layout with the mouse alone:

```
┌───────────────────────────────────────────────┐
│  Nodes palette (fixed, full width)            │
├────────────┬──────────────────────────────────┤
│            │  Workflow canvas (MDI tabs)      │
│  Node      ├──────────────────────────────────┤
│  Config    │  Logs | Data Preview | Run Hist. │
│  (full     │                                  │
│  height)   │                                  │
└────────────┴──────────────────────────────────┘
```

The layout survives a restart, and *Reset Layout* returns to the default.

## 2. Why the current system cannot do it

The window is a `QMainWindow` with `QDockWidget`s (`qt/helpers/main_window_ui_mixin.py:286-330`, `qt/layout_state.py:239-271`). Qt's dock model has hard limits:

| Limit | Effect |
|---|---|
| Docks attach only to the four window edges around **one** central widget. The central widget (`QMdiArea`) can never be split. | You cannot drop a panel *beside or below the workflow* inside the right-hand column. |
| Four corners, each owned by one edge (`setCorner` is never called). | Config (left) and the bottom area fight over the bottom-left corner. This is why "left column completely filled" does not happen. |
| Drop feedback is Qt's private rubber band (`QDockAreaLayout`). Its colour, shape and zones cannot be changed from Python. | No VS Code-style overlay is possible. |
| `saveState` is an opaque blob tied to the dock `objectName`s. | Layouts cannot be inspected, migrated or tested beyond "did it restore". |
| Nesting is brittle (`setDockNestingEnabled` is called twice, `main_window.py:135,175`) and `dock_chrome.py` / `dock_resize_cursor.py` exist only to work around Qt's private chrome. | Two helper modules and their tests are pure workaround code. |

A small patch (e.g. `setCorner`) would fix the single scenario above but not the real problem. Hence a replacement, not a tweak.

## 3. Options considered

| | A. **Qt Advanced Docking System** (`PySide6-QtAds`) | B. In-house docking framework | C. Patch `QMainWindow` |
|---|---|---|---|
| Arbitrary split tree, tabs, float | Yes | We build it | No (limits above) |
| Drop overlay (area crosses + translucent target rect) | Yes, built in, themable by QSS | We build it (~600 LOC + tests) | No |
| Auto-hide sidebars, perspectives | Yes | Later, at our cost | No |
| Persistence | XML state, versioned | Our JSON tree (readable, testable) | Opaque blob |
| Risk | New native dependency; styling and frameless-window interplay need a spike | Most code and most bugs to own | Does not meet the goal |
| Licence | LGPL-2.1 (PySide6 is already LGPL) | Ours | n/a |
| Compatibility found | Wheel `5.1.1.1` is `cp310-abi3`, Windows build available, **pins `PySide6-Essentials==6.12.0` and `shiboken6==6.12.0`: exactly this project's pins**. Adds ~1.2 MB unpacked, none of the 39 MB Addons. | n/a | n/a |

**Recommendation: A, behind our own thin interface, with a gated spike (Phase 0).** If the spike fails any gate in §6 Phase 0, switch to B; the interface in §4 makes that a swap of one module, not a rewrite of the app.

## 4. Architecture

New package `src/trigger_designer/qt/docking/`. App code never imports QtAds directly.

```
docking/
  __init__.py       public API only
  panel.py          Panel: id, title, icon, widget, closable, default placement
  host.py           DockHost (Protocol): the interface the app uses
  ads_host.py       QtAds implementation of DockHost
  layouts.py        DEFAULT layout spec + presets, as data
  persistence.py    save / restore / migrate, versioned
  actions.py        View-menu actions, "Move panel to..." menu
  theme.py          QSS + overlay colours from the theme manager
```

`DockHost` (the seam between the app and the library):

```python
class DockHost(Protocol):
    def register(self, panel: Panel) -> None: ...
    def show_panel(self, panel_id: str) -> None: ...      # un-hide + raise tab
    def hide_panel(self, panel_id: str) -> None: ...
    def is_visible(self, panel_id: str) -> bool: ...
    def toggle_action(self, panel_id: str) -> QAction: ...
    def set_central(self, widget: QWidget) -> None: ...   # the MDI area
    def apply_layout(self, spec: LayoutSpec) -> None: ... # default / presets
    def save_state(self) -> bytes: ...
    def restore_state(self, blob: bytes, version: int) -> bool: ...
    visibility_changed: Signal(str, bool)
```

Decisions:

1. **Nodes palette is not a dock.** It becomes a fixed strip above the dock host (a plain widget in the window's central layout), so it cannot be moved, closed by drag or covered. This satisfies "keep the nodes dock fixed" without feature flags.
2. **The workflow canvas (`QMdiArea`) is the dock manager's central widget.** Panels can be docked left, right, above and below it, and the central area keeps taking the leftover space.
3. **Panels become plain widgets, not `QDockWidget` subclasses.** `ConfigDock`, `LoggingDock`, `DataPreviewDock`, `RunHistoryDock` keep their class names and attributes (`window.loggingDock`, ...) to limit churn (≈100 references, listed in §7), but their base class changes from `QDockWidget` to `QWidget`, and a `Panel` wraps each one. The `show()` / `raise_()` / `toggleViewAction()` calls now go through a small compatibility shim on the wrapper so call sites change later, in one pass, not in this branch's first commits.
4. **The default layout is data.** `layouts.py` describes it as a tree (`Split(horizontal, [Panel(config), Split(vertical, [Central, Tabs(logs, preview, history)])])`). The same format is the persisted format, so Reset Layout and Restore share one code path.
5. **Layout persistence** is versioned: `layout/state_version = 3`. The old `QMainWindow.saveState` blob (version 2) cannot be converted; it is ignored once and the new default applies (documented in release notes).
6. **Theming.** All dock chrome (tab bar, title bar, splitter handle, overlay) is styled from `resources/qt/themes/base.qss` + `qss/_style.scss` through `objectName`s, per `AGENTS.md`: no inline `setStyleSheet`, hover/pressed restated per `objectName`, 1px constant borders, icon-first buttons with tooltip + `accessibleName`. The old `QDockWidget` / `QMainWindow::separator` rules are replaced by the QtAds ones (`ads--CDockAreaWidget`, `ads--CDockWidgetTab`, `ads--CDockSplitter`, `ads--CDockOverlay*`).

## 5. The drag experience

While a panel (or a whole tab group) is dragged:

1. **Targets appear** where the pointer is, not at fixed places: a small cross of five zones over the panel group under the pointer (centre = tab into it; top/bottom/left/right = split against it), and a second set of four edge markers on the window border for "dock to the whole window edge".
2. **A translucent fill previews the result** (accent colour, 30% opacity, 1px accent border) over the area the panel would occupy, so the user sees the new shape before releasing. This covers the "like Blender / VS Code" request.
3. **The canvas is a valid target too**, so "below the workflow" and "left of the workflow" work.
4. **Release** commits; **Esc** or releasing outside any target cancels and returns the panel to where it was. Dragging out of the window floats it.
5. **Drop is one history step** only for window-layout purposes; layout changes are not part of workflow undo (see Open question 5).

Extras in the same phase (cheap with the library, big for "natural"):

- Tab right-click: *Float*, *Move to ▸ Left / Right / Top / Bottom / Tab with ▸*, *Close*. This is the keyboard and precision alternative to dragging (accessibility).
- Double-click a tab: maximise the panel inside its area; double-click again restores.
- Closed panels are listed in **Window** menu with a check mark; the old shortcut `Ctrl+Shift+D` keeps toggling Data Preview.
- Minimum sizes are respected: Node Configuration keeps `minWidth 300` (`DESIGN_SYSTEM.md`), so a drop that would squeeze it below that is shown as a smaller target and refused.

## 6. Phases

Each phase is its own commit series, ends green, and is revertible.

### Phase 0 — Spike (gate, ~½ day, throwaway branch of this branch)

A script in `scripts/` that builds the Acceptance layout with `PySide6-QtAds` on top of the real `QMdiArea`. Pass/fail gates:

1. `import PySide6QtAds` works on Python 3.14 + PySide6 6.12.0 (both pinned), under `uv run`.
2. The target layout can be reproduced by mouse and by API.
3. The drop overlay shows and can be coloured from our theme tokens (dark and light).
4. Frameless main window (`window_chrome.py`) still moves, resizes and snaps; floating panels get a usable frame (try native title bar vs QWidget title bar flags).
5. `QMdiArea` as central widget keeps tabbed view, context menus and `Ctrl+Tab`.
6. PyInstaller one-folder build contains the QtAds binaries and starts.
7. Heavy panels (Data Preview table, Logs) survive hide/show and reparent without losing state.

**Any gate failing → fall back to option B** and revise this plan; do not start Phase 1 first.

### Phase 1 — Docking package and fixed Nodes strip

- Add dependency `PySide6-QtAds==5.1.1.1` (exact pin, like its neighbours), update `uv.lock`, add to `main.spec` hidden imports/binaries.
- Create `qt/docking/` (§4) with `DockHost` + `ads_host.py`.
- Move the Nodes palette out of the dock system into a fixed strip. Keep `NodesDock` name or rename to `NodesPalette` (see Open question 3).
- Tests: `tests/ui/test_dock_host.py` (register, show/hide, visibility signal, central widget).

### Phase 2 — Migrate the four panels

- `ConfigDock`, `LoggingDock`, `DataPreviewDock`, `RunHistoryDock`: base `QDockWidget` → `QWidget`; `setWindowTitle` calls move to `Panel.set_title` (the Config Dock title shows the selected node name: "Node Configuration (Duplicates)").
- Replace `createXxxDock` in `main_window_ui_mixin.py` with `Panel` registration; replace `updateWindowMenu` actions with `DockHost.toggle_action`.
- `raiseDiagnosticsDock` → `show_panel("logs")`.
- Delete `helpers/dock_chrome.py`, `helpers/dock_resize_cursor.py` and their tests once nothing uses them (QtAds owns tabs, separators, cursors).
- Remove both `setDockNestingEnabled` calls.
- Keep `ConfigDock.updateConfig(..., force=True)` and the undo wiring (`onHistoryRestored`) untouched: the Config Dock is still the editor and is still re-created on selection, per `AGENTS.md`.

### Phase 3 — Default layout and persistence

- `layouts.py`: default = the acceptance layout (Config full-height left; right column = canvas over the tabbed Logs / Data Preview / Run History). See Open question 1.
- `persistence.py`: save on close and on *Save Current Layout*; restore at start; `STATE_VERSION = 3`; graceful fallback to default on any parse error or missing panel (a restored layout never hides all panels or leaves the canvas without space).
- Off-screen floating panels are pulled back onto a visible screen on restore (multi-monitor unplugged case).
- Rewrite `layout_state.py:239-271` `apply_default_layout` to call `DockHost.apply_layout`. Keep `LayoutState` for geometry and session files (unchanged). Update `tests/unit/test_layout_state.py`.

### Phase 4 — Drag UX and theme

- Overlay colours, tab styling and splitter handles from tokens (§4.6); dark and light parity; verify with `tests/manual/style_demo.py`.
- Tab context menu, double-click maximise, *Move to ▸*.
- Window menu: panel check items + *Reset Layout* + (optional) layout presets (Open question 4).
- Min-size enforcement for Config (300).

### Phase 5 — Tests, docs, release notes

- UI tests (offscreen): build the acceptance layout by API, save, restore, assert tree equality; floating restore on a missing screen; hidden-panel restore; version-2 blob ignored.
- A QTest-driven drag test of one tab onto each overlay zone (centre/left/right/top/bottom/edge) asserting the resulting tree. If QtAds' overlay cannot be driven by synthetic events, keep a manual script and assert the API path instead (note it).
- Update `docs/guide/config-dock-and-preview.md` (layout section), `docs/DESIGN_SYSTEM.md` §8 (the "Layout" tree and dock chrome paragraph), `docs/guide/preferences.md`, `docs/internal/CHANGELOG.md`, `docs/release-notes/`.

## 7. Files that change

| Area | Files |
|---|---|
| New | `qt/docking/*`, `tests/ui/test_dock_host.py`, `tests/ui/test_dock_layout.py`, `scripts/dock_spike.py` |
| Rewritten | `qt/layout_state.py` (dock part), `qt/helpers/main_window_ui_mixin.py` (dock mixin + Window menu), `qt/docks/nodes_list.py` |
| Edited | `qt/main_window.py`, `qt/design_window.py` (2 refs), `qt/docks/node_config.py`, `logging_dock.py`, `data_preview.py`, `run_history_dock.py`, `resources/qt/themes/base.qss`, `qss/_style.scss`, `main.spec`, `pyproject.toml`, `uv.lock` |
| Deleted | `qt/helpers/dock_chrome.py`, `qt/helpers/dock_resize_cursor.py` |
| Tests updated/removed | `tests/unit/test_layout_state.py`, `tests/ui/test_dock_chrome.py` (removed), `tests/ui/test_dock_resize_cursor.py` (removed), `test_run_history_dock.py`, `test_data_preview_wiring.py`, `tests/e2e/test_undo_integration.py` |

Verify each phase with `uv run --project . ruff format <files>`, `uv run --project . ruff check <files>`, then the focused `pytest` files above, then the whole `tests/ui` suite offscreen.

## 8. Risks

| Risk | Mitigation |
|---|---|
| QtAds is a C++ wheel; a PySide6 bump needs a matching QtAds release (it pins `==6.12.0`). | It already matches today's pin; the `DockHost` seam makes a swap to option B possible; note the coupling next to the pin in `pyproject.toml`. |
| Frameless window + floating panels on Windows. | Phase 0 gate 4. |
| Panels reparent when moved; heavy widgets may repaint or lose focus. | Phase 0 gate 7; panels already rebuild from model state. |
| Users with a saved v2 layout lose it once. | Documented in release notes; Reset Layout and the default are good. |
| Config Dock rebuilds while being dragged. | Rebuild is driven by selection, not geometry; drag does not change selection. Covered by a test. |
| Dock chrome violates `DESIGN_SYSTEM.md`. | Theming through tokens only; §§1-7 re-checked in Phase 4. |

## 9. Out of scope

- Per-workflow layouts (layout stays one app-wide setting).
- Auto-hide edge sidebars (the library supports them; enable later if wanted).
- Moving the Nodes palette or turning it into a floating panel.
- Putting individual workflow tabs (MDI) into docks or a second window.
- Docking inside floating windows across multiple monitors beyond what the library gives.

## 10. Assumptions and open questions

1. **Default layout.** I assumed the layout the user described becomes the new default (Config full-height left; canvas above Logs / Preview / History on the right). The old default (Config left, bottom panels full width) stays reachable as a preset.
2. **Library vs in-house.** I assumed a vetted library (QtAds, LGPL) is acceptable, given PySide6 is already LGPL, in exchange for a fraction of the code.
3. **"Nodes dock fixed"** means: always at the top, full width, not draggable, not closable, not floatable. Not a floating-capable panel with the move feature switched off.
4. **Layout presets.** The old design deliberately has one auto-saved layout and no named presets. I kept that, adding only a short built-in list (Default, Classic) in the Window menu, not user-named layouts.
5. **Layout is not undoable** and never enters the workflow `QUndoStack` (window chrome, not document state).
6. **Existing saved layouts are dropped once** (the old blob cannot be converted).
7. **Floating panels** are allowed, rejoined by dragging back or via *Move to*; they close with the app.
8. **Tabs with panels:** any panel may tab with any other (including Node Configuration with Logs). No panel is pinned to an area.
9. **Close behaviour:** closing a panel only hides it (state kept); reopen from **Window**. Config stays closable.
10. **Platform:** Windows first (the dev and build target); macOS/Linux behaviour follows the library and is not tested in this branch.
