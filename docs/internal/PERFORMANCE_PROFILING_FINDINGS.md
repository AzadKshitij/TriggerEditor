# TriggerEditor Performance Findings

This document captures the profiling results, the fixes already applied, and the patterns to reuse when optimizing other nodes.

## Profiling Setup

| Question | Tool | How |
| --- | --- | --- |
| Which Python objects grew? | tracemalloc | `python scripts/profile_app.py --snapshot-diff` (depth 5; the diff answers "what did this session leave behind" — a single snapshot cannot tell a one-time cost from a leak) |
| How much memory *really*? | psutil (RSS) | same script prints peak/final RSS; Polars' Rust heap, DuckDB's C++ heap, PyArrow buffers and Qt never pass through CPython's allocator, so never quote a tracemalloc total without the RSS number beside it |
| Where does CPU time go? | py-spy / cProfile | `scripts\run_pyspy.bat` (sampling, no code changes) or `python scripts/profile_app.py` then `python -m pstats profiles/latest.prof` |
| Native vs Python split, per-line memory, copy volume? | scalene | see recipe below (needs `PYTHONUTF8=1` and a *clean* program exit — `--profile-seconds`) |
| How many of *what* leaked? | objgraph | `objgraph.show_most_common_types(limit=30)` against the running app (`QGraphicsItem` counts in a long session) |

Session profiler:

```bat
.venv\Scripts\python.exe scripts\profile_app.py [--profile-seconds N] [--snapshot-diff] [--no-tracemalloc]
```

`--profile-seconds N` quits the app N seconds after its event loop starts, so
the process exits on its own — required under scalene, where a killed process
writes truncated JSON that `scalene view` rejects. `--no-tracemalloc` exists to
measure the instrument's own overhead (numbers in the Phase-8 record below).

Scalene recipe (run from a `cmd` shell; the tool is in the `profiling` uv
group — `uv sync --all-groups`):

```bat
set PYTHONUTF8=1
.venv\Scripts\python.exe -m scalene run --memory -o profiles\scalene.json scripts\profile_app.py --profile-seconds 60
.venv\Scripts\python.exe -m scalene view --cli profiles\scalene.json
```

`memray` remains the Linux/macOS recommendation for the same native-vs-Python
question (zero Windows wheels have ever shipped); it is queued as a Linux-CI
addition (see `docs/alpha_deps_alternatives.md`, written in the Phase-9
hygiene pass).

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

## Seventh Round: The Node Label

The node's badge stopped trailing, and the label above the node took over. The
label is the plate that carries the node's name, and dragging a node left a
vertical stack of plates above it.

### 16. A label that painted its plate outside its text rectangle

`QDMGraphicsNodeLabel` is a `QGraphicsTextItem`. Its `paint` draws a rounded box
padded by 6px horizontally and 3px vertically around the text, plus a 1px border,
so the visible plate is 14px wider and 8px taller than the text. `boundingRect`
was the text alone.

Fixing the label was only half of it, and the half that mattered was not obvious.
A probe with the label's rectangle corrected still reported the plate's old
position outside the region the scene repainted. The reason is how Qt dirties a
move: the moved item is repainted by the rectangle *it* declared at its old
position, and its children are dirtied only at the new position. The label is a
child of the node, so its new plate was cleared and its old one was not, even
though the plate itself now fitted inside the label's rectangle.

The fix therefore has three parts:

- `QDMGraphicsNodeLabel.boundingRect()` is the text united with the padding and
  the border, and `textRect()` keeps the text rectangle on its own.
- `QDMGraphicsNode` and `QDMIconGraphicsNode` expose `labelRect()` and unite it
  into their own `boundingRect()`, so the old plate is part of the rectangle the
  node declared when it moved.
- Both `_updateLabelPos` implementations and `_refreshLabelVisibility` call
  `prepareGeometryChange()` before changing the label, so the node's rectangle
  follows the text, the offset and the level of detail.

Positioning keeps using `textRect()`. Centring on the padded box would have
shifted every label by 6px left and 3px up; the plate grew outward instead, and
the drawn pixels did not move.

`QDMGraphicsCutline` had the same defect one size smaller: it declared the bare
polyline while stroking it with a 2px pen, so a moving cut line left the outer
half of the stroke behind. Its rectangle now accounts for the pen.

Evidence: `tests/test_210_label_geometry.py` in the package runs six assertions
of the contract, and `tests/ui/test_label_geometry.py` covers the application:
the label declares its plate, the node declares the label, hiding the label
shrinks the node back to its body, and a one-step move dirties the plate's old
and new positions. Against the pre-fix package the package tests fail with
`QDMGraphicsNodeLabel has no attribute textRect`; with only the label fixed, the
move assertion still fails on the old plate (`QRectF(208, 265, 104, 28)` outside
the repainted region) until the node declares the label as well.

Pattern to reuse:

- Fixing a child's `boundingRect` clears the child's own repaints. It does not
  clear what the child left behind when the *parent* moved. The parent has to
  declare the child.
- Keep the child's content rectangle available (`textRect`, `bodyRect`) and make
  `boundingRect` the union with its decoration, rather than moving the content
  to match a larger rectangle. The look stays, the geometry tells the truth.
- Anything that changes what the parent declares while the child stays in place
  needs `prepareGeometryChange()` on the parent.

### Measured effect (seventh round)

- The repaint area grows, so a drag step costs a little more: a paired A/B in one
  process (120 labelled nodes, 45 steps per pass, four alternating passes) puts
  the declared rectangle at 1.08x at 1:1 and 1.11x zoomed out, roughly 17.5
  against 16.2 ms/step. With the labels the application actually draws, the old
  rectangle was cheating: it was 14x8 px smaller than the plate, which is exactly
  the area that stayed on screen.
- The union itself had to be cached. A first version recomputed
  `label.boundingRect().translated(...)` plus `united()` on every call; the node's
  rectangle is asked for about 190 times per drag step, and that version measured
  8.2-8.5 us per call, or 8-9% of the step. Caching the label box in
  `_label_rect` and dropping it when the label moves, changes text or hides brings
  it to 2.3-2.6 us per call, 2.4-2.6% of the step.
- The cache has a trap: `QGraphicsItem.setVisible` and `setPos` both query the
  item's rectangle while the change is still in flight, so the cache has to be
  dropped after the call as well as before it. Dropping it only before made the
  node keep the label in its rectangle after `setLabelVisible(False)`, which
  `tests/test_210_label_geometry.py` caught.
- A twelve-frame walk of a real node reports both the old and the new plate
  inside the changed region on every frame.

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

## Eighth Round: Alpha Dependency Modernization (2026-10-25/26)

The alpha moved the whole stack at once: Python 3.14, Qt 6.11.2, pyarrow 26,
polars 2.0.0, duckdb 2.0.0, and a second chart renderer (Phase 7). This round
records what the profiling stack became and what the re-measurement can and
cannot say. Everything is offscreen on the same 9.9 GB machine as the earlier
rounds; the repo's noise floor applies - a delta under +-10-25% is never a
claim, in either direction.

### The instrument, and why each part exists

- **tracemalloc at depth 5** (was 25). Five frames attribute growth to its call
  site; deeper traces mostly buy tracer memory.
- **`--snapshot-diff`**: snapshot when the event loop starts, snapshot at exit,
  print `after.compare_to(before)`. This is the question a leak hunt actually
  asks - *what did this session leave behind*. A single snapshot cannot tell a
  one-time cost from a leak.
- **RSS peak/final (psutil) beside every Python number.** Polars' Rust heap,
  DuckDB's C++ heap, PyArrow buffers and Qt never pass through CPython's
  allocator. On an idle 20 s session: tracemalloc tracked ~49.8 MB inside a
  ~144 MB process, i.e. **about a third**. A tracemalloc total quoted alone
  understates the app by roughly 3x.
- **`--profile-seconds N`**: self-exit N seconds after the event loop starts,
  so scalene gets a *clean* process exit (a killed process writes truncated
  JSON that `scalene view` rejects). Two traps found: the countdown must post
  `quit` repeatedly (a modal dialog's nested event loop swallows a single
  post), and automated runs must skip the welcome dialog, which otherwise
  blocks on a human. Both are handled in `profile_app.py`.
- **`--no-tracemalloc`**: the control half of the overhead measurement below.
- `snakeviz` and `memory-profiler` are gone (dead: a 2022-era cProfile viewer
  and a package with zero references). `python -m pstats` reads the same
  `.prof` with no dependency. `py-spy` stays; `objgraph` 3.7.0 (object counts
  by type) and `scalene` 2.4.0 (native-vs-Python split, per-line memory, copy
  volume) joined the `profiling` group. `memray` stays a Linux/macOS
  recommendation (no Windows wheels, ever) - see `docs/alpha_deps_alternatives.md`.

### Instrument overhead (stated, or the instrumented run reads as a regression)

Same 20 s window, two pairs, interleaved:

| run | wall | profiled total | peak RSS |
| --- | ---: | ---: | ---: |
| tracemalloc on #1 | 23.2 s | 23.152 s | 204.0 MB |
| tracemalloc on #2 | 23.5 s | 23.391 s | 199.3 MB |
| tracemalloc off #1 | 20.6 s | 20.542 s | 143.9 MB |
| tracemalloc off #2 | 21.6 s | 21.640 s | 144.1 MB |

**Cost of tracemalloc: ~+10% wall and ~+56 MB RSS** on this workload (which
includes the data-backend warm-up, the allocation-heaviest thing an idle
session does). cProfile is on in both columns, so this is tracemalloc's share
only. Scalene costs far more (272.6 MB peak RSS for the same session) - use it
to answer a question, not to produce a baseline.

Scale of the tracer's own bookkeeping relative to the app is also why the
`objgraph`/RSS pair matters: CPython-side growth is a third of the story at
best.

### Snapshot-diff in practice

A 20 s idle run grew ~33.5 MB *after* the event loop started. The diff's top
lines were `<frozen importlib._bootstrap_external>` +19.1 MB and
`importlib._bootstrap` +3.1 MB: the warm-up thread importing Polars/DuckDB/
PyArrow. That is a one-time boot cost, not a leak - and it is exactly the
distinction a single snapshot cannot make. Repeat the identical session; a
leak keeps growing while a one-time cost shows a flat second diff.

### Workflow re-measurement (isolated process per workflow, repeats 5)

Per-workflow processes, as established in the Phase-5 measurement (the
all-three-in-one-process mode has its own crash: see below). `after.json` now
holds the Phase-8 stack; `after_phase5.json` preserves the Phase-5 record.

| workflow | pre baseline | Phase-5 stack | Phase-8 stack | verdict |
| --- | ---: | ---: | ---: | --- |
| small_2node | 0.006 s | 0.005 s | 0.007 s (0.0066-0.0087) | noise (sub-10 ms) |
| medium_14node | 0.059 s | 0.059 s | 0.149 s (0.1296-0.1895) | **not comparable** |
| large_105node | 5.201 s | 5.410 s | 6.483 s (5.980-7.336) | unresolved, see below |

`medium_14node` used to *fail* a Formula node (`Binder Error: no function
matches 'year(VARCHAR)'`) and now completes all 70 node executions: commit
`20a43ee` fixed the sample's day-first `order_date`, so the workflow finally
does the work it was written to do. The 0.059 s figure timed a failure
cascade; the new one times a successful 14-node run. Compare it to nothing.

`large_105node` (different sample, unaffected by the fix) reads ~+20% against
the Phase-5 stack. Do not file that as a regression yet: the machine was
measurably slower for this whole measurement window (see the canvas result
below) and the run set also produced hard crashes. Re-measure on an idle
machine before reading anything into it.

### Canvas re-measurement (defaults: 120 nodes, 3 passes)

Paint counters are identical between all three runs (same `paint.background`/
`paint.edge`/`paint.node.icon` per operation), so this is a like-for-like
comparison for the first time.

| total (sum of medians) | pre baseline | Phase-5 stack | Phase-8 stack |
| --- | ---: | ---: | ---: |
| 14 operations | 8434.8 ms | 9129.7 ms (0.92x) | 12553.8 ms (0.67x) |

That 0.67x is not believable as a code result, and it is reported as
**environment, not regression**:

- The slowdown is uniform across all 14 operations (0.63x-0.72x) while the
  work done is bit-identical.
- Nothing this benchmark touches changed between the two runs. It builds nodes
  and paints; it executes no workflow, and Polars/DuckDB/pyqtgraph are lazily
  imported or unused. Qt stayed 6.11.2.
- The in-run spread of the clean run is tight (pan runs 1861/1957/2020 ms,
  8.5%), so it is a consistently slower machine, not noise.
- The same suite measured 0.92x three hours earlier in the same session
  profile, and the intervening window ran ~20 app launches, several crashed
  processes left resident, and ~40% ambient CPU from the editor/browser.

Practical lesson for the next measurement: **check for stray
`trigger-designer`/`python` processes before trusting a canvas number.** Two
stuck instances from cancelled runs (one at 76 MB, one at 35 MB) were alive
during the first attempt, and killing them did not recover the original speed
- the machine stayed slower for the rest of the night.

### The Qt crash, re-opened

`0xC0000409` (fail-fast) in **Qt6Core.dll 6.11.2.0 +0x1c8d8**, byte-identical
across WER events. Previously 5 of 9 attempts in the *combined* harness mode
and 0 of 9 isolated; this session it hit **isolated `large_105node` runs
twice in three attempts** (once mid-build, once mid-execution), each time with
the same module and offset. The surviving run is the only `large` datapoint.

That makes it an alpha blocker candidate rather than a harness curiosity, and
Phase 9's PySide6 swap changes the Qt build, so it gets re-tested there. If it
survives the swap, file it before the alpha ships with the WER events as
evidence.

One more thing that log showed: a `nanobind` reference-leak warning at exit
("this is likely caused by a reference counting issue in the binding code") in
the run that completed. Not investigated; noted because it appears only
sometimes and nanobind-backed extensions are present via the data stack.

## Notes For Future Work

- Re-profile after the second round to see what becomes dominant next.
- If `file_input.py` still appears high in cumulative startup time, inspect its module-level imports and helper initialization next.
- If edge work is still visible after caching, inspect wheel/mouse move handlers and scene item queries next.
- Keep using the baseline-vs-latest comparison workflow before and after each optimization.
