#!/usr/bin/env python3

from types import SimpleNamespace

import pytest
from nodeeditor.node_node import Node
from qtpy.QtCore import QEvent
from qtpy.QtWidgets import QApplication, QFrame

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode

APP = QApplication.instance() or QApplication([])


def test_clear_input_widgets_ignores_deleted_qt_wrappers() -> None:
    handler = TriggerChangeHandler(
        scene=SimpleNamespace(
            history=SimpleNamespace(storeHistory=lambda *args, **kwargs: None)
        ),
        node=SimpleNamespace(),
    )

    widget = QFrame()
    handler._input_widgets.append(widget)

    widget.deleteLater()
    APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    APP.processEvents()

    handler.clearInputWidgets()

    assert handler._input_widgets == []


def test_plain_node_keeps_the_default_socket_layout() -> None:
    window = TriggerSubWindow()
    node = TriggerNode(window.scene)
    assert [socket.socket_type for socket in node.inputs] == [2, 2]
    assert [socket.socket_type for socket in node.outputs] == [1]


def test_deserialize_without_hashmap_starts_from_an_empty_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = TriggerSubWindow()
    first_data = TriggerNode(window.scene).serialize()
    second_data = TriggerNode(window.scene).serialize()
    base_deserialize = Node.deserialize
    seen: list[tuple[dict, dict]] = []

    def record(self, data, hashmap, restore_id=True, *args, **kwargs):
        seen.append((hashmap, dict(hashmap)))
        return base_deserialize(self, data, hashmap, restore_id, *args, **kwargs)

    monkeypatch.setattr(Node, "deserialize", record)
    TriggerNode(window.scene).deserialize(first_data)
    TriggerNode(window.scene).deserialize(second_data)

    (first_map, _), (second_map, second_seen) = seen
    assert first_map is not second_map
    assert second_seen == {}


def test_nodes_built_without_socket_arguments_do_not_share_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_init_sockets = Node.initSockets
    received: list[tuple[list, list, list]] = []

    def record(self, inputs, outputs, input_text, output_text, reset=True):
        received.append((inputs, outputs, input_text))
        return base_init_sockets(self, inputs, outputs, input_text, output_text, reset)

    monkeypatch.setattr(Node, "initSockets", record)
    window = TriggerSubWindow()
    TriggerNode(window.scene)
    TriggerNode(window.scene)

    (first_in, first_out, first_text), (second_in, second_out, second_text) = received
    assert first_in is not second_in
    assert first_out is not second_out
    assert first_text is not second_text


def main() -> None:
    test_clear_input_widgets_ignores_deleted_qt_wrappers()
    print("ok")


if __name__ == "__main__":
    main()
