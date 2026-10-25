#!/usr/bin/env python
"""Offscreen benchmark for live graph evaluation.

Measures the real ``TriggerSubWindow``/``TriggerScene`` evaluation path:
node construction, edge wiring, ``doEvalOutputs``, edge notifications, and
the graph algorithms used by the evaluation coordinator. Wall time is
reported next to the number of ``processInputs`` calls per node, because a
faster run that silently skips a node is not a win.

Usage:
    .venv\\Scripts\\python.exe scripts\\benchmark_eval_perf.py --label baseline
    .venv\\Scripts\\python.exe scripts\\benchmark_eval_perf.py --label step1-guard
    .venv\\Scripts\\python.exe scripts\\benchmark_eval_perf.py --compare \\
        scripts/benchmark_results/eval_baseline_*.json \\
        scripts/benchmark_results/eval_step1-guard_*.json
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import io
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from qtpy.QtWidgets import QApplication

APP = QApplication.instance() or QApplication([])

from nodeeditor.node_edge import Edge
from nodeeditor.node_graph import descendants, topological_order

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers.edge_validators import register_cycle_validator
from trigger_designer.qt.node_base import TriggerNode

register_cycle_validator()

with contextlib.suppress(Exception):
    # The app configures loguru on import; a benchmark wants only numbers.
    from loguru import logger as _loguru_logger

    _loguru_logger.remove()

RESULTS_DIR = REPO_ROOT / "scripts" / "benchmark_results"

#: Counts ``processInputs`` calls, keyed by a stable benchmark node name.
COUNTERS: Counter[str] = Counter()
#: Keeps the CPU-work loop from being optimised away.
_SINK = [0]


class CountingNode(TriggerNode):
    """A real TriggerNode whose only work is to record a compute."""

    node_title = "Bench"
    content_label = "bench_eval"

    def __init__(
        self,
        scene,
        *,
        inputs,
        outputs,
        key: str,
        work: int = 0,
    ) -> None:
        self._bench_key = key
        self._bench_work = work
        super().__init__(scene, inputs=inputs, outputs=outputs)
        # The graphics title is cosmetic; the counter key is what matters.
        with contextlib.suppress(Exception):
            self.title = key

    def processInputs(self, input_values):
        COUNTERS[self._bench_key] += 1
        if self._bench_work:
            total = 0
            for i in range(self._bench_work):
                total = (total + i * 2654435761) & 0xFFFFFFFF
            _SINK[0] ^= total
        return input_values

    def get_code(self) -> str:
        return ""


class FrameNode(TriggerNode):
    """Source node returning one frame, for Union-chain measurements."""

    node_title = "Frame"
    content_label = "bench_frame"

    def __init__(self, scene, *, key: str, value, work: int = 0) -> None:
        self._bench_key = key
        self._bench_value = value
        self._bench_work = work
        super().__init__(scene, inputs=[], outputs=[3])
        with contextlib.suppress(Exception):
            self.title = key

    def processInputs(self, input_values):
        COUNTERS[self._bench_key] += 1
        if self._bench_work:
            total = 0
            for i in range(self._bench_work):
                total = (total + i * 2654435761) & 0xFFFFFFFF
            _SINK[0] ^= total
        return [{"data": self._bench_value, "variable_name": self._bench_key}]

    def get_code(self) -> str:
        return ""


# ---------------------------------------------------------------------------
# graph builders
# ---------------------------------------------------------------------------
def make_window() -> TriggerSubWindow:
    window = TriggerSubWindow()
    with contextlib.suppress(Exception):
        # Constructor-time logging configuration, if any, is not useful here.
        from loguru import logger

        logger.remove()
    # A headless validation dialog would block the process forever.
    window._show_workflow_validation_warnings = lambda *a, **k: None
    return window


@contextlib.contextmanager
def _gc_paused():
    """Keep a collection pause out of a timed region.

    A 500-node graph allocates enough during setup that Windows sometimes
    collects in the middle of the first timed repeat, producing a 200 ms p95
    that says nothing about evaluation. Collect before t0, then pause.
    """
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def _close_window(window: TriggerSubWindow) -> None:
    window.close()
    window.deleteLater()
    APP.processEvents()


def _edge(scene, source_socket, target_socket):
    return scene.getEdgeClass()(scene, source_socket, target_socket)


def build_diamond(window, branches: int, stages: int, work: int = 0):
    """source -> [branches] -> join, repeated ``stages`` times."""
    scene = window.scene
    scene.beginBulkLoad()
    keys: set[str] = set()
    try:
        source = CountingNode(scene, inputs=[], outputs=[1], key="s", work=work)
        keys.add("s")
        previous = source
        for stage in range(stages):
            branch_nodes = []
            for index in range(branches):
                key = f"b{stage}_{index}"
                node = CountingNode(scene, inputs=[1], outputs=[1], key=key, work=work)
                _edge(scene, previous.outputs[0], node.inputs[0])
                branch_nodes.append(node)
                keys.add(key)
            join_key = f"j{stage}"
            join = CountingNode(
                scene,
                inputs=[1] * branches,
                outputs=[1],
                key=join_key,
                work=work,
            )
            for index, node in enumerate(branch_nodes):
                _edge(scene, node.outputs[0], join.inputs[index])
            keys.add(join_key)
            previous = join
    finally:
        scene.endBulkLoad()
    APP.processEvents()
    return source, previous, keys


def build_chain(window, count: int, work: int = 0, root_inputs: bool = False):
    scene = window.scene
    scene.beginBulkLoad()
    keys: set[str] = set()
    try:
        nodes = []
        for index in range(count):
            key = f"n{index}"
            node = CountingNode(
                scene,
                inputs=[] if index == 0 and not root_inputs else [1],
                outputs=[1],
                key=key,
                work=work,
            )
            if nodes:
                _edge(scene, nodes[-1].outputs[0], node.inputs[0])
            nodes.append(node)
            keys.add(key)
    finally:
        scene.endBulkLoad()
    APP.processEvents()
    return nodes, keys


def build_layered(window, total_nodes: int, width: int = 10, work: int = 0):
    """A chain of diamonds, sized to roughly ``total_nodes`` nodes."""
    stages = max(1, (total_nodes - 1) // (width + 1))
    _source, _tail, keys = build_diamond(window, width, stages, work)
    return keys


def build_fanout(window, sinks: int, work: int = 0):
    scene = window.scene
    scene.beginBulkLoad()
    keys: set[str] = set()
    try:
        source = CountingNode(scene, inputs=[], outputs=[1], key="s", work=work)
        keys.add("s")
        for index in range(sinks):
            key = f"t{index}"
            node = CountingNode(scene, inputs=[1], outputs=[], key=key, work=work)
            _edge(scene, source.outputs[0], node.inputs[0])
            keys.add(key)
    finally:
        scene.endBulkLoad()
    APP.processEvents()
    return source, keys


def build_union_chain(window, depth: int, work: int = 0):
    """A chain of real Union nodes, each fed by one fresh frame source."""
    import polars as pl

    from trigger_designer.qt.widgets.nodes.Join.union import TriggerNode_Union

    class CountingUnion(TriggerNode_Union):
        """Real Union evaluation, with a counter around the recompute."""

        def __init__(self, scene, key: str) -> None:
            self._bench_key = key
            super().__init__(scene)

        def evalImplementation(self):
            COUNTERS[self._bench_key] += 1
            return super().evalImplementation()

    scene = window.scene
    scene.beginBulkLoad()
    keys: set[str] = set()
    try:
        previous = None
        for index in range(depth):
            source_key = f"f{index}"
            source = FrameNode(
                scene,
                key=source_key,
                value=pl.DataFrame({"v": [index], "src": [source_key]}),
                work=work,
            )
            keys.add(source_key)
            union = CountingUnion(scene, f"u{index}")
            union.title = f"u{index}"
            keys.add(f"u{index}")
            if previous is not None:
                _edge(scene, previous.outputs[0], union.inputs[0])
            _edge(scene, source.outputs[0], union.inputs[0])
            previous = union
    finally:
        scene.endBulkLoad()
    APP.processEvents()
    return keys


# ---------------------------------------------------------------------------
# measurement helpers
# ---------------------------------------------------------------------------
def reset_counters() -> None:
    COUNTERS.clear()


def settle(window) -> None:
    reset_counters()
    window.doEvalOutputs()
    APP.processEvents()
    reset_counters()


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _stats(times_s: list[float]) -> dict:
    values = [value * 1000.0 for value in times_s]
    return {
        "ms_median": round(statistics.median(values), 3),
        "ms_p95": round(_percentile(values, 0.95), 3),
        "ms_min": round(min(values), 3),
        "ms_max": round(max(values), 3),
        "repeats": len(values),
    }


def _counts(expected: set[str]) -> dict:
    by_node = {key: COUNTERS.get(key, 0) for key in sorted(COUNTERS)}
    total = sum(by_node.values())
    unique = len(by_node)
    return {
        "total": total,
        "by_node": by_node,
        "unique_nodes": unique,
        "expected_nodes": len(expected),
        "missing": sorted(expected - set(by_node)),
        "duplicate_ratio": round(total / unique, 3) if unique else 0.0,
    }


def _use_first_counts(counts: dict) -> None:
    """Make the global counter reflect the first (cold) repeat only."""
    COUNTERS.clear()
    COUNTERS.update(counts)


def _run_repeats(repeats: int, action):
    times: list[float] = []
    first_counts: dict | None = None
    for _ in range(repeats):
        reset_counters()
        with _gc_paused():
            started = time.perf_counter()
            action()
            times.append(time.perf_counter() - started)
        if first_counts is None:
            first_counts = dict(COUNTERS)
    return times, first_counts or {}


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------
def scenario_edit_diamond(branches: int, stages: int, repeats: int, work: int):
    window = make_window()
    try:
        source, _join, expected = build_diamond(window, branches, stages, work)
        settle(window)
        times, counts = _run_repeats(repeats, source.onInputChanged)
        _use_first_counts(counts)
        data = _stats(times)
        data["computes"] = _counts(expected)
        data["nodes"] = len(window.scene.nodes)
        data["edges"] = len(window.scene.edges)
        return data
    finally:
        _close_window(window)


def scenario_edit_chain(count: int, repeats: int, work: int):
    window = make_window()
    try:
        nodes, all_keys = build_chain(window, count, work)
        settle(window)
        edited_index = count // 2
        edited = nodes[edited_index]
        expected = set(all_keys) - {f"n{i}" for i in range(edited_index)}
        times, counts = _run_repeats(repeats, edited.onInputChanged)
        _use_first_counts(counts)
        data = _stats(times)
        data["computes"] = _counts(expected)
        data["nodes"] = len(window.scene.nodes)
        data["edges"] = len(window.scene.edges)
        data["edited_index"] = edited_index
        return data
    finally:
        _close_window(window)


def _edge_connect_case(work: int):
    """A join with one settled input, then the exact drag-end sequence."""
    window = make_window()
    scene = window.scene
    scene.beginBulkLoad()
    try:
        first = CountingNode(scene, inputs=[], outputs=[1], key="a", work=work)
        second = CountingNode(scene, inputs=[], outputs=[1], key="b", work=work)
        join = CountingNode(scene, inputs=[1, 1], outputs=[1], key="j", work=work)
        _edge(scene, first.outputs[0], join.inputs[0])
    finally:
        scene.endBulkLoad()
    settle(window)
    return window, second, join


def scenario_edit_edge_connect(repeats: int, work: int):
    times: list[float] = []
    counts: dict = {}
    for _ in range(repeats):
        window, source, join = _edge_connect_case(work)
        try:
            reset_counters()
            with _gc_paused():
                started = time.perf_counter()
                new_edge = _edge(window.scene, source.outputs[0], join.inputs[1])
                for socket in (source.outputs[0], join.inputs[1]):
                    socket.node.onEdgeConnectionChanged(new_edge)
                    if socket.is_input:
                        socket.node.onInputChanged(socket)
                # Edge notifications coalesce in a 0 ms flush; the benchmark
                # closes the event turn explicitly so counts are comparable.
                window.scene.evaluator.flush_now()
                times.append(time.perf_counter() - started)
            if not counts:
                counts = dict(COUNTERS)
        finally:
            _close_window(window)
    _use_first_counts(counts)
    data = _stats(times)
    data["computes"] = _counts({"j"})
    data["nodes"] = 3
    data["edges"] = 2
    return data


def scenario_edit_split(repeats: int, work: int):
    """Insert a node into an edge and replay the package's notification loop."""
    times: list[float] = []
    counts: dict = {}
    for _ in range(repeats):
        window = make_window()
        scene = window.scene
        scene.beginBulkLoad()
        try:
            source = CountingNode(scene, inputs=[], outputs=[1], key="a", work=work)
            target = CountingNode(scene, inputs=[1], outputs=[], key="b", work=work)
            inserted = CountingNode(scene, inputs=[1], outputs=[1], key="n", work=work)
            original = _edge(scene, source.outputs[0], target.inputs[0])
        finally:
            scene.endBulkLoad()
        settle(window)
        try:
            reset_counters()
            with _gc_paused():
                started = time.perf_counter()
                original.remove(silent=True)
                first_edge = _edge(scene, source.outputs[0], inserted.inputs[0])
                second_edge = _edge(scene, inserted.outputs[0], target.inputs[0])
                # The package's auto-split order: internal input, internal
                # output, then the old downstream input.
                for socket, edge in (
                    (inserted.inputs[0], first_edge),
                    (inserted.outputs[0], second_edge),
                    (target.inputs[0], second_edge),
                ):
                    socket.node.onEdgeConnectionChanged(edge)
                    if socket.is_input:
                        socket.node.onInputChanged(socket)
                window.scene.evaluator.flush_now()
                times.append(time.perf_counter() - started)
            if not counts:
                counts = dict(COUNTERS)
        finally:
            _close_window(window)
    _use_first_counts(counts)
    data = _stats(times)
    data["computes"] = _counts({"n", "b"})
    data["nodes"] = 3
    data["edges"] = 2
    return data


def scenario_eval_full(total_nodes: int, repeats: int, work: int):
    window = make_window()
    try:
        expected = build_layered(window, total_nodes, width=10, work=work)
        settle(window)
        times: list[float] = []
        counts: dict = {}
        for _ in range(repeats):
            reset_counters()
            for node in window.scene.nodes:
                node.markDirty(True)
            with _gc_paused():
                started = time.perf_counter()
                window.doEvalOutputs()
                times.append(time.perf_counter() - started)
            if not counts:
                counts = dict(COUNTERS)
        _use_first_counts(counts)
        data = _stats(times)
        data["computes"] = _counts(expected)
        data["nodes"] = len(window.scene.nodes)
        data["edges"] = len(window.scene.edges)
        return data
    finally:
        _close_window(window)


def scenario_order_topological(total_nodes: int, repeats: int, work: int):
    window = make_window()
    try:
        build_layered(window, total_nodes, width=10, work=work)
        # No evaluation needed: ordering is a pure graph operation.
        times, _ = _run_repeats(repeats, lambda: topological_order(window.scene))
        data = _stats(times)
        data["nodes"] = len(window.scene.nodes)
        data["edges"] = len(window.scene.edges)
        return data
    finally:
        _close_window(window)


def scenario_descendants_worst(total_nodes: int, repeats: int, work: int):
    window = make_window()
    try:
        source, _keys = build_fanout(window, max(1, total_nodes - 1), work)
        times, _ = _run_repeats(repeats, lambda: descendants(window.scene, source))
        data = _stats(times)
        data["nodes"] = len(window.scene.nodes)
        data["edges"] = len(window.scene.edges)
        data["closure"] = len(descendants(window.scene, source))
        return data
    finally:
        _close_window(window)


def scenario_validate_cycle(total_nodes: int, repeats: int, work: int):
    window = make_window()
    try:
        nodes, _keys = build_chain(window, max(2, total_nodes), work, root_inputs=True)
        first, last = nodes[0], nodes[-1]
        times, _ = _run_repeats(
            repeats,
            lambda: Edge.validateEdge(last.outputs[0], first.inputs[0]),
        )
        data = _stats(times)
        data["nodes"] = len(window.scene.nodes)
        data["edges"] = len(window.scene.edges)
        return data
    finally:
        _close_window(window)


def scenario_union_chain(depth: int, repeats: int, work: int):
    window = make_window()
    try:
        expected = build_union_chain(window, depth, work)
        settle(window)
        times: list[float] = []
        counts: dict = {}
        for _ in range(repeats):
            reset_counters()
            for node in window.scene.nodes:
                node.markDirty(True)
            with _gc_paused():
                started = time.perf_counter()
                window.doEvalOutputs()
                times.append(time.perf_counter() - started)
            if not counts:
                counts = dict(COUNTERS)
        _use_first_counts(counts)
        data = _stats(times)
        data["computes"] = _counts(expected)
        data["nodes"] = len(window.scene.nodes)
        data["edges"] = len(window.scene.edges)
        return data
    finally:
        _close_window(window)


# ---------------------------------------------------------------------------
# metadata / io
# ---------------------------------------------------------------------------
def _git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:  # noqa: BLE001 - metadata is best effort
        return ""


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("nodeeditor-qtpy")
    except Exception:  # noqa: BLE001
        try:
            import nodeeditor

            return getattr(nodeeditor, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            return "unknown"


def meta(label: str, work: int) -> dict:
    return {
        "label": label,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "commit": _git("rev-parse", "--short", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "python": platform.python_version(),
        "platform": sys.platform,
        "nodeeditor": _package_version(),
        "work": work,
    }


def save(label: str, work: int, scenarios: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"eval_{label}_{stamp}.json"
    document = {"meta": meta(label, work), "scenarios": scenarios}
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _all_scenarios(repeats: int, work: int, only: set[str] | None = None) -> dict:
    jobs: list[tuple[str, object]] = []
    for branches in (2, 4):
        for stages in (1, 2):
            key = f"edit.diamond.{branches}x{stages}"
            jobs.append(
                (
                    key,
                    lambda b=branches, s=stages: scenario_edit_diamond(
                        b, s, repeats, work
                    ),
                )
            )
    for count in (50, 200, 500):
        jobs.append(
            (
                f"edit.chain.{count}",
                lambda c=count: scenario_edit_chain(c, repeats, work),
            )
        )
    jobs.append(
        ("edit.edge.connect", lambda: scenario_edit_edge_connect(repeats, work))
    )
    jobs.append(("edit.split", lambda: scenario_edit_split(repeats, work)))
    for count in (50, 200, 500):
        jobs.append(
            (
                f"eval.full.grid.{count}",
                lambda c=count: scenario_eval_full(c, repeats, work),
            )
        )
    for count in (50, 200, 500):
        jobs.append(
            (
                f"order.topological.{count}",
                lambda c=count: scenario_order_topological(c, repeats, work),
            )
        )
    for count in (50, 200, 500):
        jobs.append(
            (
                f"descendants.worst.{count}",
                lambda c=count: scenario_descendants_worst(c, repeats, work),
            )
        )
    for count in (50, 200, 500):
        jobs.append(
            (
                f"validate.cycle.{count}",
                lambda c=count: scenario_validate_cycle(c, repeats, work),
            )
        )
    for depth in (10, 25, 50):
        jobs.append(
            (
                f"union.chain.{depth}",
                lambda d=depth: scenario_union_chain(d, repeats, work),
            )
        )

    scenarios: dict = {}
    for key, job in jobs:
        if only and key not in only:
            continue
        print(f"  {key} ...", file=sys.stderr, flush=True)
        try:
            # Node construction and resource lookups print debug noise; the
            # benchmark's own progress goes to stderr, so silence stdout here.
            with contextlib.redirect_stdout(io.StringIO()):
                scenarios[key] = job()  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 - one scenario must not lose the rest
            import traceback

            traceback.print_exc()
            scenarios[key] = {
                "error": f"{type(exc).__name__}: {exc}",
                "ms_median": 0.0,
                "ms_p95": 0.0,
                "ms_min": 0.0,
                "ms_max": 0.0,
                "repeats": repeats,
            }
    return scenarios


def _print_summary(scenarios: dict) -> None:
    print(
        f"\n{'scenario':<28} {'median':>9} {'p95':>9} "
        f"{'computes':>9} {'unique':>7} {'dup':>6} {'missing':>8}"
    )
    for key, row in scenarios.items():
        if row.get("error"):
            print(f"{key:<28} ERROR: {row['error']}")
            continue
        computes = row.get("computes") or {}
        print(
            f"{key:<28} {row['ms_median']:>8.3f}ms {row['ms_p95']:>8.3f}ms "
            f"{computes.get('total', '-'):>9} {computes.get('unique_nodes', '-'):>7} "
            f"{computes.get('duplicate_ratio', '-'):>6} "
            f"{len(computes.get('missing', [])):>8}"
        )


def compare(paths: list[str]) -> None:
    before = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    after = json.loads(Path(paths[1]).read_text(encoding="utf-8"))
    b_scenarios = before.get("scenarios", {})
    a_scenarios = after.get("scenarios", {})
    print(f"\nbefore: {paths[0]}")
    print(f"after:  {paths[1]}\n")
    print(
        f"{'scenario':<28} {'before ms':>10} {'after ms':>9} "
        f"{'speedup':>8} {'computes':>15} {'dup':>11}"
    )
    for key in b_scenarios:
        if key not in a_scenarios:
            continue
        b = b_scenarios[key]
        a = a_scenarios[key]
        if b.get("error") or a.get("error"):
            print(
                f"{key:<28} ERROR before={b.get('error', '-')} "
                f"after={a.get('error', '-')}"
            )
            continue
        b_ms = b["ms_median"]
        a_ms = a["ms_median"]
        speedup = (b_ms / a_ms) if a_ms else float("inf")
        b_computes = (b.get("computes") or {}).get("total", "-")
        a_computes = (a.get("computes") or {}).get("total", "-")
        b_dup = (b.get("computes") or {}).get("duplicate_ratio", "-")
        a_dup = (a.get("computes") or {}).get("duplicate_ratio", "-")
        print(
            f"{key:<28} {b_ms:>10.3f} {a_ms:>9.3f} {speedup:>7.2f}x "
            f"{b_computes!s:>6} -> {a_computes!s:<6} "
            f"{b_dup!s:>5} -> {a_dup!s:<5}"
        )
    b_total = sum(
        row["ms_median"] for row in b_scenarios.values() if not row.get("error")
    )
    a_total = sum(
        row["ms_median"] for row in a_scenarios.values() if not row.get("error")
    )
    print(
        f"\n{'TOTAL (sum of medians)':<28} {b_total:>10.3f} {a_total:>9.3f} "
        f"{(b_total / a_total) if a_total else float('inf'):>7.2f}x"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--label", help="Save as eval_<label>_<timestamp>.json")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--work",
        type=int,
        default=0,
        help="Arithmetic iterations per processInputs; 0 isolates graph overhead",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        help="Compare two saved result files",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated scenario keys to run (default: all)",
    )
    args = parser.parse_args()

    if args.compare:
        compare(args.compare)
        return
    if not args.label:
        parser.error("--label is required unless --compare is given")

    sys.setrecursionlimit(10000)
    only = {key.strip() for key in (args.only or "").split(",") if key.strip()} or None
    print(
        f"nodeeditor {_package_version()} | Python {platform.python_version()} | "
        f"work={args.work} | repeats={args.repeats}"
    )
    print("Building scenarios...")
    started = time.perf_counter()
    scenarios = _all_scenarios(args.repeats, args.work, only)
    path = save(args.label, args.work, scenarios)
    _print_summary(scenarios)
    print(f"\nSaved {path} in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
