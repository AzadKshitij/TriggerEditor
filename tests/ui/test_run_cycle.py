"""A cyclic graph refuses to run and leaves Run usable (BUG-012)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nodeeditor.node_graph import GraphCycleError

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers import workflow_execution_mixin as mixin_module


def test_cycle_keeps_run_button_enabled(qtbot, monkeypatch) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.show()
    logged: list[str] = []
    monkeypatch.setattr(window, "logInfo", logged.append)

    def refuse(_scene):
        raise GraphCycleError("Graph has at least one cycle")

    monkeypatch.setattr(mixin_module, "topological_order", refuse)
    monkeypatch.setattr(mixin_module, "select_cycle_edges", lambda *_a: None)

    window.run_workflow()  # must not raise

    assert window.run_button.isEnabled() and window.run_button.isVisible()
    assert window.cancel_button.isHidden()
    assert window._workflow_worker is None
    assert any("cycle" in line.lower() or "loop" in line.lower() for line in logged)
