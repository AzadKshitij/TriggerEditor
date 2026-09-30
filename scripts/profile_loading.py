"""Headless, phase-by-phase profile of saved workflow loading and dock rendering.

Usage: uv run --no-sync python scripts/profile_loading.py --workflow large --cprofile
       uv run --no-sync python scripts/profile_loading.py --workflow medium

The first run includes cold Python/Qt imports. Times are wall-clock, not CPU.
Evaluation of downstream nodes can be nested: per-node eval timings are
inclusive and must not be added together. JSON and optional .prof are saved
under profiles/ for comparison with later runs.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import os
import sys
import time
from collections import defaultdict
from contextlib import ExitStack
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
START = time.perf_counter()

from qtpy.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])
QT_READY = time.perf_counter()

from nodeeditor.node_editor_widget import NodeEditorWidget

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.performance_scene import TriggerScene

IMPORTS_READY = time.perf_counter()

WORKFLOWS = {
    "small": ROOT / "savedfiles/1. in-select.tds",
    "medium": ROOT / "savedfiles/Example_1/Test1.tds",
    "large": ROOT / "savedfiles/Example_2_Retail_Ledger/app_workflow/1.tds",
}


def summarize(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {
        "calls": len(ordered),
        "total_ms": round(sum(ordered) * 1000, 2),
        "max_ms": round(ordered[-1] * 1000, 2),
    }


def measure(stack: ExitStack, cls: type, name: str, samples: dict, label: str):
    original = getattr(cls, name)

    @wraps(original)
    def timed(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return original(self, *args, **kwargs)
        finally:
            samples[label].append(time.perf_counter() - start)

    stack.enter_context(patch.object(cls, name, timed))


def snapshot_nodes(nodes) -> dict:
    """Fingerprint actual node outputs after timing, for before/after checks."""
    import polars as pl

    snapshots = {}
    for node in nodes:
        value = getattr(node, "value", None)
        entries = value if isinstance(value, list) else [value]
        outputs = []
        for entry in entries:
            if not isinstance(entry, dict) or "data" not in entry:
                continue
            data = entry["data"]
            if isinstance(data, pl.LazyFrame):
                data = data.collect()
            if isinstance(data, pl.DataFrame):
                buffer = io.BytesIO()
                # GroupBy does not promise row order; compare the same rows
                # regardless of the hash-table iteration order of a run.
                data.sort(data.columns).write_ipc(buffer)
                outputs.append(
                    {
                        "shape": list(data.shape),
                        "schema": {k: str(v) for k, v in data.schema.items()},
                        "sha256": hashlib.sha256(buffer.getvalue()).hexdigest(),
                    }
                )
        snapshots[str(node.id)] = {
            "type": type(node).__name__,
            "invalid": node.isInvalid(),
            "outputs": outputs,
        }
    return snapshots


def run(
    path: Path, detailed: bool, snapshot: bool = False, force_settle: bool = False
) -> dict:
    samples: dict[str, list[float]] = defaultdict(list)
    eval_stack: list[list[float]] = []  # [start, nested evalImplementation seconds]
    before_eval_counts: dict[str, int] = {}
    first_pass_counts: dict[str, int] = {}
    profile = cProfile.Profile() if detailed else None
    started = time.perf_counter()
    window = TriggerSubWindow()
    window._show_workflow_validation_warnings = lambda *a, **kw: None
    window_ready = time.perf_counter()

    # NodeEditorWidget.fileLoad includes disk I/O, JSON parsing, and scene
    # deserialize. The latter is timed separately to split out I/O + parsing.
    with ExitStack() as stack:
        for cls, method, label in (
            (NodeEditorWidget, "fileLoad", "base_file_load"),
            (TriggerScene, "deserialize", "scene_deserialize"),
            (TriggerScene, "endBulkLoad", "edge_finalization"),
            (TriggerSubWindow, "validateConnections", "connections"),
            (TriggerSubWindow, "validateLoadedWorkflow", "validation"),
            (TriggerSubWindow, "doEvalOutputs", "evaluation"),
        ):
            measure(stack, cls, method, samples, label)

        measured_eval = TriggerSubWindow.doEvalOutputs

        @wraps(measured_eval)
        def timed_eval(self, *args, **kwargs):
            before_eval_counts.update(
                {
                    key: len(value)
                    for key, value in samples.items()
                    if key.startswith("node_eval/")
                }
            )
            return measured_eval(self, *args, **kwargs)

        stack.enter_context(patch.object(TriggerSubWindow, "doEvalOutputs", timed_eval))

        # Separate the initial graph walk from the deliberate Union re-settle
        # pass. evalImplementation is called only for real recomputes (not
        # cached eval() calls), so snapshots give accurate per-pass counts.
        from trigger_designer.qt import design_window

        original_settle = design_window.settle_multi_input_nodes

        def timed_settle(scene):
            first_pass_counts.update(
                {
                    key: len(value)
                    for key, value in samples.items()
                    if key.startswith("node_eval/")
                }
            )
            start = time.perf_counter()
            try:
                if force_settle:
                    from nodeeditor.node_multi_input_node import MultiInputNode

                    collectors = [
                        node for node in scene.nodes if isinstance(node, MultiInputNode)
                    ]
                    for node in collectors:
                        node.markDirty(True)
                        node.markDescendantsDirty(True)
                    if collectors:
                        for node in scene.nodes:
                            node.eval()
                    return None
                return original_settle(scene)
            finally:
                samples["union_settle"].append(time.perf_counter() - start)

        stack.enter_context(
            patch.object(design_window, "settle_multi_input_nodes", timed_settle)
        )

        # Wrap the concrete node classes from the saved file. This separates
        # construction from property restoration even for overridden methods.
        data = json.loads(path.read_text(encoding="utf-8"))
        classes = {window.getNodeClassFromData(n) for n in data["nodes"]}
        for cls in classes:
            for method, label in (
                ("__init__", "node_init"),
                ("deserialize", "node_restore"),
                ("evalImplementation", "node_eval"),
            ):
                original = getattr(cls, method)

                @wraps(original)
                def timed(self, *args, _original=original, _label=label, **kwargs):
                    start = time.perf_counter()
                    if _label == "node_eval":
                        eval_stack.append([start, 0.0])
                    try:
                        return _original(self, *args, **kwargs)
                    finally:
                        elapsed = time.perf_counter() - start
                        samples[f"{_label}/{type(self).__name__}"].append(elapsed)
                        if _label == "node_eval":
                            _, nested = eval_stack.pop()
                            samples[f"node_eval_self/{type(self).__name__}"].append(
                                max(0.0, elapsed - nested)
                            )
                            if eval_stack:
                                eval_stack[-1][1] += elapsed

                stack.enter_context(patch.object(cls, method, timed))

        if profile:
            profile.enable()
        try:
            loaded = window.fileLoad(str(path))
        finally:
            if profile:
                profile.disable()
        loaded_at = time.perf_counter()

    if not loaded:
        raise RuntimeError(f"Workflow did not load: {path}")

    # Build a real dock for each representative node type, including tearing
    # down the previous panel. This exercises the same selection UI as the app.
    dock = ConfigDock()
    dock_samples: dict[str, list[float]] = defaultdict(list)
    with ExitStack() as stack:
        measure(stack, ConfigDock, "clear_dock", samples, "dock_clear")
        for content_cls in {type(node.content) for node in window.scene.nodes}:
            for method, label in (
                ("create_layout", "dock_layout"),
                ("registerUnboundDockWidgets", "dock_bind"),
            ):
                if hasattr(content_cls, method):
                    measure(stack, content_cls, method, samples, label)
        for node in window.scene.nodes:
            start = time.perf_counter()
            dock.updateConfig([node.grNode])
            dock_samples[type(node).__name__].append(time.perf_counter() - start)
        dock.updateConfig([])

    try:
        workflow_name = path.relative_to(ROOT).as_posix()
    except ValueError:
        workflow_name = str(path)
    out = {
        "workflow": workflow_name,
        "nodes": len(window.scene.nodes),
        "edges": len(window.scene.edges),
        "startup_ms": {
            "qt_create": round((QT_READY - START) * 1000, 2),
            "imports_after_qt": round((IMPORTS_READY - QT_READY) * 1000, 2),
            "window_create": round((window_ready - started) * 1000, 2),
        },
        "load_wall_ms": round((loaded_at - window_ready) * 1000, 2),
        "phases": {
            k: summarize(v)
            for k, v in samples.items()
            if "/" not in k and not k.startswith("dock_")
        },
        "node_init": {
            k.removeprefix("node_init/"): summarize(v)
            for k, v in samples.items()
            if k.startswith("node_init/")
        },
        "node_restore": {
            k.removeprefix("node_restore/"): summarize(v)
            for k, v in samples.items()
            if k.startswith("node_restore/")
        },
        "node_eval_inclusive": {
            k.removeprefix("node_eval/"): summarize(v)
            for k, v in samples.items()
            if k.startswith("node_eval/")
        },
        "node_eval_self": {
            k.removeprefix("node_eval_self/"): summarize(v)
            for k, v in samples.items()
            if k.startswith("node_eval_self/")
        },
        "recomputes_by_pass": {
            "before_eval": {
                k.removeprefix("node_eval/"): count
                for k, count in before_eval_counts.items()
            },
            "first": {
                k.removeprefix("node_eval/"): count - before_eval_counts.get(k, 0)
                for k, count in first_pass_counts.items()
                if count > before_eval_counts.get(k, 0)
            },
            "union_settle": {
                k.removeprefix("node_eval/"): len(v) - first_pass_counts.get(k, 0)
                for k, v in samples.items()
                if k.startswith("node_eval/") and len(v) > first_pass_counts.get(k, 0)
            },
        },
        "dock_phases": {
            k: summarize(v) for k, v in samples.items() if k.startswith("dock_")
        },
        "dock_selection": {k: summarize(v) for k, v in dock_samples.items()},
    }
    if profile:
        out["profile"] = profile
    if snapshot:
        out["output_snapshot"] = snapshot_nodes(window.scene.nodes)
    window.close()
    dock.close()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", choices=WORKFLOWS, default="large")
    parser.add_argument("--file", type=Path, help="Override with any saved .tds")
    parser.add_argument(
        "--cprofile",
        action="store_true",
        help="Save load-only cProfile stats (slows timings)",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Fingerprint node outputs for correctness comparison",
    )
    parser.add_argument(
        "--force-settle",
        action="store_true",
        help="Benchmark the old unconditional Union pass for A/B comparisons",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Repeat in one process to separate cold and warm loads",
    )
    parser.add_argument("--label", default="", help="Label written profile artifacts")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    path = (args.file or WORKFLOWS[args.workflow]).resolve()
    output_dir = ROOT / "profiles"
    output_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    for index in range(args.repeats):
        result = run(path, args.cprofile, args.snapshot, args.force_settle)
        name = f"load_{path.stem}_{stamp}_{args.label}_{index + 1}"
        profile = result.pop("profile", None)
        if profile:
            prof_path = output_dir / f"{name}.prof"
            profile.dump_stats(str(prof_path))
            result["cprofile_file"] = str(prof_path.relative_to(ROOT))
        json_path = output_dir / f"{name}.json"
        json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"{result['workflow']}: {result['nodes']} nodes, {result['edges']} edges")
        print(f"Load {index + 1}/{args.repeats}: {result['load_wall_ms']:.0f} ms")
        for phase, stats in sorted(
            result["phases"].items(), key=lambda item: item[1]["total_ms"], reverse=True
        ):
            print(f"  {phase}: {stats['total_ms']:.0f} ms")
        for phase, counts in result["recomputes_by_pass"].items():
            print(f"  {phase} recomputes: {sum(counts.values())}")
        print("Dock selection (separate from load):")
        for phase, stats in result["dock_phases"].items():
            print(f"  {phase}: {stats['total_ms']:.0f} ms / {stats['calls']} calls")
        print("Slowest node types (exclusive eval):")
        for node_type, stats in sorted(
            result["node_eval_self"].items(),
            key=lambda item: item[1]["total_ms"],
            reverse=True,
        )[:5]:
            print(f"  {node_type}: {stats['total_ms']:.0f} ms ({stats['calls']} calls)")
        print(f"Saved: {json_path}")


if __name__ == "__main__":
    main()
