# Logs dock

The Logs dock is one panel for the active design window: the running commentary
and the list of nodes with problems. It is a view, not a store.

## Overview

Each design window owns a `DiagnosticFeed` (`window.diagnostics`). The feed holds
log lines *and* problem records in one order; the dock paints whichever document
is active and keeps no records of its own. Switching windows repoints the dock at
another feed.

A problem record wraps the whole `NodeError`, so code, Fix, Caused-by, technical
text and fingerprint survive unflattened. The node's badge still reads
`NodeErrorState.by_source`; the feed is a copy pushed after it, never a second
authority.

## Features

- One list: log lines and node problems interleaved by insertion order.
- Counted filter strip: `All`, `N Errors`, `N Conv`, `N Warnings`, `N Messages`.
  The chip is both the filter and the count; there is no tab-title count.
- `Last Run` / `Configuration`: split problem records by origin. Log lines appear
  in both modes, because a log line has no phase.
- `Ctrl+F` search over message, code, title, detail and node name, debounced
  300 ms.
- Click a problem row to select its node and centre the canvas; Return does the
  same from the keyboard.
- Double-click or Space expands a problem row to the code, Fix, Caused-by and
  (with the toggle on) the first technical line.
- `Copy details` copies the selected problems, or every problem the filter shows.
- `Clear` empties log lines only. A live problem leaves when its node goes clean.
- `Follow new entries` keeps the newest record in view.
- Can be closed and reopened from Window ▸ Logs; a failed Run raises it with
  `Last Run` and `Errors` selected.

### Dock chrome

The dock shares the bottom tab bar with Data Preview and Run History. While it is
a tab it hides its own title bar; dragging the tab out pops the panel out with a
frame and re-docks on drop.

## Usage

```python
# From a design window: appends a log record to this document's feed.
self.logInfo("General information")
self.logWarning("Warning message")
self.log("INFO", "Custom message")
```

Node errors do not go through `log()`: `NodeErrorState.set` pushes the structured
record straight into `window.diagnostics`, and `log_new` writes only to the
session log file.

## Implementation details

| Part | Role |
|---|---|
| `helpers/diagnostic_feed.py` | `DiagnosticFeed` and `DiagnosticRecord`: one order, `seq`, immutable `first_seen`, per-kind retention, `changed` signal. |
| `helpers/diagnostic_feed.py` | Category (`Errors`, `Conv`, `Warnings`, `Messages`) is derived from kind, severity and the `TD-TYP-` prefix, never stored. |
| `docks/logging_dock.py` | `LoggingDock` (strip, mode, search, actions), `DiagnosticModel` (flat `QAbstractItemModel`), `DiagnosticDelegate` (all row painting and colour). |
| `design_window.py` | Owns the feed, sets `scene.diagnostics`, and is the only place `log()` appends. |
| `node_runtime.py` | `NodeErrorState.diagnostics_feed()` reads `scene.diagnostics`; no widget walk. |

### Memory

- 1,000 log records per document; the oldest are dropped past the cap.
- Problem records are never trimmed by that cap and never deleted by Clear.
- A problem record leaves when node state drops it, or when the next Run starts
  (run-origin records).
- Nothing is left in place of a fixed problem; the session log file is the trail.

### Performance

- The feed emits `changed`; the dock coalesces to a 0 ms timer and rebuilds the
  projection list.
- The model resets only when the identity sequence changes; a payload-only update
  emits `dataChanged`.
- Selection and scroll are restored by record id after a reset.
- No HTML is generated anywhere in the path.

## Related docks

The Data Preview dock (`docs/DATA_PREVIEW_DOCK_README.md`) shares this tab stack.
Both follow the active document and drop its state in `onDesignWindowClose`.
