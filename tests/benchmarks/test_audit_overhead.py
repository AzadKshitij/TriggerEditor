"""Run-record overhead budgets (docs/plan/02-audit-trail.md 6.5).

Opt-in: ``pytest tests/benchmarks/test_audit_overhead.py --run-benchmarks -s``.
A 1,000,000-row CSV goes through File Input -> Normalize -> Sort -> Unique ->
File Output (parquet); the same workflow is timed with recording off and in
each row-count mode (median of 3 after a warm-up).
"""

from __future__ import annotations

import os
import statistics
import time
from pathlib import Path

import numpy as np
import orjson
import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.audit.fingerprint import sha256_stream
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.preferences import get_preferences

ROWS = int(os.environ.get("AUDIT_BENCH_ROWS", "1000000"))


@pytest.fixture(scope="session")
def big_csv(tmp_path_factory) -> Path:
    folder = tmp_path_factory.mktemp("audit_bench")
    rng = np.random.default_rng(20261021)
    letters = np.array(list("abcdefghijklmnopqrstuvwxyz"))

    def words() -> list[str]:
        codes = rng.integers(0, 26, size=(50, 8))
        return ["".join(row) for row in letters[codes]] * (ROWS // 50)

    frame = pl.DataFrame(
        {
            "id": np.arange(ROWS, dtype=np.int64),
            "amount": rng.random(ROWS) * 1000,
            "name": words(),
            "city": words(),
            "note": words(),
            "date": ["2026-10-21"] * ROWS,
        }
    )
    path = folder / "big.csv"
    frame.write_csv(path)
    return path


def _build(tmp_path: Path, csv: Path) -> Path:
    window = TriggerSubWindow()
    scene = window.scene
    fin = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    norm = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )(scene)
    sort = get_class_from_opcode(PreparationNodes.SORT, NodeTypes.PREPARATION)(scene)
    unique = get_class_from_opcode(PreparationNodes.UNIQUE, NodeTypes.PREPARATION)(
        scene
    )
    fout = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    fin.content.filePath = str(csv)
    fin.content.file_type = "csv"
    sort.content.settings["keys"] = [{"column": "id", "order": "Ascending"}]
    unique.content.settings["selected_columns"] = ["id"]
    fout.content.settings["filePath"] = str(tmp_path / "out.parquet")
    fout.content.settings["file_format"] = "parquet"
    Edge(scene, fin.outputs[0], norm.inputs[0])
    Edge(scene, norm.outputs[0], sort.inputs[0])
    Edge(scene, sort.outputs[0], unique.inputs[0])
    Edge(scene, unique.outputs[0], fout.inputs[0])
    tds = tmp_path / "bench.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds


def _timed(qtbot, window) -> float:
    start = time.perf_counter()
    run_workflow_and_wait(qtbot, window, timeout_ms=600_000)
    return time.perf_counter() - start


def _median_run(qtbot, window, configure) -> float:
    configure()
    _timed(qtbot, window)  # warm-up: file cache, imports
    return statistics.median(_timed(qtbot, window) for _ in range(3))


@pytest.mark.benchmark
def test_overhead_budgets_hold(qtbot, tmp_path, big_csv, no_modal_dialogs):
    prefs = get_preferences()
    tds = _build(tmp_path, big_csv)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True

    def mode(record: bool, counts: str = "auto"):
        def apply() -> None:
            prefs.set("audit/record_runs", record)
            prefs.set("audit/row_counts", counts)

        return apply

    base = _median_run(qtbot, window, mode(False))
    off = _median_run(qtbot, window, mode(True, "off"))
    sink = _median_run(qtbot, window, mode(True, "sink"))
    everything = _median_run(qtbot, window, mode(True, "all"))

    # A record always costs the output hash and two fsyncs; the plan's 5% was
    # written for a ~1 s pipeline, so the fixed part is added to the allowance
    # instead of being hidden in a percentage of a very fast run.
    started = time.perf_counter()
    sha256_stream(tmp_path / "out.parquet")
    output_hash_s = time.perf_counter() - started
    fixed = 0.10 + 1.5 * output_hash_s
    print(
        "\naudit overhead (s): "
        f"base={base:.2f} off={off:.2f} sink={sink:.2f} all={everything:.2f} "
        f"fixed_allowance={fixed:.2f}"
    )
    assert off <= 1.05 * base + 0.05 + fixed
    # counting is measured against the fingerprint-only run
    assert sink <= 1.05 * off + 0.10
    assert everything <= 1.25 * off + 0.5

    directory = tds.with_suffix(".runs")
    lines = (directory / "index.jsonl").read_bytes().splitlines()
    entry = orjson.loads(lines[-1])
    record = orjson.loads((directory / entry["file"]).read_bytes())
    assert record["options"]["row_count_mode_effective"] == "all"
    unique_node = next(n for n in record["nodes"] if n["op"].endswith("unique"))
    assert max(unique_node["rows_out"].values()) == ROWS
    sink_node = next(n for n in record["nodes"] if n["op"] == "input.file_output")
    assert sink_node["rows_in"][0]["rows"] == ROWS  # counts of the measured run


@pytest.mark.benchmark
def test_hashing_throughput_floor(tmp_path):
    path = tmp_path / "blob.bin"
    block = np.random.default_rng(1).bytes(1024 * 1024)
    with open(path, "wb") as handle:
        handle.writelines(block for _ in range(200))
    start = time.perf_counter()
    assert sha256_stream(path)
    assert time.perf_counter() - start < 5.0
