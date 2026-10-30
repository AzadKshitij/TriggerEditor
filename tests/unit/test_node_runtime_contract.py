"""Characterization of the node evaluation, error and content contracts.

These pin behaviour of ``TriggerNode`` and the content bases that the
node-base simplification (docs/plan/08) must keep identical: the failure
transitions of ``evalImplementation``, ``eval`` exception handling, error
knock-on clearing, invalidation on input changes and the content MRO.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from qtpy.QtWidgets import QApplication

from trigger_designer.core.errors import make_error
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers.content_undo_mixin import TriggerContentUndoMixin
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerContent,
    TriggerNode,
)

APP = QApplication.instance() or QApplication([])


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, value=1):
        self._seed = value
        super().__init__(scene, inputs=[], outputs=[1])

    def processInputs(self, input_values):
        return self._seed

    def get_code(self) -> str:
        return ""


class Consumer(TriggerNode):
    node_title = "Consumer"
    result = "ok"
    raises: Exception | None = None
    specific_error = False

    def __init__(self, scene, inputs=(1,), optional=()):
        self.optional_inputs = frozenset(optional)
        super().__init__(scene, inputs=list(inputs), outputs=[1])

    def processInputs(self, input_values):
        if self.raises is not None:
            raise self.raises
        if self.specific_error:
            self.set_error(make_error("TD-SYS-001", None, message="specific"), "live")
            return None
        return self.result

    def get_code(self) -> str:
        return ""


def _edge(scene, source, target):
    return scene.getEdgeClass()(scene, source, target)


def _window():
    return TriggerSubWindow()


def test_missing_required_input_sets_run_005_and_dirties_descendants() -> None:
    window = _window()
    try:
        scene = window.scene
        node = Consumer(scene)
        child = Consumer(scene)
        _edge(scene, node.outputs[0], child.inputs[0])
        child.markDirty(False)

        assert node.eval() is None

        assert node.isInvalid()
        assert child.isDirty()
        assert node.current_error.code == "TD-RUN-005"
        assert node.current_error.params["input_number"] == "1"
    finally:
        window.close()


def test_optional_input_receives_none_and_computes() -> None:
    window = _window()
    try:
        node = Consumer(window.scene, optional=(0,))
        assert node.eval() == "ok"
        assert not node.isInvalid()
        assert node.current_error is None
    finally:
        window.close()


def test_failed_upstream_sets_run_003_naming_the_culprit() -> None:
    window = _window()
    try:
        scene = window.scene
        upstream = Consumer(scene)  # no input -> evaluates to None
        downstream = Consumer(scene)
        _edge(scene, upstream.outputs[0], downstream.inputs[0])

        assert downstream.eval() is None

        assert downstream.isInvalid()
        error = downstream.current_error
        assert error.code == "TD-RUN-003"
        assert error.culprit_node_id == upstream.id
    finally:
        window.close()


def test_none_result_without_error_gets_fallback_sys_001() -> None:
    window = _window()
    try:
        scene = window.scene
        source = Source(scene)
        node = Consumer(scene)
        node.result = None
        _edge(scene, source.outputs[0], node.inputs[0])

        assert node.eval() is None

        assert node.isInvalid()
        assert node.current_error.code == "TD-SYS-001"
        assert node.current_error.params["message"] == "Invalid operation"
    finally:
        window.close()


def test_none_result_keeps_the_error_processinputs_already_set() -> None:
    window = _window()
    try:
        scene = window.scene
        source = Source(scene)
        node = Consumer(scene)
        node.specific_error = True
        _edge(scene, source.outputs[0], node.inputs[0])

        assert node.eval() is None

        assert node.isInvalid()
        assert node.current_error.params["message"] == "specific"
    finally:
        window.close()


def test_success_commits_value_and_clears_live_error() -> None:
    window = _window()
    try:
        scene = window.scene
        source = Source(scene, 7)
        node = Consumer(scene)
        _edge(scene, source.outputs[0], node.inputs[0])
        node.set_error(make_error("TD-SYS-001", None, message="old"), "live")

        assert node.eval() == "ok"

        assert node.value == "ok"
        assert not node.isDirty()
        assert not node.isInvalid()
        assert node.current_error is None
    finally:
        window.close()


def test_value_error_and_exception_invalidate_and_record_error(monkeypatch) -> None:
    from trigger_designer.qt import node_runtime

    monkeypatch.setattr(node_runtime, "dumpException", lambda exc: None)
    window = _window()
    try:
        scene = window.scene
        source = Source(scene)
        for exc in (ValueError("bad value"), RuntimeError("boom")):
            node = Consumer(scene)
            node.raises = exc
            child = Consumer(scene)
            _edge(scene, source.outputs[0], node.inputs[0])
            _edge(scene, node.outputs[0], child.inputs[0])
            child.markDirty(False)

            assert node.eval() is None

            assert node.isInvalid()
            assert node.current_error is not None
            assert node._evaluating is False
            # Only the ValueError path dirties the descendants.
            assert child.isDirty() is isinstance(exc, ValueError)
    finally:
        window.close()


def test_clear_run_error_clears_knock_on_children_recursively() -> None:
    window = _window()
    try:
        scene = window.scene
        a, b, c, d = (Consumer(scene) for _ in range(4))
        _edge(scene, a.outputs[0], b.inputs[0])
        _edge(scene, b.outputs[0], c.inputs[0])
        _edge(scene, a.outputs[0], d.inputs[0])
        a.set_error(make_error("TD-SYS-001", None, message="root"), "run")
        for node in (b, c):
            node.set_error(make_error("TD-RUN-008", None, culprit_label="a"), "run")
        d.set_error(make_error("TD-SYS-001", None, message="own"), "run")

        a.clear_error("run")

        assert a.current_error is None
        assert b.current_error is None
        assert c.current_error is None
        # A child with its own (non knock-on) run error is left alone.
        assert d.current_error is not None
    finally:
        window.close()


def test_clear_live_error_does_not_cascade_and_survives_cycles() -> None:
    window = _window()
    try:
        scene = window.scene
        a, b = Consumer(scene), Consumer(scene)
        _edge(scene, a.outputs[0], b.inputs[0])
        b.set_error(make_error("TD-RUN-008", None, culprit_label="a"), "run")
        a.set_error(make_error("TD-SYS-001", None, message="x"), "live")

        a.clear_error("live")

        assert a.current_error is None
        assert b.current_error is not None

        seen: set[int] = set()
        a.clear_error(None, _seen=seen)
        a.clear_error(None, _seen=seen)  # already seen: a no-op, not a loop
    finally:
        window.close()


def test_run_error_outranks_live_error() -> None:
    window = _window()
    try:
        node = Consumer(window.scene)
        live = make_error("TD-SYS-001", None, message="live")
        run = make_error("TD-SYS-001", None, message="run")
        node.set_error(live, "live")
        node.set_error(run, "run")
        assert node.current_error is run
        node.clear_error("run")
        assert node.current_error is live
    finally:
        window.close()


def test_input_change_marks_dirty_and_recomputes() -> None:
    window = _window()
    try:
        scene = window.scene
        source = Source(scene)
        node = Consumer(scene)
        child = Consumer(scene)
        _edge(scene, source.outputs[0], node.inputs[0])
        _edge(scene, node.outputs[0], child.inputs[0])
        node.eval()
        assert not node.isDirty()

        node.set_error(make_error("TD-RUN-008", None, culprit_label="a"), "run")
        node.onInputChanged()

        assert node.current_error is None
        assert not node.isDirty()
        assert node.value == "ok"
    finally:
        window.close()


def test_suspended_content_skips_input_change() -> None:
    window = _window()
    try:
        scene = window.scene
        node = Consumer(scene, inputs=())
        node.eval()
        node.content._suspend_node_evaluation = True
        node.set_error(make_error("TD-SYS-001", None, message="keep"), "run")

        node.onInputChanged()

        assert node.current_error is not None
    finally:
        window.close()


def test_edge_change_on_the_producer_only_clears_run_error() -> None:
    window = _window()
    try:
        scene = window.scene
        source = Source(scene)
        node = Consumer(scene)
        edge = _edge(scene, source.outputs[0], node.inputs[0])
        source.eval()
        node.eval()
        source.set_error(make_error("TD-SYS-001", None, message="x"), "run")

        source.onEdgeConnectionChanged(edge)

        assert source.current_error is None
        assert not source.isDirty()  # the producer is not the edge's end node

        node.onEdgeConnectionChanged(edge)
        assert node.isDirty()
    finally:
        window.close()


def test_content_history_stamp_resolves_to_the_undo_mixin() -> None:
    assert (
        TriggerContent.history_stamp_callback
        is TriggerContentUndoMixin.history_stamp_callback
    )
    assert issubclass(TriggerContent, QDMNodeIconContentWidget)
    assert issubclass(TriggerChangeHandler, TriggerContentUndoMixin)


def test_config_content_is_a_change_handler_and_icon_content() -> None:
    from trigger_designer.qt.node_content import ConfigContent

    assert issubclass(ConfigContent, QDMNodeIconContentWidget)
    assert issubclass(ConfigContent, TriggerChangeHandler)
    assert "evaluate" in ConfigContent.__dict__


def test_handler_without_init_still_has_input_widget_store() -> None:
    class Legacy(QDMNodeIconContentWidget, TriggerChangeHandler):
        def __init__(self):  # deliberately does not chain
            pass

    handler = Legacy.__new__(Legacy)
    assert handler._input_widgets == []
    assert handler._input_widgets is handler._input_widgets


def test_trigger_content_is_a_config_content_adapter() -> None:
    from trigger_designer.qt.helpers.config_content import (
        ConfigContent as LegacyConfigContent,
    )
    from trigger_designer.qt.node_content import ConfigContent

    assert LegacyConfigContent is ConfigContent
    assert issubclass(TriggerContent, ConfigContent)
