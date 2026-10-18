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

## Third Round: Canvas Interactivity

A workflow of 105-120 nodes made panning, zooming, dragging and rubber-band
selection unusable. The work is measured with `scripts/benchmark_canvas_perf.py`,
which drives the real `TriggerSubWindow` under the offscreen Qt platform and
reports a median per operation together with paint counts (a frame that gets
cheaper by painting twice as often shows up as time down and paints up).

Command used for the numbers below:

```bat
.venv\Scripts\python.exe scripts\benchmark_canvas_perf.py --nodes 120 --repeats 5 --pan-steps 60 --drag-steps 45 --label paired_after
.venv\Scripts\python.exe scripts\benchmark_canvas_perf.py --compare scripts/benchmark_results/canvas_paired_baseline_*.json scripts/benchmark_results/canvas_paired_after_*.json
```

### 7. Interaction plumbing

Problem:

- Every mouse move re-scanned a 248-unit square of the scene to find the nearest
  socket for CTRL-snapping, then repainted the whole viewport.
- Every mouse move walked every node in the scene, and `Node.setPos` rebuilt all
  of that node's edge paths a second time after Qt had already moved the node.

Implementation:

- `QDMGraphicsView.DEFAULT_VIEWPORT_UPDATE_MODE = MinimalViewportUpdate` and one
  tracked `_highlighted_socket` that repaints only the two sockets involved.
- `ItemSendsGeometryChanges` plus `itemChange` refresh exactly the moved node's
  edges, replacing the per-move scene scan.
- `Node.setPos` no longer duplicates the `calcPath` loop.

### 8. Paint cost

Problem:

- `NoIndex` forced every culling pass, hit test and rubber-band query to walk the
  whole item list.
- The grid drew each line as an individual `drawLine` with antialiasing on, and
  the project's node class recomputed `shape()` on every repaint.

Implementation:

- `BspTreeIndex` is back (the `NoIndex` workaround addressed QTBUG-18021, fixed in
  Qt 5.7).
- Grid levels below `MIN_GRID_SPACING_PX` are dropped, remaining lines are batched
  into two `drawLines` calls, antialiasing is off for them.
- `TriggerGraphicsNode.shape()` caches its `QPainterPath`; the transparent
  state ring and the 24px status sprite are skipped when they cannot be seen.

### 9. Level of detail at low zoom

Below `QDMGraphicsScene.DETAIL_LOD_THRESHOLD` (0.5) the scene asks every item to
drop its fine detail: content widget, floating label and socket circles. At that
size none of them is legible or aimable. `drawBackground` broadcasts only when
the state flips, and `Node.__init__` re-pushes it onto sockets and the content
proxy, which are built after the node has already joined the scene.

### Measured effect

Paired runs, same machine, same session (`canvas_paired_baseline_20261018_205924.json`
vs `canvas_paired_after_20261018_210017.json`):

| Operation (120 nodes, 119 edges) | Before ms | After ms | Speedup |
| --- | ---: | ---: | ---: |
| zoomed out, pan (60 steps) | 2238.56 | 708.00 | 3.16x |
| zoomed out, drag a node (45 steps) | 2135.12 | 191.41 | 11.15x |
| zoomed out, rubber band (45 steps) | 2388.14 | 606.27 | 3.94x |
| zoomed out, Ctrl+wheel zoom | 1085.94 | 166.03 | 6.54x |
| zoomed out, viewport repaint | 420.45 | 129.32 | 3.25x |
| zoomed out, 600x600 item query | 470.55 | 156.19 | 3.01x |
| 1:1, pan | 1069.88 | 689.67 | 1.55x |
| 1:1, drag a node | 1046.28 | 373.52 | 2.80x |
| 1:1, rubber band | 1176.39 | 670.15 | 1.76x |
| 1:1, 600x600 item query | 512.21 | 460.89 | 1.11x |
| **total (sum of medians)** | **13659.06** | **4631.74** | **2.95x** |

The paint counts are identical on both sides for every operation, so the time is
frame cost and not skipped frames. Run-to-run noise on this machine is +-10-25%
(uniform across operations, so re-check with a same-session paired pair before
believing a single-run difference).

Pattern to reuse:

- Wrap the entry points (paint, mouse move) with counters so a faster frame cannot
  hide behind a higher frame rate.
- Let Qt tell you what moved (`itemChange`) instead of scanning the scene.
- Cache geometry on the item and invalidate on state change, not per paint.
- Drop detail the user cannot see at the current zoom, but make the decision in
  one place and broadcast it only on flips.

### 10. Empty draw batches in `drawBackground`

`drawBackground` built two lists of grid lines and painted them with
`painter.drawLines(*lines_dark)`. PyQt6 has no zero-argument overload of
`drawLines`, so an empty batch raised `TypeError` - and the batch empties exactly
when the minor grid lines are dropped, i.e. as soon as the user zooms out far
enough to take in a graph. The lines are now painted through the sequence
overload, which accepts an empty list, and `tests/ui/test_canvas_grid_render.py`
covers the zoomed-out (empty minor batch), grid-off and LOD paths.

Pattern to reuse:

- A `*args` expansion of a list into a Qt overload is a per-item call with a
  different failure mode from the list overload; prefer the list form.
- Guard the branch that can produce an empty batch, and pin it with a test that
  asserts the branch is actually taken.

## Fourth Round: Making The Optimizations Safe

Three of the round-three changes were correct about cost and wrong about what the
user sees. They shipped broken, the user reported two screenshots, and the fixes
below are what make the speedups usable.

### 11. A level of detail that hid the whole node

Below 0.5 scale the scene asked every node to hide its content widget. That
widget *is* the node: `QDMIconGraphicsNode.paint` is commented out and each node
class hands its content widget a pixmap (`self.node.rsm.get(self.node.icon)`)
that contains the entire card artwork - border, fill and icon. Hiding it erased
every node from the canvas and left only the edges, which is what "when I zoom
out all the nodes just disappear" looked like.

The node now keeps a cheap stand-in: `TriggerGraphicsNode._paintLowDetail` blits
that same pixmap into the node's rect with smoothing off. One scaled blit per
node replaces a full `QGraphicsProxyWidget` render, so the zoomed-out win
survives while the graph stays readable.

`node_icon_content_widget.py` now also stores the pixmap on the widget
(`self.icon`, alongside the `QLabel` it already puts it in), so the node does not
have to walk its widget tree; `_findContentPixmap()` is the fallback for content
classes that build their own label, and `apply_theme` drops the cache.

Pattern to reuse:

- A level of detail must replace the detail with something cheaper that still
  carries the same information. Hiding it is not a cheaper node, it is a missing
  node.
- Find out what actually draws a thing before hiding it. Here the answer was
  "one pixmap inside a proxy widget", not "the graphics item's paint".

### 12. Deciding the level of detail inside the paint pass

`applyDetailLod` ran from `drawBackground`, i.e. while Qt was painting the frame.
Hiding an item there is not allowed: the viewport update region was computed from
the item being visible, so the pixels it had already claimed stayed on screen, and
the next scroll dragged those ghosts along. That is the smeared, translated cards
in the second screenshot.

The decision now happens before the scene paints:

- `QDMGraphicsView._syncDetailLod()` compares the current scale with
  `DETAIL_LOD_THRESHOLD` and asks the scene to flip if needed.
- It is called from `applyZoom` (the Ctrl+wheel path, so the flip lands before the
  next frame) and from `paintEvent` before `super().paintEvent` (the net for any
  other transform change: restored zoom, `fitInView`, direct `scale()`).
- `QDMGraphicsScene.updateDetailLod` / `setDetailLod` are the scene side and are
  documented as "not from inside a paint pass".
- When the flip happens in `paintEvent`, the viewport is repainted once more so
  the area the hidden items occupied is cleared in that pass.

A side effect worth having: `QGraphicsView.render()` (exporting or thumbnailing a
workflow) no longer walks the LOD path, so a rendered image always has full
detail. The visible canvas is painted through `paintEvent`, so the user still gets
the cheap path.

Pattern to reuse:

- Never change item state (visibility, geometry, parent) from `drawBackground` or
  `paint`. Qt has already fixed the update region for that frame.
- Drive derived display state from the input that changes it (zoom) and keep a
  pre-paint check as the net, instead of deriving it during paint.

### 13. Viewport update mode

Round three switched `FullViewportUpdate` to `MinimalViewportUpdate`. The old
mode was upstream's choice, and every node is an embedded `QGraphicsProxyWidget`,
which is the combination Qt documents as prone to painting trails. The canvas now
uses `BoundingRectViewportUpdate`: wider than minimal, so a whole node move or
scroll is repainted as one rectangle, and it keeps the culling that makes dragging
cheap.

Same-session comparison at 120 nodes / 119 edges (median ms per step, 3 passes):

| Operation | Minimal | BoundingRect | Full |
| --- | ---: | ---: | ---: |
| zoomed out, viewport repaint | 12.21 | 12.85 | 11.60 |
| zoomed out, pan (60) | 11.65 | 12.03 | 11.92 |
| zoomed out, drag a node (45) | 7.37 | **5.64** | 16.16 |
| 1:1, pan (40) | 7.25 | 6.84 | 8.25 |
| 1:1, drag a node (30) | 9.81 | **8.48** | 11.83 |

The deciding number is the edge paints per drag pass: bounding rect paints 36
edges where full paints 119, and minimal paints 35. The narrow mode buys nothing
over bounding rect and carries the wider artifact risk.

Pattern to reuse:

- When the frame cost is dominated by items rather than by region bookkeeping,
  the wider update modes are free. Measure the mode instead of assuming the
  narrowest is the fastest.

## Fifth Round: Ghosting While Dragging A Node

The narrower viewport update mode from round four exposed a latent geometry bug.
`FullViewportUpdate` repainted the whole viewport on every change, which cleaned
up after any item that painted outside the rectangle it declared. Bounding-rect
mode repaints what changed, so nothing did.

### 14. An edge that painted outside its own bounding rect

The artifacts were edge strokes: smeared arcs and loops trailing a node while it
was dragged, in the colour of the edges. Two things made the edge item
dishonest.

`QDMGraphicsEdge.boundingRect()` returned `self.shape().boundingRect()`, the bare
path rectangle, while `paint()` strokes that path with pens up to 5px wide (the
hovered pen; 3px normally, selected and dragging). A stroke reaches half its
width past the path on both sides, so the declared rectangle was smaller than
what the item drew. Qt's own `QGraphicsPathItem` inflates for the pen; the
override dropped that.

The path was also only adopted inside `paint()`:

```python
def paint(self, painter, option, widget=None):
    self.setPath(self.calcPath())   # geometry changed while painting
```

Qt invalidates an item by its declared geometry. The invalid region for a frame
was therefore the *previous* path rectangle, the new path was drawn into it, and
the outer band of the new stroke fell outside the region and was clipped away.
The band only got painted when something forced a wider repaint (a zoom, a
resize, a selection pass). It then stayed there: the next drags kept invalidating
narrow rectangles that never covered it. Every frame of a drag added another
band, and the bands are the smeared arcs in the screenshot.

The fix:

- `QDMGraphicsEdge.strokeMargin()` returns half the widest pen the item can paint
  with plus one pixel for antialiasing, and `boundingRect()` inflates by it.
- `QDMGraphicsEdge.refreshPath()` adopts the current path and label position.
  `setSource` / `setDestination` call it as soon as a position changes, so by the
  time a caller asks for a repaint the item is already declaring its new
  geometry, and Qt repaints the union of the old and the new.
- `QDMGraphicsEdge.setPositions(source, destination)` sets both ends and adopts
  once. A node move changes both, and the route calculation is the expensive part
  of the move: adopting in each setter ran it twice per edge per frame, which
  showed up as a drag regression (0.56x against the previous round) until the two
  setters were folded into one call. `setSource` and `setDestination` now
  delegate to it, so a single-end change still adopts.
- `CachedGraphicsEdge.setSource` / `setDestination` invalidate the cached path
  *before* calling the base setter, so the setter adopts the fresh path rather
  than the previous position's cache. `paint()` keeps its `setPath` call as the
  fallback for consumers that only ever paint; it is a no-op once the geometry is
  current.

Evidence: `tests/ui/test_edge_geometry.py`. It asserts that Qt itself inflates a
path item for the pen, that the declared rectangle contains the stroked path for
every pen the edge can paint with, that a moved edge declares its new geometry
before anything paints it, and that the region the scene reports for an edge move
covers the old stroke as well as the new. That last test fails on the pre-fix
rectangle with the new stroke outside the reported region, so it is not a
formality.

Pattern to reuse:

- An item's `boundingRect()` is a contract: it must cover everything `paint()`
  draws, pen width included. Qt repaints by that rectangle, and the alternative to
  an honest one is a full-viewport repaint hiding the lie.
- Change geometry when the geometry changes, not while painting. An item that
  only adopts its path during `paint` invalidates the wrong region for one frame,
  which is enough to leave pixels behind.
- A latent geometry bug can hide behind `FullViewportUpdate` indefinitely. When
  narrowing the update mode, check what the items declare, not just what the
  mode costs.
- Adopting geometry at change time moves work out of paint and into the event
  handler. Where several inputs change together, give the item one call that
  takes them all; adopting per setter doubles the work behind the move.

## Sixth Round: The Node's Own Badge

The edge fix did not end the trails. The remaining artifact was the node's
status badge: the green check circle drawn on the node's bottom edge, left
behind in a stack of copies under a dragged node.

### 15. A node that painted its badge below its own rectangle

`TriggerGraphicsNode.paint` drew the 24px badge at `icon_y = height - 12`, i.e.
centred on the bottom edge, so 12px of it fell below the body. Upstream's
`boundingRect` is `QRectF(0, 0, width, height)`, the body alone. The declared
rectangle was therefore smaller than what the item drew, and the same
mechanism as the edge followed: Qt repainted the declared rectangle, the badge's
lower half was outside it, and each drag frame left another copy.

The state ring had the same problem from the other direction: `paint` strokes
`shape()` with a 5px pen, so the ring reaches 2.5px outside the body on every
side. Moving a node normally moves a *selected* node, whose ring is visible, so
the ring contributed its own band.

The fix keeps drawing where it drew and declares the truth:

- `bodyRect()` is the node body, used by the state ring (`shape()` is built from
  it, so the ring still hugs the node rather than the badge).
- `statusBadgeRect()` is where `paint` draws the badge, and `paint` now uses it
  instead of recomputing the arithmetic, so the drawn and declared rectangles
  cannot drift apart.
- `boundingRect()` is the body united with the badge, inflated by half
  `RING_PEN_WIDTH` plus a pixel for antialiasing. The pen width is a class
  constant used by both `_pen_from_token` and `_rebuild_theme_pens`, so a change
  to the ring width moves the margin with it.
- `initSizes` drops the cached rectangle and shape, so anything built against
  the previous size cannot survive a resize.

Evidence: `tests/ui/test_node_geometry.py`. It asserts the declared rectangle
covers the body, the badge and the ring, that it is not simply the body, that the
badge is centred on the bottom edge, and that the region the scene reports for a
one-step move covers the badge's old and new positions. Against the body-only
rectangle that last assertion fails and the declared rectangle reports
120x120; with the fix it reports 127x139 and both positions are covered.

Pattern to reuse:

- The same contract as the edge, one item over: `boundingRect()` must cover
  everything `paint` draws, including anything drawn past the item's designed
  outline and including the width of any pen.
- When an item's look is "the body plus a thing attached to its edge", keep the
  body rectangle available as its own method. Hit-testing and the selection ring
  want the body; only the repaint region wants the union.

### Measured effect (sixth round)

- Full suite: 599 passed. The tree also carries two unrelated test files added
  during this session (`tests/unit/test_win_caption_hit_test.py`), which is why
  the total moved more than the twelve geometry tests added here.
- Round seven against round four totals 0.94x, with the zoomed-out drag at 0.78x;
  three separate runs of the session agree on that shape. It is machine drift
  rather than the fix. A paired A/B that toggles move-time adoption inside one
  process puts the shipped timing at 4.011 ms/step against 4.342 for the pre-fix
  timing (zoomed out) and 6.933 against 7.122 at 1:1: adopting the geometry
  before the paint pass is, if anything, cheaper than adopting it during paint.
  The earlier 0.56x drag in round five was real, and folding the two setters into
  one call removed it (6.29 -> 4.68 ms/step).
- Against the paired baseline the canvas is still 2.80x overall and 10.63x on a
  zoomed-out node drag.

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
