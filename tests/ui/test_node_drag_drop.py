"""The palette drag payload and the drop that turns it into a node.

Issue #3: ``QDataStream.writeInt`` no longer exists on PySide6 (Qt 6 renamed
it to ``writeInt32``), so ``startDrag`` raised before a drag ever began. These
tests drive the real palette serialization and the real drop handler.
"""

from __future__ import annotations

from qtpy.QtCore import QDataStream, QIODevice, QMimeData, QPointF, Qt
from qtpy.QtGui import QDropEvent, QPixmap
from qtpy.QtWidgets import QApplication

from trigger_designer.core.node_configuration import (
    LISTBOX_MIMETYPE,
    NodeTypes,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets import node_drag_listbox


class _FakeDrag:
    """Stand-in for ``QDrag``: ``exec_`` would block on a real drag loop."""

    last: _FakeDrag | None = None

    def __init__(self, source) -> None:
        self.source = source
        self.mime: QMimeData | None = None

    def setMimeData(self, data: QMimeData) -> None:
        self.mime = data

    def setHotSpot(self, *_args) -> None:
        pass

    def setPixmap(self, *_args) -> None:
        pass

    def exec_(self, *_args) -> Qt.DropAction:
        type(self).last = self
        return Qt.DropAction.IgnoreAction


def _palette_drag(qtbot, monkeypatch) -> tuple[QMimeData, int]:
    palette = node_drag_listbox.QTRDragListbox(node_type=NodeTypes.IO)
    qtbot.addWidget(palette)
    palette.setCurrentRow(0)
    expected_code = palette.currentItem().data(Qt.ItemDataRole.UserRole + 1)

    monkeypatch.setattr(node_drag_listbox, "QDrag", _FakeDrag)
    _FakeDrag.last = None
    palette.startDrag()

    drag = _FakeDrag.last
    assert drag is not None, "startDrag produced no drag"
    assert drag.mime is not None, "startDrag produced no mime data"
    return drag.mime, expected_code


def test_the_palette_writes_a_readable_drag_payload(qtbot, monkeypatch) -> None:
    mime, expected_code = _palette_drag(qtbot, monkeypatch)
    assert mime.hasFormat(LISTBOX_MIMETYPE)

    payload = mime.data(LISTBOX_MIMETYPE)
    stream = QDataStream(payload, QIODevice.OpenModeFlag.ReadOnly)
    pixmap = QPixmap()
    stream >> pixmap
    node_code = stream.readInt32()
    node_type = stream.readQString()

    assert node_code == expected_code
    assert node_type == str(NodeTypes.IO)
    assert stream.status() == QDataStream.Status.Ok


def test_dropping_the_payload_adds_the_node(qtbot, monkeypatch) -> None:
    mime, expected_code = _palette_drag(qtbot, monkeypatch)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    QApplication.processEvents()

    before = len(window.scene.nodes)
    event = QDropEvent(
        QPointF(160.0, 120.0),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.onDrop(event)

    assert event.isAccepted()
    assert len(window.scene.nodes) == before + 1
    node = window.scene.nodes[-1]
    assert node.node_code == expected_code
    assert node.node_type == str(NodeTypes.IO)
