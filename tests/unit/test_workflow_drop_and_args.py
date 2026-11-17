"""Which command-line arguments and dragged items name workflow files to open."""

from __future__ import annotations

import os

import pytest
from qtpy.QtCore import QMimeData, QUrl

from trigger_designer.main import files_from_argv
from trigger_designer.qt.helpers.workflow_drop import workflow_paths

pytestmark = pytest.mark.unit


def _mime(*targets) -> QMimeData:
    mime = QMimeData()
    mime.setUrls(
        [t if isinstance(t, QUrl) else QUrl.fromLocalFile(str(t)) for t in targets]
    )
    return mime


@pytest.fixture
def workflows(tmp_path):
    made = {}
    for name in ("a.tds", "B.TDS", "c.tds"):
        path = tmp_path / name
        path.write_text("{}", encoding="utf-8")
        made[name] = path
    (tmp_path / "data.csv").write_text("x\n1\n", encoding="utf-8")
    (tmp_path / "folder.tds").mkdir()  # a folder that happens to end in .tds
    return made


# ------------------------------------------------------------- command line
def test_a_path_from_explorer_is_the_file_to_open(tmp_path):
    path = str(tmp_path / "My Workflow.tds")
    assert files_from_argv(["TriggerEditor.exe", path]) == [path]


def test_no_arguments_means_no_file():
    assert files_from_argv(["TriggerEditor.exe"]) == []


def test_every_file_named_is_returned_in_order(tmp_path):
    first, second = str(tmp_path / "one.tds"), str(tmp_path / "two.tds")
    assert files_from_argv(["x", first, second]) == [first, second]


def test_a_dash_argument_and_its_value_are_handled_like_qt_does(tmp_path):
    """Qt's own ``-platform offscreen`` reaches us in sys.argv: the flag is
    dropped, and the word after it is just another (non-existent) path that the
    open step will refuse. A real workflow after them is still found."""
    path = str(tmp_path / "a.tds")
    result = files_from_argv(["x", "-platform", "offscreen", path])
    assert path in result and not any(r.startswith("-") for r in result)


def test_the_same_file_written_twice_is_opened_once(tmp_path):
    path = str(tmp_path / "a.tds")
    assert files_from_argv(["x", path, path, path.upper()]) == [path]


def test_a_relative_path_becomes_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert files_from_argv(["x", "flow.tds"]) == [str(tmp_path / "flow.tds")]


# ------------------------------------------------------------- drag and drop
def test_a_dropped_workflow_is_found(workflows):
    assert workflow_paths(_mime(workflows["a.tds"])) == [
        os.path.normpath(str(workflows["a.tds"]))
    ]


def test_the_extension_is_not_case_sensitive(workflows):
    assert workflow_paths(_mime(workflows["B.TDS"])) == [
        os.path.normpath(str(workflows["B.TDS"]))
    ]


def test_several_workflows_come_back_in_order_and_once_each(workflows):
    got = workflow_paths(
        _mime(workflows["c.tds"], workflows["a.tds"], workflows["c.tds"])
    )
    assert [os.path.basename(p) for p in got] == ["c.tds", "a.tds"]


def test_other_files_folders_and_missing_files_are_not_workflows(workflows, tmp_path):
    mime = _mime(
        tmp_path / "data.csv",
        tmp_path / "folder.tds",
        tmp_path / "gone.tds",
        workflows["a.tds"],
    )
    assert [os.path.basename(p) for p in workflow_paths(mime)] == ["a.tds"]


def test_a_web_link_is_not_a_workflow():
    assert workflow_paths(_mime(QUrl("https://example.com/flow.tds"))) == []


def test_text_or_an_empty_drag_has_no_workflows():
    mime = QMimeData()
    mime.setText("flow.tds")
    assert workflow_paths(mime) == []
    assert workflow_paths(QMimeData()) == []
    assert workflow_paths(None) == []
