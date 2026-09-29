#!/usr/bin/env python3
"""Benchmark harness for "Run Workflow" execution.

Loads a handful of saved .tds workflows headlessly and times how long it
takes NodeExecutor.execute_node() to run every node in the graph, from the
moment executeWorkflow() is called to the moment the LAST node's
execute_node() call returns. That measurement point is deliberately
redesign-agnostic: NodeExecutor.execute_node's role and call signature are
unchanged whether the outer node loop lives on the GUI thread (a
QTimer.singleShot chain) or on a background WorkflowWorker thread, so this
script produces numbers that are directly comparable before and after that
change. It deliberately excludes the workflow's own fixed ~1s cosmetic
completion delay (see _execution_cleanup), which would otherwise pad every
measurement by a constant amount unrelated to actual execution speed.

Usage:
    python scripts/benchmark_workflow_execution.py --label baseline
    python scripts/benchmark_workflow_execution.py --label after
    python scripts/benchmark_workflow_execution.py --compare
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Several node/UI modules print emoji straight to stdout; on a raw Windows
# console (cp1252) that raises UnicodeEncodeError and aborts the run. Force
# UTF-8 so this script works the same whether launched from a UTF-8-aware
# terminal or not.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import psutil
from qtpy.QtCore import QEventLoop, QTimer
from qtpy.QtWidgets import QApplication

# A QApplication must exist before any Qt widget/graphics-object-touching
# module is imported (some of this app's modules build icons/pixmaps as a
# side effect of import), so construct it before importing design_window.
_APP = QApplication.instance() or QApplication([])

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.qt.design_window import TriggerSubWindow

RESULTS_DIR = REPO_ROOT / "scripts" / "benchmark_results"

SAVED_FILES = {
    "small_2node": REPO_ROOT / "savedfiles" / "1. in-select.tds",
    "medium_14node": REPO_ROOT / "savedfiles" / "Example_1" / "Test1.tds",
    "large_105node": (
        REPO_ROOT / "savedfiles" / "Example_2_Retail_Ledger" / "app_workflow" / "1.tds"
    ),
}

REPEATS = 5
# Safety valve so a broken/hung run can't hang the benchmark forever.
PER_RUN_TIMEOUT_MS = 60_000


def _run_one(path: Path) -> dict:
    """Load `path` and run its workflow once, returning timing/memory info."""
    window = TriggerSubWindow()
    # Never let a validation-warning dialog try to pop up and block headless.
    window._show_workflow_validation_warnings = lambda *args, **kwargs: None

    loaded = window.fileLoad(str(path))
    if not loaded:
        raise RuntimeError(f"Failed to load {path}")

    node_timestamps: list[float] = []
    original_execute_node = NodeExecutor.execute_node

    def _wrapped_execute_node(self, node):
        result = original_execute_node(self, node)
        node_timestamps.append(time.perf_counter())
        return result

    NodeExecutor.execute_node = _wrapped_execute_node

    loop = QEventLoop()
    original_cleanup = window._execution_cleanup

    def _wrapped_cleanup(success=True):
        original_cleanup(success)
        loop.quit()

    window._execution_cleanup = _wrapped_cleanup

    process = psutil.Process(os.getpid())
    rss_before = process.memory_info().rss / (1024 * 1024)

    try:
        t0 = time.perf_counter()
        window.executeWorkflow()
        QTimer.singleShot(PER_RUN_TIMEOUT_MS, loop.quit)
        loop.exec_()
    finally:
        NodeExecutor.execute_node = original_execute_node

    rss_after = process.memory_info().rss / (1024 * 1024)
    stats = window.get_workflow_statistics()
    time_to_last_node = (node_timestamps[-1] - t0) if node_timestamps else None

    window.close()
    window.deleteLater()

    return {
        "node_count": len(node_timestamps),
        "time_to_last_node_s": time_to_last_node,
        "last_execution_time_s": stats["last_execution_time"],
        "rss_delta_mb": rss_after - rss_before,
        "execution_results_count": len(window.execution_results),
    }


def run_benchmark(repeats: int = REPEATS, only: str | None = None) -> dict:
    QApplication.instance() or QApplication([])
    results: dict = {}

    files = SAVED_FILES if only is None else {only: SAVED_FILES[only]}

    for name, path in files.items():
        if not path.exists():
            print(f"  [skip] {name}: {path} not found")
            continue

        runs = []
        for i in range(repeats):
            run = _run_one(path)
            runs.append(run)
            print(
                f"  {name} run {i + 1}/{repeats}: "
                f"{run['node_count']} nodes, "
                f"time_to_last_node={run['time_to_last_node_s']}, "
                f"rss_delta={run['rss_delta_mb']:.1f}MB"
            )

        times = [
            r["time_to_last_node_s"]
            for r in runs
            if r["time_to_last_node_s"] is not None
        ]
        results[name] = {
            "runs": runs,
            "avg_time_to_last_node_s": sum(times) / len(times) if times else None,
            "min_time_to_last_node_s": min(times) if times else None,
            "max_time_to_last_node_s": max(times) if times else None,
        }

    return results


def compare(baseline: dict, after: dict) -> None:
    header = f"{'workflow':<16} {'baseline avg':>14} {'after avg':>12} {'delta':>10} {'speedup':>10}"
    print(f"\n{header}")
    for name in baseline:
        if name not in after:
            continue
        b = baseline[name]["avg_time_to_last_node_s"]
        a = after[name]["avg_time_to_last_node_s"]
        if b is None or a is None:
            continue
        delta = a - b
        speedup = b / a if a else float("inf")
        print(f"{name:<16} {b:>13.3f}s {a:>11.3f}s {delta:>+9.3f}s {speedup:>9.2f}x")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label",
        choices=["baseline", "after"],
        help="Run the benchmark and save results under this label",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Print a comparison of previously saved baseline vs after results",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=REPEATS,
        help="Runs per saved file (default: %(default)s)",
    )
    parser.add_argument(
        "--only", choices=sorted(SAVED_FILES), help="Only benchmark this one saved file"
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.compare:
        baseline_path = RESULTS_DIR / "baseline.json"
        after_path = RESULTS_DIR / "after.json"
        if not baseline_path.exists() or not after_path.exists():
            print("Need both baseline.json and after.json to compare.")
            return
        compare(
            json.loads(baseline_path.read_text()), json.loads(after_path.read_text())
        )
        return

    if not args.label:
        parser.error("--label is required unless --compare is given")

    print(f"Running benchmark, label={args.label}...")
    results = run_benchmark(repeats=args.repeats, only=args.only)
    out_path = RESULTS_DIR / f"{args.label}.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
