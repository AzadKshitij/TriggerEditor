"""Drop a .tds file on the editor to open it (and Explorer-style paths on the
command line), through real Qt drag events."""

from __future__ import annotations

import pytest
from qtpy.QtCore import QByteArray, QMimeData, QPoint, QPointF, Qt, QUrl
from qtpy.QtGui import QDragEnterEvent, QDropEvent
from qtpy.QtWidgets import QApplication

from trigger_designer.core.authoring import Editor, new_workflow
from trigger_designer.core.headless.params import dump_workflow
from trigger_designer.qt.design_window import LISTBOX_MIMETYPE
from trigger_designer.qt.main_window import TriggerWindow

pytestmark = pytest.mark.ui

COPY = Qt.DropAction.CopyAction
LEFT = Qt.MouseButton.LeftButton
NONE = Qt.KeyboardModifier.NoModifier


def _workflow(folder, name: str, nodes: int = 1):
    editor = Editor(new_workflow(), base_dir=str(folder))
    for _ in range(nodes):
        editor.add_node("preparation.sort")
    path = folder / name
    path.write_bytes(dump_workflow(editor.data))
    return path


def _mime(*files) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(f)) for f in files])
    return mime


def _enter(widget, mime) -> bool:
    event = QDragEnterEvent(QPoint(5, 5), COPY, mime, LEFT, NONE)
    QApplication.sendEvent(widget, event)
    return event.isAccepted()


def _drop(widget, mime) -> bool:
    event = QDropEvent(QPointF(5, 5), COPY, mime, LEFT, NONE)
    QApplication.sendEvent(widget, event)
    return event.isAccepted()


@pytest.fixture
def window():
    # Not qtbot.addWidget: closing a TriggerWindow quits the shared application
    # (tests/conftest.py), so it is hidden and deleted here instead.
    win = TriggerWindow()
    win.resize(1200, 800)
    win.show()
    yield win
    win.hide()
    win.deleteLater()
    QApplication.processEvents()


def _open_count(window) -> int:
    return len(window.mdiArea.subWindowList())


def test_the_window_accepts_dropped_files(window):
    assert window.acceptDrops() is True


def test_a_dropped_workflow_opens_in_a_new_window(window, tmp_path, qtbot):
    flow = _workflow(tmp_path, "flow.tds", nodes=2)
    mime = _mime(flow)

    assert _enter(window, mime) is True  # the pointer shows it can be dropped
    assert _drop(window, mime) is True

    qtbot.waitUntil(lambda: _open_count(window) == 1, timeout=20000)
    opened = window.mdiArea.subWindowList()[0].widget()
    assert len(opened.scene.nodes) == 2
    assert opened.filename.lower().endswith("flow.tds")


def test_several_dropped_workflows_all_open(window, tmp_path, qtbot):
    first = _workflow(tmp_path, "one.tds", nodes=1)
    second = _workflow(tmp_path, "two.tds", nodes=3)

    mime = _mime(first, second)

    assert _enter(window, mime) is True
    assert _drop(window, mime) is True

    qtbot.waitUntil(lambda: _open_count(window) == 2, timeout=30000)
    counts = sorted(len(w.widget().scene.nodes) for w in window.mdiArea.subWindowList())
    assert counts == [1, 3]


def test_dropping_a_file_that_is_already_open_shows_it_instead_of_opening_it_twice(
    window, tmp_path, qtbot
):
    flow = _workflow(tmp_path, "flow.tds")
    window.openFile(str(flow))
    assert _open_count(window) == 1

    _drop(window, _mime(flow))
    qtbot.wait(300)

    assert _open_count(window) == 1


def test_the_same_file_spelled_differently_is_still_the_same_document(
    window, tmp_path, qtbot, monkeypatch
):
    flow = _workflow(tmp_path, "Flow.tds")
    window.openFile(str(flow))
    monkeypatch.chdir(tmp_path)

    window.openFile("flow.tds")  # relative, different case: Windows paths do not care
    window.openFile(str(flow).upper())

    assert _open_count(window) == 1


def test_a_data_file_or_a_web_link_is_refused_and_nothing_opens(
    window, tmp_path, qtbot
):
    data = tmp_path / "data.csv"
    data.write_text("a\n1\n", encoding="utf-8")
    link = QMimeData()
    link.setUrls([QUrl("https://example.com/flow.tds")])

    assert _enter(window, _mime(data)) is False
    assert _enter(window, link) is False
    assert _drop(window, _mime(data)) is False
    qtbot.wait(300)

    assert _open_count(window) == 0


def test_a_workflow_dropped_on_the_canvas_opens_as_its_own_workflow(
    window, tmp_path, qtbot
):
    """The canvas takes node drags from the palette; a file is not a node."""
    current = _workflow(tmp_path, "current.tds", nodes=2)
    dropped = _workflow(tmp_path, "dropped.tds", nodes=3)
    window.openFile(str(current))
    canvas = window.mdiArea.subWindowList()[0].widget().view.viewport()
    mime = _mime(dropped)

    assert _enter(canvas, mime) is True
    assert _drop(canvas, mime) is True

    qtbot.waitUntil(lambda: _open_count(window) == 2, timeout=20000)
    by_name = {
        w.widget().filename.lower().rsplit("\\", 1)[-1]: w.widget()
        for w in window.mdiArea.subWindowList()
    }
    assert len(by_name["current.tds"].scene.nodes) == 2  # no node was added to it
    assert len(by_name["dropped.tds"].scene.nodes) == 3


def test_a_node_dragged_from_the_palette_is_still_accepted_by_the_canvas(
    window, tmp_path
):
    window.openFile(str(_workflow(tmp_path, "current.tds")))
    canvas = window.mdiArea.subWindowList()[0].widget().view.viewport()
    palette = QMimeData()
    palette.setData(LISTBOX_MIMETYPE, QByteArray())

    assert _enter(canvas, palette) is True


def test_the_canvas_still_refuses_what_it_cannot_use(window, tmp_path):
    window.openFile(str(_workflow(tmp_path, "current.tds")))
    canvas = window.mdiArea.subWindowList()[0].widget().view.viewport()
    other = QMimeData()
    other.setText("just text")

    assert _enter(canvas, other) is False


def test_help_menu_offers_to_register_tds_files(window):
    action = window.actAssociateFiles
    assert action.objectName() == "actionAssociateTdsFiles"
    assert "Open .tds files" in action.text()
    assert action in window.helpMenu.actions()
