#!/usr/bin/env python
"""Offscreen benchmark for node-graph canvas interactivity.

Measures what a user feels when a workflow has many nodes on screen: panning
with the middle mouse button, zooming with Ctrl+wheel, rubber-band selection,
dragging a node, a full viewport repaint, and scene item queries. It runs the
real canvas - ``TriggerSubWindow`` with its ``TriggerScene`` and the project's
node/edge graphics classes - under the offscreen Qt platform, so results are
comparable between runs on the same machine even though there is no GPU.

Paints are counted next to the timings. A change that makes a frame cheaper by
painting twice as often (or the reverse) shows up as time down and paints up,
which is exactly the trap this benchmark exists to expose.

Setup (node construction, workflow load) never counts toward a measurement.
Every operation is repeated and the median reported.

Usage:
    .venv\\Scripts\\python.exe scripts\\benchmark_canvas_perf.py --label before
    .venv\\Scripts\\python.exe scripts\\benchmark_canvas_perf.py --label after --nodes 400
    .venv\\Scripts\\python.exe scripts\\benchmark_canvas_perf.py --compare \\
        scripts/benchmark_results/canvas_before_*.json scripts/benchmark_results/canvas_after_*.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Node/UI modules print emoji straight to stdout; a cp1252 console would raise
# UnicodeEncodeError mid-benchmark. Force UTF-8 like the other scripts here.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from qtpy.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from qtpy.QtGui import QImage, QMouseEvent, QPainter, QWheelEvent
from qtpy.QtWidgets import QApplication

# A QApplication must exist before anything imports the app's widget modules.
APP = QApplication.instance() or QApplication([])

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

RESULTS_DIR = REPO_ROOT / "scripts" / "benchmark_results"

COUNTERS: dict[str, int] = {}
_INSTRUMENTED = False


# --------------------------------------------------------------------------
# paint / event counters
# --------------------------------------------------------------------------
def _count(key: str) -> None:
    COUNTERS[key] = COUNTERS.get(key, 0) + 1


def instrument() -> None:
    """Wrap the paint and mouse-move entry points with cheap counters.

    Wrapping happens once per process; the added call is a dict increment and
    is present in every run being compared, so it never biases a comparison.
    """
    global _INSTRUMENTED
    if _INSTRUMENTED:
        return
    _INSTRUMENTED = True

    def wrap(cls, name: str, key: str) -> None:
        original = getattr(cls, name)

        def counted(self, *args, **kwargs):
            _count(key)
            return original(self, *args, **kwargs)

        setattr(cls, name, counted)

    from nodeeditor.node_graphics_edge import QDMGraphicsEdge
    from nodeeditor.node_graphics_node import QDMGraphicsNode
    from nodeeditor.node_graphics_scene import QDMGraphicsScene
    from nodeeditor.node_graphics_view import QDMGraphicsView
    from nodeeditor.node_icon_graphics_node import QDMIconGraphicsNode

    wrap(QDMGraphicsScene, "drawBackground", "paint.background")
    wrap(QDMGraphicsEdge, "paint", "paint.edge")
    wrap(QDMGraphicsNode, "paint", "paint.node")
    wrap(QDMIconGraphicsNode, "paint", "paint.node.icon")
    wrap(QDMGraphicsView, "mouseMoveEvent", "event.mouse_move")
    wrap(QDMGraphicsView, "setSocketHighlights", "view.socket_scan")


# --------------------------------------------------------------------------
# synthetic node class
# --------------------------------------------------------------------------
class BenchNode(TriggerNode):
    """Minimal node: one label of content, nothing to evaluate.

    Enough to build a real ``TriggerGraphicsNode`` (proxy widget, sockets,
    theme pens) without pulling a heavy node's evaluator into the picture.
    """

    node_title = "Bench"
    content_label = "bench"
    content_label_objname = "bench_node_label"


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------
class CanvasDriver:
    """Sends real Qt mouse/wheel events to the canvas and times the result."""

    def __init__(self, window: TriggerSubWindow) -> None:
        self.window = window
        self.view = window.view
        self.grScene = window.scene.grScene
        self.vp = window.view.viewport()

    # -- event plumbing -----------------------------------------------------
    def _send(self, event: QEvent) -> None:
        QApplication.sendEvent(self.vp, event)

    def _mouse(
        self,
        etype: QEvent.Type,
        pos: QPoint,
        button: Qt.MouseButton,
        buttons: Qt.MouseButton,
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    ) -> None:
        event = QMouseEvent(
            etype,
            QPointF(pos),
            QPointF(self.vp.mapToGlobal(pos)),
            button,
            buttons,
            modifiers,
        )
        self._send(event)

    def _wheel(self, pos: QPoint, delta: int, modifiers: Qt.KeyboardModifier) -> None:
        event = QWheelEvent(
            QPointF(pos),
            QPointF(self.vp.mapToGlobal(pos)),
            QPoint(0, 0),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            modifiers,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        self._send(event)

    # -- viewport helpers ---------------------------------------------------
    def center_point(self) -> QPoint:
        return QPoint(self.vp.width() // 2, self.vp.height() // 2)

    def viewport_scene_rect(self) -> QRectF:
        return self.view.mapToScene(self.vp.rect()).boundingRect()

    def point_over_item(self, node) -> QPoint | None:
        """A viewport point that Qt resolves to `node`'s own graphics item."""
        scene_pt = node.grNode.sceneBoundingRect().center()
        vp_pt = self.view.mapFromScene(scene_pt)
        if not self.vp.rect().contains(vp_pt):
            return None
        item = self.view.itemAt(vp_pt)
        while item is not None and getattr(item, "node", None) is not node:
            item = item.parentItem()
        return vp_pt if item is not None else None

    def point_over_empty(self) -> QPoint:
        """A viewport point that Qt resolves to no item."""
        rect = self.vp.rect()
        for y in range(4, rect.height() - 4, 12):
            for x in range(4, rect.width() - 4, 12):
                pt = QPoint(x, y)
                if self.view.itemAt(pt) is None:
                    return pt
        return QPoint(2, 2)

    # -- operations ---------------------------------------------------------
    def repaint_viewport(self) -> None:
        """Force full viewport repaints; isolates widget paint cost."""
        for _ in range(10):
            self.vp.repaint()

    def render_offscreen(self) -> None:
        """Render the scene into an image; works even without widget exposure."""
        rect = self.vp.rect()
        image = QImage(rect.size(), QImage.Format.Format_ARGB32_Premultiplied)
        for _ in range(10):
            painter = QPainter(image)
            self.view.render(painter, QRectF(rect))
            painter.end()

    def pan(self, steps: int = 40, step_px: int = 12) -> None:
        """Middle-button pan: the exact path the app's pan uses."""
        pos = self.center_point()
        self._mouse(
            QEvent.Type.MouseButtonPress,
            pos,
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.MiddleButton,
        )
        for _ in range(steps):
            pos += QPoint(step_px, step_px // 2)
            self._mouse(
                QEvent.Type.MouseMove,
                pos,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.MiddleButton,
            )
            APP.processEvents()
        self._mouse(
            QEvent.Type.MouseButtonRelease,
            pos,
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.NoButton,
        )
        APP.processEvents()

    def zoom(self, steps: int = 12) -> None:
        """Ctrl+wheel out then back in, one wheel step per event."""
        pos = self.center_point()
        for _ in range(steps):
            self._wheel(pos, -120, Qt.KeyboardModifier.ControlModifier)
            APP.processEvents()
        for _ in range(steps):
            self._wheel(pos, 120, Qt.KeyboardModifier.ControlModifier)
            APP.processEvents()

    def rubber_band(self, steps: int = 30) -> None:
        """Press empty space, drag across the scene, release."""
        rect = self.vp.rect()
        start = self.point_over_empty()
        end = QPoint(rect.width() - 6, rect.height() - 6)
        self._mouse(
            QEvent.Type.MouseButtonPress,
            start,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
        for i in range(1, steps + 1):
            t = i / steps
            pos = QPoint(
                int(start.x() + (end.x() - start.x()) * t),
                int(start.y() + (end.y() - start.y()) * t),
            )
            self._mouse(
                QEvent.Type.MouseMove,
                pos,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
            )
            APP.processEvents()
        self._mouse(
            QEvent.Type.MouseButtonRelease,
            end,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        )
        APP.processEvents()

    def drag_node(self, node, steps: int = 30, dx: int = 8, dy: int = 4) -> None:
        """Left-drag a node by `steps` moves; the node's own move handler runs."""
        pt = self.point_over_item(node)
        if pt is None:
            return
        self._mouse(
            QEvent.Type.MouseButtonPress,
            pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
        pos = QPoint(pt)
        for _ in range(steps):
            pos += QPoint(dx, dy)
            self._mouse(
                QEvent.Type.MouseMove,
                pos,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
            )
            APP.processEvents()
        self._mouse(
            QEvent.Type.MouseButtonRelease,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        )
        APP.processEvents()

    def query_items(self, steps: int = 200, size: float = 600.0) -> None:
        """Scene item queries in a viewport-sized rect: BSP vs linear index."""
        center = self.view.mapToScene(self.center_point())
        rect = QRectF(center.x() - size / 2, center.y() - size / 2, size, size)
        for _ in range(steps):
            self.grScene.items(rect)


# --------------------------------------------------------------------------
# scenario setup
# --------------------------------------------------------------------------
def build_window() -> TriggerSubWindow:
    window = TriggerSubWindow()
    # Headless: a validation dialog would block forever.
    window._show_workflow_validation_warnings = lambda *a, **k: None
    window.resize(1200, 800)
    window.show()
    APP.processEvents()
    return window


def build_grid(window: TriggerSubWindow, count: int):
    """Place `count` synthetic nodes on a grid and chain them with edges."""
    scene = window.scene
    scene.beginBulkLoad()
    nodes = []
    try:
        columns = max(1, int(math.sqrt(count * 1.6)))
        for i in range(count):
            node = BenchNode(scene)
            node.grNode.setPos((i % columns) * 220.0, (i // columns) * 180.0)
            nodes.append(node)
        # chain consecutive nodes; a large graph is edge-heavy too
        edge_cls = scene.getEdgeClass()
        for index, (a, b) in enumerate(itertools.pairwise(nodes)):
            try:
                edge_cls(scene, a.outputs[0], b.inputs[0])
            except Exception as exc:  # noqa: BLE001 - one bad pair must not abort the build
                print(f"  edge {index} skipped: {exc}")
    finally:
        scene.endBulkLoad()
    APP.processEvents()
    return nodes


def build_from_file(window: TriggerSubWindow, path: Path):
    loaded = window.fileLoad(str(path))
    if not loaded:
        raise RuntimeError(f"failed to load {path}")
    APP.processEvents()
    return list(window.scene.nodes)


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------
def measure(fn, steps: int, repeats: int, before_each=None) -> dict:
    """Run `fn` `repeats` times; report median time and median paint counts."""
    times: list[float] = []
    counters: list[dict[str, int]] = []
    for _ in range(repeats):
        if before_each is not None:
            before_each()
            APP.processEvents()
        COUNTERS.clear()
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
        counters.append(dict(COUNTERS))

    times.sort()
    total = times[len(times) // 2]
    merged: dict[str, int] = {}
    for key in sorted(set().union(*counters) if counters else set()):
        merged[key] = int(statistics.median([c.get(key, 0) for c in counters]))
    return {
        "steps": steps,
        "ms_median": round(total * 1000.0, 3),
        "ms_per_step": round(total * 1000.0 / max(1, steps), 4),
        "runs_ms": [round(t * 1000.0, 3) for t in times],
        "counters": merged,
    }


def run_ops(
    driver: CanvasDriver, label: str, args, nodes, results: dict, reset_view
) -> None:
    """Run the whole operation set once for the current view state.

    `reset_view` restores the starting transform before every measured pass, so
    pan and zoom cannot drift the canvas into empty space and silently turn the
    later operations into no-ops.
    """
    ops = [
        ("repaint.viewport", driver.repaint_viewport, 10),
        ("render.offscreen", driver.render_offscreen, 10),
        # Each op is called with the step count that is also reported, so
        # ms/step stays honest when the CLI overrides it.
        ("pan.middle", lambda: driver.pan(args.pan_steps), args.pan_steps),
        ("zoom.ctrl_wheel", lambda: driver.zoom(args.zoom_steps), args.zoom_steps * 2),
        (
            "rubber_band.select",
            lambda: driver.rubber_band(args.drag_steps),
            args.drag_steps,
        ),
        (
            "query.items_600",
            lambda: driver.query_items(args.query_steps),
            args.query_steps,
        ),
    ]

    # Dragging is measured on whatever node is under the viewport centre at the
    # time of the pass: the preceding ops move the view, so the node is picked
    # after the reset rather than now.
    def _drag_op():
        node = _pick_center_node(driver, nodes)
        if node is not None:
            driver.drag_node(node, args.drag_steps)

    ops.insert(4, ("drag.node", _drag_op, args.drag_steps))

    for name, fn, steps in ops:
        key = f"{label}.{name}"

        def before_each(_reset=reset_view):
            _reset()
            _clear_selection()
            APP.processEvents()

        results["metrics"][key] = measure(
            fn, steps, args.repeats, before_each=before_each
        )
        row = results["metrics"][key]
        print(
            f"  {key:<34} {row['ms_median']:>9.2f} ms  "
            f"({row['ms_per_step']:>7.3f} ms/step)  "
            f"paints={_fmt_counters(row['counters'])}"
        )


def _clear_selection() -> None:
    _CURRENT_DRIVER.grScene.clearSelection()


_CURRENT_DRIVER: CanvasDriver | None = None


def _center_anchor(nodes):
    """The node closest to the centre of the whole graph.

    Used to re-center the 1:1 view from scratch: picking blindly from the
    current view would fail once an earlier op has scrolled it into empty
    space, and every later op would then measure nothing.
    """
    if not nodes:
        return None
    rect = nodes[0].grNode.sceneBoundingRect()
    for node in nodes[1:]:
        rect = rect.united(node.grNode.sceneBoundingRect())
    center = rect.center()
    return min(
        nodes,
        key=lambda n: (
            n.grNode.sceneBoundingRect().center() - center
        ).manhattanLength(),
    )


def _pick_center_node(driver: CanvasDriver, nodes):
    """The node closest to the viewport center whose item Qt resolves to it."""
    if not nodes:
        return None
    center = driver.view.mapToScene(driver.center_point())
    ranked = sorted(
        nodes,
        key=lambda n: (
            n.grNode.sceneBoundingRect().center() - center
        ).manhattanLength(),
    )
    for node in ranked[:12]:
        if driver.point_over_item(node) is not None:
            return node
    return None


def _metrics_of(doc: dict) -> dict:
    """Operation records from a result file.

    Newer files nest them under ``metrics``; the first files written by this
    harness kept them at the top level, so accept both.
    """
    nested = doc.get("metrics") or {}
    if nested:
        return nested
    return {
        key: value
        for key, value in doc.items()
        if isinstance(value, dict) and "ms_median" in value
    }


_SHORT_COUNTERS = {
    "paint.background": "bg",
    "paint.edge": "edge",
    "paint.node": "node",
    "paint.node.icon": "node",
    "event.mouse_move": "move",
    "view.socket_scan": "scan",
}


def _short_counters(counters: dict[str, int]) -> str:
    """Compact paint/event counts for the comparison table."""
    if not counters:
        return "-"
    parts = []
    for key, value in sorted(counters.items()):
        if not value:
            continue
        parts.append(f"{_SHORT_COUNTERS.get(key, key)}={value}")
    return " ".join(parts) if parts else "-"


def _fmt_counters(counters: dict[str, int]) -> str:
    if not counters:
        return "-"
    return ",".join(f"{k.split('.')[-1]}={v}" for k, v in sorted(counters.items()) if v)


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------
def compare(paths: list[str]) -> None:
    if len(paths) != 2:
        raise SystemExit("--compare needs exactly two result files")
    before = json.loads(Path(paths[0]).read_text())
    after = json.loads(Path(paths[1]).read_text())
    b_metrics = _metrics_of(before)
    a_metrics = _metrics_of(after)

    print(f"\nbefore: {paths[0]}")
    print(f"after:  {paths[1]}\n")
    print(
        f"{'operation':<40} {'before ms':>10} {'after ms':>10} "
        f"{'speedup':>9} {'before paints':>14} {'after paints':>13}"
    )

    keys = [k for k in b_metrics if k in a_metrics]
    for key in keys:
        b = b_metrics[key]["ms_median"]
        a = a_metrics[key]["ms_median"]
        speedup = (b / a) if a else float("inf")
        bp = _short_counters(b_metrics[key]["counters"])
        ap = _short_counters(a_metrics[key]["counters"])
        print(f"{key:<40} {b:>10.2f} {a:>10.2f} {speedup:>8.2f}x {bp:>16} -> {ap:<16}")

    totals_b = sum(v["ms_median"] for v in b_metrics.values())
    totals_a = sum(v["ms_median"] for v in a_metrics.values())
    print(
        f"\n{'TOTAL (sum of medians)':<40} {totals_b:>10.2f} {totals_a:>10.2f} "
        f"{(totals_b / totals_a) if totals_a else float('inf'):>8.2f}x"
    )


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--label", help="Save results as canvas_<label>_<timestamp>.json"
    )
    parser.add_argument(
        "--nodes",
        type=int,
        default=120,
        help="Number of synthetic nodes when no --file is given",
    )
    parser.add_argument("--file", help="Load a saved .tds workflow instead of a grid")
    parser.add_argument("--repeats", type=int, default=3, help="Passes per operation")
    parser.add_argument("--pan-steps", type=int, default=40)
    parser.add_argument("--zoom-steps", type=int, default=12)
    parser.add_argument("--drag-steps", type=int, default=30)
    parser.add_argument("--query-steps", type=int, default=200)
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        help="Compare two saved result files",
    )
    args = parser.parse_args()

    if args.compare:
        compare(args.compare)
        return
    if not args.label:
        parser.error("--label is required unless --compare is given")

    instrument()

    print(f"Building canvas ({args.file or f'{args.nodes} synthetic nodes'})...")
    window = build_window()
    t0 = time.perf_counter()
    if args.file:
        nodes = build_from_file(window, Path(args.file))
    else:
        nodes = build_grid(window, args.nodes)
    print(
        f"  built in {time.perf_counter() - t0:.2f}s: "
        f"{len(nodes)} nodes, {len(window.scene.edges)} edges"
    )

    driver = CanvasDriver(window)
    global _CURRENT_DRIVER
    _CURRENT_DRIVER = driver

    results: dict = {
        "config": {
            "label": args.label,
            "nodes": len(nodes),
            "edges": len(window.scene.edges),
            "repeats": args.repeats,
            "source": args.file or "synthetic",
            "viewport": [driver.vp.width(), driver.vp.height()],
        },
        "metrics": {},
    }

    # zoomed out: every node in view, the case the user says hurts most
    def reset_zoomed_out() -> None:
        window.view.resetTransform()
        window.view.fitInView(
            window.scene.grScene.itemsBoundingRect().adjusted(-60, -60, 60, 60),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    reset_zoomed_out()
    APP.processEvents()
    scale = driver.view.transform().m11()
    results["config"]["zoom_out_scale"] = round(scale, 4)
    print(f"Zoomed out to scale {scale:.3f}; running operations...")
    run_ops(driver, "zoomed_out", args, nodes, results, reset_zoomed_out)

    # zoomed in to 1:1 on the busiest area
    anchor = _center_anchor(nodes)

    def reset_zoomed_in() -> None:
        window.view.resetTransform()
        if anchor is not None:
            window.view.centerOn(anchor.grNode.sceneBoundingRect().center())

    reset_zoomed_in()
    APP.processEvents()
    print(
        f"Zoomed in to 1:1 (scale {driver.view.transform().m11():.3f}); "
        "running operations..."
    )
    run_ops(driver, "zoomed_in", args, nodes, results, reset_zoomed_in)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"canvas_{args.label}_{stamp}.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")

    window.close()


if __name__ == "__main__":
    main()
