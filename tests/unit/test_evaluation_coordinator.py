"""Ordered passes, coalesced edge edits, and blocking of failed branches."""

import os
import sys
import weakref
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])


class CountingNode(TriggerNode):
    node_title = "Count"
    content_label = "evaluation_coordinator_count"

    def __init__(self, scene, *, inputs, outputs, key):
        self.computes = 0
        self.key = key
        self.fail = False
        super().__init__(scene, inputs=inputs, outputs=outputs)
        self.title = key

    def processInputs(self, input_values):
        self.computes += 1
        if self.fail:
            return None
        return input_values

    def get_code(self) -> str:
        return ""


def _edge(window, source_socket, target_socket):
    return window.scene.getEdgeClass()(window.scene, source_socket, target_socket)


def _reset(*nodes):
    for node in nodes:
        node.computes = 0


def test_coordinator_coalesces_multiple_origins() -> None:
    window = TriggerSubWindow()
    try:
        left = CountingNode(window.scene, inputs=[], outputs=[1], key="left")
        right = CountingNode(window.scene, inputs=[], outputs=[1], key="right")
        join = CountingNode(window.scene, inputs=[1, 1], outputs=[1], key="join")
        _edge(window, left.outputs[0], join.inputs[0])
        _edge(window, right.outputs[0], join.inputs[1])
        window.doEvalOutputs()
        _reset(left, right, join)

        window.scene.evaluator.request_evaluation(left, defer=True)
        window.scene.evaluator.request_evaluation(right, defer=True)
        window.scene.evaluator.flush_now()

        assert left.computes == 1
        assert right.computes == 1
        assert join.computes == 1
    finally:
        window.close()


def test_interactive_error_does_not_evaluate_downstream() -> None:
    window = TriggerSubWindow()
    try:
        source = CountingNode(window.scene, inputs=[], outputs=[1], key="source")
        sink = CountingNode(window.scene, inputs=[1], outputs=[], key="sink")
        _edge(window, source.outputs[0], sink.inputs[0])
        window.doEvalOutputs()
        _reset(source, sink)

        source.fail = True
        source.onInputChanged()

        assert source.isInvalid()
        assert sink.isDirty()
        assert sink.current_error is None
        assert source.computes == 1
        assert sink.computes == 0

        _reset(source, sink)
        source.fail = False
        source.onInputChanged()

        assert not source.isInvalid()
        assert source.computes == 1
        assert sink.computes == 1
        assert sink.current_error is None
    finally:
        window.close()


def test_load_error_still_evaluates_all() -> None:
    window = TriggerSubWindow()
    try:
        source = CountingNode(window.scene, inputs=[], outputs=[1], key="source")
        sink = CountingNode(window.scene, inputs=[1], outputs=[], key="sink")
        _edge(window, source.outputs[0], sink.inputs[0])

        source.fail = True
        window.doEvalOutputs()

        assert source.isInvalid()
        assert sink.isInvalid()
        assert sink.current_error is not None
        assert sink.current_error.code == "TD-RUN-003"
    finally:
        window.close()


def test_bulk_load_does_not_flush() -> None:
    window = TriggerSubWindow()
    try:
        window.scene.beginBulkLoad()
        try:
            node = CountingNode(window.scene, inputs=[], outputs=[1], key="bulk")
            node.onInputChanged()
            assert node.computes == 0
        finally:
            window.scene.endBulkLoad()

        window.scene.evaluator.flush_now()
        assert node.computes == 0
    finally:
        window.close()


def test_bulk_load_discards_pending() -> None:
    window = TriggerSubWindow()
    try:
        node = CountingNode(window.scene, inputs=[], outputs=[1], key="bulk")
        window.scene.beginBulkLoad()
        window.scene.evaluator.request_evaluation(node, defer=True)
        assert node in window.scene.evaluator.pending
        window.scene.endBulkLoad()

        assert window.scene.evaluator.pending == set()
        window.scene.evaluator.flush_now()
        assert node.computes == 0
    finally:
        window.close()


def test_suspend_queues_live_evaluation_until_resume() -> None:
    window = TriggerSubWindow()
    try:
        node = CountingNode(window.scene, inputs=[], outputs=[1], key="deferred")
        window.doEvalOutputs()
        _reset(node)
        coordinator = window.scene.evaluator

        coordinator.suspend()
        node.onInputChanged()
        assert node.computes == 0
        assert node in coordinator.pending

        coordinator.resume()
        assert node.computes == 1
        assert coordinator.pending == set()
    finally:
        window.close()


def test_suspend_queues_evaluate_all_until_resume() -> None:
    window = TriggerSubWindow()
    try:
        node = CountingNode(window.scene, inputs=[], outputs=[1], key="deferred-all")
        window.doEvalOutputs()
        _reset(node)
        coordinator = window.scene.evaluator

        coordinator.suspend()
        window.doEvalOutputs()
        assert node.computes == 0
        assert node in coordinator.pending

        coordinator.resume()
        assert node.computes == 1
    finally:
        window.close()


def test_undo_restore_resets_pending() -> None:
    window = TriggerSubWindow()
    try:
        node = CountingNode(window.scene, inputs=[], outputs=[1], key="restore")
        window.scene.evaluator.request_evaluation(node, defer=True)
        assert node in window.scene.evaluator.pending
        reference = weakref.ref(node)

        window.onHistoryRestored()

        assert window.scene.evaluator.pending == set()
        assert reference() is node
    finally:
        window.close()


def test_progress_and_notify_counts() -> None:
    window = TriggerSubWindow()
    try:
        source = CountingNode(window.scene, inputs=[], outputs=[1], key="source")
        sink = CountingNode(window.scene, inputs=[1], outputs=[], key="sink")
        _edge(window, source.outputs[0], sink.inputs[0])
        window.doEvalOutputs()
        _reset(source, sink)

        progress = []
        notified = []
        window.scene._eval_progress_cb = lambda node, finished: progress.append(
            (node, finished)
        )
        window.scene.addNodeEvaluatedListener(notified.append)

        source.onInputChanged()

        assert source.computes == 1
        assert sink.computes == 1
        assert len(progress) == 4
        assert notified == [source, sink]

        progress.clear()
        notified.clear()
        assert sink.eval() is not None
        assert progress == []
        assert notified == []
    finally:
        window.scene._eval_progress_cb = None
        window.close()


def test_cycle_fallback_in_edit_reports_once() -> None:
    window = TriggerSubWindow()
    messages = []
    window.logWarning = messages.append
    try:
        first = CountingNode(window.scene, inputs=[1], outputs=[1], key="first")
        second = CountingNode(window.scene, inputs=[1], outputs=[1], key="second")
        _edge(window, first.outputs[0], second.inputs[0])
        _edge(window, second.outputs[0], first.inputs[0])

        first.onInputChanged()
        first.onInputChanged()

        cycle_messages = [m for m in messages if "cycle" in m.lower()]
        assert len(cycle_messages) == 1
    finally:
        window.close()


def test_deferred_edge_change_coalesces() -> None:
    window = TriggerSubWindow()
    try:
        first = CountingNode(window.scene, inputs=[], outputs=[1], key="first")
        second = CountingNode(window.scene, inputs=[], outputs=[1], key="second")
        join = CountingNode(window.scene, inputs=[1, 1], outputs=[1], key="join")
        _edge(window, first.outputs[0], join.inputs[0])
        window.doEvalOutputs()
        _reset(first, second, join)

        new_edge = _edge(window, second.outputs[0], join.inputs[1])
        for socket in (second.outputs[0], join.inputs[1]):
            socket.node.onEdgeConnectionChanged(new_edge)
            if socket.is_input:
                socket.node.onInputChanged(socket)
        assert join.computes == 0  # still deferred
        window.scene.evaluator.flush_now()

        assert first.computes == 0
        assert second.computes == 0
        assert join.computes == 1
    finally:
        window.close()


def test_split_notifications_coalesce() -> None:
    window = TriggerSubWindow()
    try:
        source = CountingNode(window.scene, inputs=[], outputs=[1], key="source")
        target = CountingNode(window.scene, inputs=[1], outputs=[], key="target")
        inserted = CountingNode(window.scene, inputs=[1], outputs=[1], key="inserted")
        original = _edge(window, source.outputs[0], target.inputs[0])
        window.doEvalOutputs()
        _reset(source, target, inserted)

        original.remove(silent=True)
        first_edge = _edge(window, source.outputs[0], inserted.inputs[0])
        second_edge = _edge(window, inserted.outputs[0], target.inputs[0])
        for socket, edge in (
            (inserted.inputs[0], first_edge),
            (inserted.outputs[0], second_edge),
            (target.inputs[0], second_edge),
        ):
            socket.node.onEdgeConnectionChanged(edge)
            if socket.is_input:
                socket.node.onInputChanged(socket)
        window.scene.evaluator.flush_now()

        assert source.computes == 0
        assert inserted.computes == 1
        assert target.computes == 1
    finally:
        window.close()


def test_content_edit_is_immediate() -> None:
    window = TriggerSubWindow()
    try:
        node = CountingNode(window.scene, inputs=[], outputs=[1], key="content")
        window.doEvalOutputs()
        node.computes = 0

        node.onInputChanged()

        assert node.computes == 1
    finally:
        window.close()


def test_eval_flushes_pending() -> None:
    window = TriggerSubWindow()
    try:
        node = CountingNode(window.scene, inputs=[], outputs=[1], key="pending")
        window.doEvalOutputs()
        node.computes = 0
        node.value = ["stale"]

        window.scene.evaluator.request_evaluation(node, defer=True)
        assert node.computes == 0
        value = node.eval()

        assert node.computes == 1
        assert value != ["stale"]
    finally:
        window.close()


def test_timer_after_reset_is_noop() -> None:
    window = TriggerSubWindow()
    try:
        node = CountingNode(window.scene, inputs=[], outputs=[1], key="timer")
        window.doEvalOutputs()
        node.computes = 0

        window.scene.evaluator.request_evaluation(node, defer=True)
        window.scene.evaluator.reset_pending()
        QApplication.processEvents()

        assert node.computes == 0
        assert window.scene.evaluator.pending == set()
    finally:
        window.close()
