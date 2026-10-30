"""Sample end to end: File Input -> Sample -> three File Outputs.

The same seed must give the same sample on every Run, and the Selection log that
the third output writes must be enough to see how the draw was made.
"""

from __future__ import annotations

import json
from collections import Counter

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.audit_ledger import make_ledger
from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.audit.sampling import (
    LOG_COLUMNS,
    SamplingParams,
    run_sample,
)
from trigger_designer.core.node_configuration import (
    AuditNodes,
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


SETTINGS = {
    "random": {"sample_size": 60},
    "systematic": {"sample_size": 60},
    "mus": {"sample_size": 40, "amount_column": "amount"},
    "stratified": {
        "amount_column": "amount",
        "band_edges": [1000.0, 10000.0],
        "band_sizes": [10, 10, 25],
    },
}


def _build(root, method: str, source=None, **extra):
    ledger = make_ledger().frame
    source = source or root / "ledger.csv"
    if not source.exists():
        ledger.write_csv(source)
    out_dir = root / "out"
    out_dir.mkdir(exist_ok=True)
    paths = {k: out_dir / f"{k}.csv" for k in ("sample", "rest", "log")}

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    sample = get_class_from_opcode(AuditNodes.SAMPLE, NodeTypes.AUDIT)(scene)
    outputs = [
        get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene) for _ in paths
    ]

    file_input.content.filePath = str(source)
    file_input.content.file_type = "csv"
    settings = {
        "method": method,
        "key_columns": ["je_number"],
        **SETTINGS[method],
        **extra,
    }
    for name, value in settings.items():
        setattr(sample.content, name, value)
    for output, path in zip(outputs, paths.values()):
        output.content.settings["filePath"] = str(path)
        output.content.settings["file_format"] = "csv"

    Edge(scene, file_input.outputs[0], sample.inputs[0])
    for socket, output in enumerate(outputs):
        Edge(scene, sample.outputs[socket], output.inputs[0])
    tds = root / f"sample_{method}_{source.stem}.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, paths, settings


def _run(qtbot, tds):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    return window


def _read(path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema=False)


@pytest.mark.parametrize("method", list(SETTINGS))
def test_same_seed_gives_identical_output_twice(qtbot, tmp_path, method) -> None:
    tds, paths, settings = _build(tmp_path, method)
    window = _run(qtbot, tds)
    assert len(window.execution_results) == len(window.getAllNodes())
    first = {k: p.read_bytes() for k, p in paths.items()}
    for path in paths.values():
        path.unlink()

    run_workflow_and_wait(qtbot, window)  # same window, second Run
    assert {k: p.read_bytes() for k, p in paths.items()} == first

    again = _run(qtbot, tds)  # a freshly loaded copy of the file
    assert {k: p.read_bytes() for k, p in paths.items()} == first
    del again

    sample, rest, log = (_read(paths[k]) for k in ("sample", "rest", "log"))
    ledger = make_ledger().frame
    assert sample.height + rest.height == ledger.height
    # je_number repeats in the ledger, so compare the multiset of values.
    assert Counter(sample["je_number"]) + Counter(rest["je_number"]) == Counter(
        ledger["je_number"]
    )
    assert sample["sample_seq"].is_not_null().all()
    assert list(log.columns) == list(LOG_COLUMNS)
    overall = log.filter(pl.col("scope") == "overall").row(0, named=True)
    assert overall["population_rows"] == str(ledger.height)
    assert overall["seed"] == "42" and overall["algorithm"] == "td-sample-1"
    assert overall["sample_size"] == str(sample.height)
    # The parameters in the log are the settings of the node.
    logged = json.loads(overall["parameters"])
    assert {k: logged[k] for k in settings} == settings

    # Re-performing the draw from the logged parameters gives the same rows.
    redo = run_sample(
        pl.read_csv(tmp_path / "ledger.csv"), SamplingParams.from_dict(logged)
    )
    assert (
        redo.frames[0].collect()["je_number"].to_list() == sample["je_number"].to_list()
    )


def test_a_different_seed_changes_the_sample(qtbot, tmp_path) -> None:
    tds, paths, _settings = _build(tmp_path, "random")
    _run(qtbot, tds)
    first = _read(paths["sample"])["je_number"].to_list()
    other = tmp_path / "other"
    other.mkdir()
    tds2, paths2, _ = _build(other, "random", seed=43)
    _run(qtbot, tds2)
    second = _read(paths2["sample"])["je_number"].to_list()
    assert first != second and len(first) == len(second) == 60


def test_the_same_ledger_in_another_row_order_gives_the_same_sample(
    qtbot, tmp_path
) -> None:
    ledger = make_ledger().frame
    tds, paths, _ = _build(tmp_path, "mus")
    _run(qtbot, tds)
    expected = _read(paths["sample"])

    shuffled = ledger.sample(fraction=1.0, shuffle=True, seed=7)
    assert shuffled["je_number"].to_list() != ledger["je_number"].to_list()
    other = tmp_path / "shuffled"
    other.mkdir()
    shuffled.write_csv(other / "ledger.csv")
    tds2, paths2, _ = _build(other, "mus", source=other / "ledger.csv")
    _run(qtbot, tds2)
    got = _read(paths2["sample"])
    assert set(got["je_number"]) == set(expected["je_number"])
    ranks = dict(zip(expected["je_number"], expected["sample_seq"]))
    assert all(ranks[j] == s for j, s in zip(got["je_number"], got["sample_seq"]))
