"""The CLI and the editor's Run must agree (plan 08 6.2 ``test_gui_and_cli_parity``).

The same workflow runs once through ``TriggerSubWindow`` + ``WorkflowWorker``
(the Run button) and once through ``trigger-designer-cli``; outputs and run
records are compared. The policy corpus test lives here too: it loads every
checked-in workflow and asserts the generated code passes the CLI's safety
policy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl
import pytest

from tests.support.cli import run_cli
from tests.support.corpus import FILE_OUTPUT_CASES
from tests.support.frames import read_frame
from tests.support.workflows import REPO_ROOT, materialize, run_workflow_and_wait
from trigger_designer.core.audit.store import RunStore

pytestmark = pytest.mark.e2e

UNORDERED = {c.name for c in FILE_OUTPUT_CASES if c.unordered_goldens}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest(folder: Path) -> dict:
    files = sorted(
        (p for p in folder.glob("*.json") if p.name != "hash_cache.json"),
        key=lambda p: p.stat().st_mtime,
    )
    assert files, f"no record in {folder}"
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _shape(record: dict) -> dict:
    return {
        "status": record["status"],
        "ops": [n["op"] for n in record["nodes"]],
        "statuses": [n["status"] for n in record["nodes"]],
        # variable names embed node ids, which v1 files regenerate on every load
        "rows_out": [sorted(n["rows_out"].values()) for n in record["nodes"]],
        "inputs": sorted((Path(i["path"]).name, i["sha256"]) for i in record["inputs"]),
        "outputs": sorted(
            (Path(o["path"]).name, o["sha256"]) for o in record["outputs"]
        ),
        "graph": record["graph_sha256"],
    }


@pytest.mark.parametrize("case", FILE_OUTPUT_CASES, ids=lambda c: c.name)
def test_gui_and_cli_parity(case, qtbot, tmp_path, no_modal_dialogs, monkeypatch):
    from trigger_designer.qt.design_window import TriggerSubWindow

    gui_dir, cli_dir = tmp_path / "gui", tmp_path / "cli"
    gui = materialize(case, gui_dir)
    cli = materialize(case, cli_dir)

    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(gui.path)) is True
    run_workflow_and_wait(qtbot, window)

    proc = run_cli(
        "run",
        cli.path,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        cli_dir / "rec",
        cwd=cli_dir,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]

    for basename in case.goldens:
        a, b = gui.out_dir / basename, cli.out_dir / basename
        assert a.exists() and b.exists(), basename
        if case.name in UNORDERED:
            fa, fb = read_frame(a), read_frame(b)
            assert fa.columns == fb.columns
            cols = fa.columns
            assert fa.sort(cols).equals(fb.sort(cols)), basename
        else:
            assert _sha(a) == _sha(b), f"{basename} differs between GUI and CLI"

    gui_record = RunStore().load_dict(
        next(p for p in gui_dir.glob("*.runs/*.json") if p.name != "hash_cache.json")
    )
    cli_record = _latest(cli_dir / "rec")
    shape_gui, shape_cli = _shape(gui_record), _shape(cli_record)
    if case.name in UNORDERED:
        for key in ("outputs",):
            shape_gui.pop(key), shape_cli.pop(key)
    assert [s for s in shape_cli["statuses"]] == [s for s in shape_gui["statuses"]]
    assert shape_cli["ops"] == shape_gui["ops"]
    assert shape_cli["rows_out"] == shape_gui["rows_out"]
    assert shape_cli["status"] == shape_gui["status"] == "ok"
    assert len(shape_cli["inputs"]) == len(shape_gui["inputs"])
    assert [h for _n, h in shape_cli["inputs"]] == [h for _n, h in shape_gui["inputs"]]
    if "outputs" in shape_cli:
        assert shape_cli["outputs"] == shape_gui["outputs"]
    assert cli_record["generated_code"] and gui_record["generated_code"]


def test_scene_save_keeps_the_parameters_block(qtbot, tmp_path, no_modal_dialogs):
    """A GUI save must not drop ``workflow_metadata.parameters`` (plan 08 3.5.8)."""
    from trigger_designer.qt.design_window import TriggerSubWindow

    case = FILE_OUTPUT_CASES[1]
    m = materialize(case, tmp_path)
    data = json.loads(m.path.read_text(encoding="utf-8"))
    block = [{"name": "p", "type": "string", "node_id": 1, "setting": "value"}]
    data["workflow_metadata"] = {"schema_version": 2, "parameters": block}
    m.path.write_text(json.dumps(data), encoding="utf-8")
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(m.path)) is True
    saved = tmp_path / "saved.tds"
    assert window.scene.saveToFile(str(saved)) in (None, True)
    out = json.loads(saved.read_text(encoding="utf-8"))
    assert out["workflow_metadata"]["parameters"] == block


def _corpus_files() -> list[Path]:
    found = []
    for pattern in ("savedfiles/*.tds", "tests/e2e/workflows/*.tds", "data/*.tds"):
        found.extend(sorted(REPO_ROOT.glob(pattern)))
    return found


@pytest.mark.slow
def test_corpus_passes_policy(qtbot, no_modal_dialogs):
    """Every checked-in workflow's generated code is accepted by the policy."""
    from trigger_designer.core.headless.code_policy import validate_generated_code
    from trigger_designer.qt.design_window import TriggerSubWindow

    checked = refused = 0
    skipped: list[str] = []
    for path in _corpus_files():
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        window = TriggerSubWindow()
        qtbot.addWidget(window)
        if not window.fileLoad(str(path)):
            continue
        for node in window.getAllNodes():
            try:
                code = node.get_code()
            except Exception as exc:  # noqa: BLE001 - an unfinished node has no code
                skipped.append(f"{path.name}: {node.node_title}: {exc}")
                continue
            checked += 1
            try:
                validate_generated_code(code, io_paths=None)
            except Exception as exc:  # noqa: BLE001
                refused += 1
                pytest.fail(f"{path.name}: {node.node_title}: {exc}")
    assert checked >= 40 and refused == 0
    assert pl is not None
