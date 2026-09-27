# Node labels & groups

Floating single-line labels on nodes and visual node groups. Both are
implemented by the `qtpy-nodeeditor` package (`Group` in
`nodeeditor.node_group`, labels on `nodeeditor.node_node.Node`); this app
only wires them into its menus, Config Dock, edges, and undo.

## Labels

- **Canvas:** click the textbox above a node to edit. `Enter` commits,
  `Escape` reverts, focus-out commits. Single-line is enforced.
- **Node menu:** `Set Label...` (empty text removes it). Single node:
  checkable `Show Label`. Multi-select: `Show Labels` / `Hide Labels`
  (showing skips nodes with no text — empty labels are always hidden).
- **Config Dock:** `Label` section above each node's controls, debounced
  (~300ms) like other text inputs.
- **Persistence:** `label_text` / `label_visible` / `label_offset` travel
  with `Node.serialize()`; old `.tds` files load label-less.
- **Undo:** one `"Node label changed"` / `"Node(s) label shown|hidden"`
  step per edit or burst.

## Groups

- **Create:** select 2+ nodes → right-click `Group Selected Nodes`, or
  press `G`. Drag nodes onto a group to drop them in.
- **Header (title bar) only** is interactive: drag to move (children
  follow), `+`/`−` or `C` to collapse/expand, double-click to rename,
  right-click for rename / color / ungroup / delete.
- **Shortcuts:** `G` group, `U` / `Shift+G` ungroup, `C` collapse.
  Ignored while typing in a text field.
- **Detach:** right-click a grouped node → `Detach from Group`.
- **Delete:** `Del` on a group header deletes the group **and** its
  children; `Ungroup` keeps the nodes.
- **Collapse** hides children and internal edges; external edges reroute
  to stub rows on the box. Positions/sizes are never altered.
- **Copy rule:** copy the header to copy the whole group (children +
  internal edges included).
- **Undo/files:** group ops stamp history; `Scene.serialize()` stores
  `groups` (v2). The old hand-rolled `NodeGroup` was never serialized,
  so there is nothing to migrate.

## Notes for contributors

- `TriggerEdge.updatePositions()` (`qt/performance_scene.py`) keeps its
  socket math, caching, and bulk-load deferral, plus the upstream
  collapsed-group branch (stub routing, hidden internals). If upstream
  changes `Edge.updatePositions`, re-check that branch.
- The Edit-menu group actions come from `NodeEditorWindow` via `super()`
  — do not re-implement them in the app menus.
- `Shift+G` is reserved for Ungroup; do not bind it in `design_window.py`.
- The Config Dock's canvas→field label sync is a Python closure owned by
  the node: `updateConfig` disconnects it on every rebuild
  (`_disconnect_label_sync`), or stale closures hit deleted editors.
