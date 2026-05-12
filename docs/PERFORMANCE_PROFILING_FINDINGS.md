# TriggerEditor Performance Findings

This document captures the profiling results, the fixes already applied, and the patterns to reuse when optimizing other nodes.

## Profiling Setup

- Session profiler: `python scripts/profile_app.py`
- Visual report: `snakeviz profiles/latest.prof`
- Sampling profiler: `scripts\run_pyspy.bat`

Relevant implementation:

- `scripts/profile_app.py`
- `scripts/run_pyspy.bat`

## Baseline vs Latest

Compared profiles:

- Baseline: `profiles/profile_20260508_193836.prof`
- Latest: `profiles/profile_20260512_124233.prof`

Observed totals:

| Metric | Baseline | Latest | Change |
| --- | ---: | ---: | ---: |
| Total profiled time | 268.47s | 123.58s | -53.97% |
| Function calls | 2,693,078 | 1,520,149 | -43.55% |

## Fixes That Helped

### 1. Lazy loading heavy node modules

Problem:

- `trigger_designer.qt.widgets.nodes.__init__` eagerly imported every node module.
- This pulled in heavy transitive imports at startup, especially `matplotlib`, `pandas`, and expensive file-input dependencies.

Measured effect:

| Hotspot | Baseline | Latest |
| --- | ---: | ---: |
| `qt/widgets/nodes/__init__.py::<module>` | 39.56s | 9.79s |
| `qt/widgets/nodes/Report/graph.py::<module>` | 31.26s | 0.00s |
| `qt/widgets/data_preview_window.py::<module>` | 15.41s | not present |

Pattern to reuse:

- Keep lightweight metadata in the registry.
- Import the real module only when `get_class_from_opcode()` is called.
- For node palette and menus, registry entries only need:
  - `node_code`
  - `node_type`
  - `node_title`
  - `icon`

When adding a new expensive node:

1. Add it to the lazy registration map in `qt/widgets/nodes/__init__.py`.
2. Keep module-level imports minimal.
3. Move optional libraries into feature entry points where possible.

### 2. Breaking GroupBy self-triggered reevaluation

Problem:

- `GroupByContent.apply_groupby()` emitted `evaluate`.
- The node connected that signal to `onInputChanged()`.
- During file load and graph propagation, this created repeated reevaluation.

Measured effect:

| Hotspot | Baseline | Latest |
| --- | ---: | ---: |
| `groupby.py::processInputs` | 394 calls / 13.31s | 3 calls / 0.03s |
| `groupby.py::apply_groupby` | 394 calls / 13.30s | 3 calls / 0.02s |

Pattern to reuse:

- Separate internal recompute from UI-triggered recompute.
- Internal graph evaluation should not emit a signal that re-enters the same node.
- UI actions can emit downstream updates, but internal refresh paths should stay silent.

When optimizing expensive nodes:

Check for these loops first:

- `processInputs()` calling a method that emits a node signal
- `deserialize()` rebuilding UI and causing `itemChanged` storms
- `onInputChanged()` calling `eval()` even when the node is already recomputing

### 3. Reducing logging overhead

Problem:

- Every log message triggered filter rebuilding and full text rendering.
- Standard output and log file streams flushed on every write.

Measured effect:

| Hotspot | Baseline | Latest |
| --- | ---: | ---: |
| `logging_dock.py::log` | 3700 calls / 1.85s | 346 calls / 0.05s |
| `main.py::write` | 3490 calls / 4.33s | 646 calls / 0.25s |

Pattern to reuse:

- Batch log filtering on a timer.
- Render incrementally rather than rebuilding the full document.
- Flush only on line boundaries unless real-time output is required.

## Second Round Follow-Up

The next pass focused on the remaining import cost, edge geometry churn, and log rendering overhead.

### 4. Full lazy registration for registered node modules

Implementation:

- `qt/widgets/nodes/__init__.py` now registers all known node modules lazily.
- The real module is imported only when a node class is resolved.

Observed effect:

- Fresh import of `trigger_designer.qt.design_window` dropped to about `0.95s` in an offscreen process.
- `pandas` and `matplotlib.pyplot` stayed out of `sys.modules` during that import.

Pattern to reuse:

- For node packages, keep the registry metadata static and cheap.
- Do not import the implementation module to build the node palette.

### 5. Edge path caching

Important finding:

- The `calcPath` hotspot was not primarily caused by scene restore.
- Profile callers showed most time came from repeated `shape()` and `boundingRect()` queries in `QDMGraphicsEdge`, especially during normal view activity.

Implementation:

- Added an app-owned `CachedGraphicsEdge` in `qt/performance_scene.py`.
- The expensive path calculator now runs only when edge endpoints or edge type change.
- Repeated `boundingRect()` or `shape()` queries reuse the cached path.

Validation:

- Repeating `boundingRect()` 50 times on the same edge executed the underlying path calculator only once.
- After changing the destination point, the next `boundingRect()` triggered one new calculation, confirming correct invalidation.

Pattern to reuse:

- If a Qt graphics item computes expensive geometry, cache the geometry and invalidate only on state changes.
- Optimize the geometry source, not just the repaint wrapper.

### 6. Incremental log rendering

Implementation:

- `LoggingDock` now appends new visible entries during normal log flow.
- Full HTML rebuilds are reserved for filter changes, window switches, or truncation events.

Validation:

- After the initial refresh, subsequent `log()` calls kept `_full_refresh_required = False` and appended incrementally.

Pattern to reuse:

- For QTextEdit-based consoles, append deltas when filters are unchanged.
- Reserve full rebuilds for state transitions, not steady-state event flow.

## Remaining Major Hotspots

After the first round of fixes, the main costs were:

| Hotspot | Latest cumtime |
| --- | ---: |
| `main.py::main` | 95.93s |
| built-in `exec` | 93.05s |
| importlib loading | 28.49s |
| `qtpy.enums_compat.promote_enums` | 11.46s |
| `qt/main_window.py::<module>` | 11.14s |
| `qt/design_window.py::<module>` | 10.19s |
| `core/node_configuration.py::<module>` | 9.92s |
| `qt/widgets/nodes/__init__.py::<module>` | 9.79s |
| `qt/widgets/nodes/InOut/file_input.py::<module>` | 8.91s |
| `node_graphics_edge_path.py::calcPath` | 7.14s |

Interpretation:

- App-owned startup costs were largely reduced by lazy node registration.
- The edge-path hotspot is best treated as a geometry caching problem.
- Qt compatibility work in `qtpy` is still visible but is less directly controllable.

## Optimization Playbook For Expensive Nodes

When a node becomes expensive, inspect it in this order:

### A. Import-time work

Look for module-level imports of:

- `pandas`
- `matplotlib`
- database clients
- file readers
- anything that loads plugins, schemas, or Qt widgets eagerly

Preferred fix:

- Move those imports inside the method that first uses them.

### B. Reevaluation loops

Look for:

- `evaluate.emit()` inside data-processing methods
- `itemChanged` or `currentTextChanged` handlers that immediately call `eval()`
- `deserialize()` rebuilding widgets without blocking signals

Preferred fix:

- Add explicit silent/internal recompute paths.
- Block widget signals during state restoration.

### C. UI rebuild cost

Look for:

- full table rebuilds on every keystroke
- full HTML or QTextEdit reset on every event
- repeated scene relayout or repaint during bulk restore

Preferred fix:

- batch updates
- append deltas instead of rebuilding
- suspend viewport updates during bulk load

### D. Edge geometry churn

If profiling shows many calls to edge/path or socket paint methods:

- inspect callers of `calcPath`, `shape`, and `boundingRect`
- cache computed geometry if callers are mostly paint or layout queries
- only optimize bulk restore separately if callers actually point to deserialization paths

## Practical Checklist Before Merging An Optimization

1. Capture a `before` profile.
2. Make one focused change.
3. Re-run the same workflow profile.
4. Compare:
   - total time
   - call counts
   - the touched function's cumulative time
   - any new hotspot that became visible
5. Keep the change only if the profile moves in the right direction.

## Notes For Future Work

- Re-profile after the second round to see what becomes dominant next.
- If `file_input.py` still appears high in cumulative startup time, inspect its module-level imports and helper initialization next.
- If edge work is still visible after caching, inspect wheel/mouse move handlers and scene item queries next.
- Keep using the baseline-vs-latest comparison workflow before and after each optimization.
