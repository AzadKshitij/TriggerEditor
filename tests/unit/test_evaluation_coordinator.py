"""Ordered passes, coalesced edge edits, and blocking of failed branches."""

import weakref

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


# --- incremental full pass (a deferred open evaluates in slices) --------------


def _pump(predicate, timeout: float = 5.0) -> None:
    """Run the Qt event loop until ``predicate()`` holds."""
    import time

    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "timed out waiting for the event loop"
        APP.processEvents()
        time.sleep(0.005)


def _chain(window):
    a = CountingNode(window.scene, inputs=[], outputs=[1], key="a")
    b = CountingNode(window.scene, inputs=[1], outputs=[1], key="b")
    c = CountingNode(window.scene, inputs=[1], outputs=[], key="c")
    _edge(window, a.outputs[0], b.inputs[0])
    _edge(window, b.outputs[0], c.inputs[0])
    return a, b, c


def test_incremental_pass_evaluates_every_node_in_order_and_reports_progress() -> None:
    window = TriggerSubWindow()
    try:
        a, b, c = _chain(window)
        order: list[str] = []
        for node in (a, b, c):
            original = node.processInputs

            def traced(values, original=original, key=node.key):
                order.append(key)
                return original(values)

            node.processInputs = traced
        _reset(a, b, c)
        progress: list[tuple[int, int]] = []
        done: list[bool] = []

        window.scene.evaluator.evaluate_all_incrementally(
            budget_ms=0.0,  # one node per slice: the worst case for the loop
            on_progress=lambda finished, total: progress.append((finished, total)),
            on_done=lambda: done.append(True),
        )
        assert (a.computes, b.computes, c.computes) == (0, 0, 0)  # nothing yet

        _pump(lambda: done)
        assert order == ["a", "b", "c"]
        assert progress == [(1, 3), (2, 3), (3, 3)]
        assert done == [True]
    finally:
        window.close()


def test_a_full_pass_supersedes_an_unfinished_incremental_one() -> None:
    window = TriggerSubWindow()
    try:
        a, b, c = _chain(window)
        _reset(a, b, c)
        progress: list[tuple[int, int]] = []
        done: list[bool] = []

        window.scene.evaluator.evaluate_all_incrementally(
            budget_ms=0.0,
            on_progress=lambda finished, total: progress.append((finished, total)),
            on_done=lambda: done.append(True),
        )
        _pump(lambda: progress)  # the first slice ran
        window.doEvalOutputs()  # a Run or an undo restore: its own full pass
        for _ in range(20):
            APP.processEvents()

        assert done == []  # the superseded pass never finishes
        assert len(progress) == 1
        # the superseding full pass evaluated every node itself
        assert all(node.computes >= 1 for node in (a, b, c))
    finally:
        window.close()


def test_incremental_pass_waits_while_the_evaluator_is_suspended() -> None:
    window = TriggerSubWindow()
    try:
        a, b, c = _chain(window)
        _reset(a, b, c)
        progress: list[tuple[int, int]] = []
        done: list[bool] = []
        evaluator = window.scene.evaluator

        evaluator.suspend()  # a workflow run owns Polars/DuckDB
        evaluator.evaluate_all_incrementally(
            budget_ms=0.0,
            on_progress=lambda finished, total: progress.append((finished, total)),
            on_done=lambda: done.append(True),
        )
        import time

        end = time.monotonic() + 0.2
        while time.monotonic() < end:
            APP.processEvents()
            time.sleep(0.005)
        assert progress == []  # held back while suspended

        evaluator.resume()
        _pump(lambda: done)
        assert progress[-1] == (3, 3)
    finally:
        window.close()
