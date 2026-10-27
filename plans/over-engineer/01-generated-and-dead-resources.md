# 01 — Generated and dead resources (biggest cut)

Paths relative to `src/trigger_designer/` unless noted. Runtime theming is `resources/qt/themes/base.qss` + theme JSONs (`theme_manager._base_qss`). `qss/_style.scss` and `qss/_variable.scss` stay (AGENTS.md / DESIGN_SYSTEM.md require them to agree with base.qss).

## Batch A — zero importers, no replacement (~14,500 lines) — risk low

1. `delete:` legacy stylesheet sources, 0 references in src/tests/scripts/spec (only `docs/plan/00-codebase-brief.md` and `examples/example_test/main.py` mention them):
   - `qss/QDarkStyle.qss` (2215), `qss/_my_style.scss` (2214), `qss/darkstyle.qss` (1627), `qss/blender_style.qss` (185), `qss/blender_style_ascent.qss` (89), `qss/blender_style_ascent copy.qss`, `qss/nodeeditor.qss` (83), `qss/nodeeditor-dark.qss` (40), `qss/nodeeditor.styl`, `qss/main.scss` (imports nonexistent `_variables`/`_styles`), `qss/nodestyle.qss`.
2. `delete:` `qss/nodeeditor_dark_resources.py` (516) and its byte-identical twin `resources/nodeeditor_dark_resources.py` (516). 0 importers.
3. `delete:` `resources/rc_icon.py` (3673), `resources/rc_uicon.py` (3671). 0 importers.
4. `delete:` `examples/example_test/` (loads `qss/nodestyle.qss`, not referenced by pyproject/spec). Leave it only if you keep `nodestyle.qss`.

Steps: `git grep -nw` each filename once more, `git rm`, delete mention lines in `docs/plan/00-codebase-brief.md`. Verify `trigger.spec` datas (lines ~64-76) do not list `qss/`. Tests: none touch these. Smoke launch.

## Batch B — duplicated icon path (~2,520 lines) — risk medium

`native/reuse:` `resources/icons_rc.py` (2493 lines compiled QRC) + `resources/icons.qrc` + `rsm.get_icon_path` + the QRC branch of `_get_action_icon` (`qt/helpers/context_menu_mixin.py:65-77`). The same SVGs resolve through `ResourceManager.get(icon_id)` (`resources.json` `node_*` keys), which `_get_action_icon` already falls back to (line 72).

Steps:
1. Confirm every node icon has a `resources.json` key (loop over registered nodes in `nodes/__init__.py` `_LAZY_NODE_SPECS`, check `icon` value exists).
2. Make `_get_action_icon` always call `rsm.get(icon_id)`.
3. Delete `icons_rc.py`, `icons.qrc`, `get_icon_path` (18 lines), the `icons_rc` import in `main.py` (~:245).
Tests: `tests/ui/test_context_menu_dev_actions.py`, `tests/ui/test_theme_icons.py`.

## Batch C — oversized auto-generated rc blob (up to ~11,000 lines) — risk medium, confidence medium

`shrink:` `qt/darkstyle_rc.py` (11,383 lines, PyQt5-era compiled resources) imported at `main.py:~244` only to register `:/qss_icons/...`. Referenced: `problems_dock.py:76,85`, `config_widgets.py:896,1000,1006` (copy, arrow_down, arrow_up, arrow_right) plus ~97 `url(:/qss_icons...)` refs in `base.qss`.

Steps:
1. `grep -o ":/qss_icons/[^)\"']*" resources/qt/themes/base.qss | sort -u` plus the Python refs → exact used set.
2. Ship only those PNGs (or recolored SVGs via `theme_icons`) and register a tiny rc, or load by file path. Keep other icons that might be useful in future. or May be use a entirely different library for icons like qt-material-icons or any other library with icons...
3. Delete `darkstyle_rc.py`.
4. Visual check: checkboxes, combo arrows, spin buttons, dock icons in light and dark themes.
Tests: `tests/ui/` full run plus manual screenshot comparison.

## Batch D — small resource_manager cleanup (~45 lines) — risk low

`qt/resource_manager.py`: delete `load_theme()` (55-68, labelled deprecated, 0 callers), the unreachable `mode == "pil"` branch (`resources.json` modes are only rb/qimg/qpixmap; this also removes the sole `PIL` import there, see 06), the ~15-line commented reader block (~152-168), `__getattr__` (~122-125) after `git grep -n "rsm\.\w*[^(a-z_]"` shows 0 attribute-style uses. Remove six unused `resources.json` keys (`icon_details`, `icon_apply`, `icon_chevron_first/prev/next/last`) and their SVGs under `resources/qt/images/ui` after a grep (also check no `f"icon_{...}"` construction). Test: `tests/ui/test_theme_icons.py`.
