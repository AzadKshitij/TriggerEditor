"""Copy/paste of a configured File Input node (issue #44)."""

from __future__ import annotations

import orjson
from qtpy.QtWidgets import QApplication

from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.main_window import TriggerWindow


def _source_file(tmp_path) -> str:
    source = tmp_path / "in.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    return str(source)


def test_constructor_eval_is_deferred_during_bulk_load(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    cls = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)

    window.scene.beginBulkLoad()
    try:
        node = cls(window.scene)
    finally:
        window.scene.endBulkLoad()

    assert node.current_error is None
    assert node._node_tooltip() == ""


def test_paste_restores_file_and_clears_error(qtbot, tmp_path) -> None:
    main = TriggerWindow()
    qtbot.addWidget(main)
    main.show()
    main.onFileNew()
    QApplication.processEvents()
    window = main.mdiArea.subWindowList()[0].widget()
    cls = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)
    source = _source_file(tmp_path)
    node = cls(window.scene)
    node.content.filePath = source
    node.content.file_type = "csv"
    node.eval()
    assert node.current_error is None

    node.grNode.setSelected(True)
    main.onEditCopy()
    payload = orjson.loads(QApplication.clipboard().text())
    assert len(payload["nodes"]) == 1

    main.onEditPaste()
    pasted = [item for item in window.scene.nodes if item is not node]
    assert len(pasted) == 1
    result = pasted[0]
    assert result.content.filePath == source
    assert result.current_error is None
    assert result._node_tooltip() == ""
    assert result.value is not None

    # Keep the test window's teardown from opening a modal "save changes?" box.
    window.scene.has_been_modified = False
