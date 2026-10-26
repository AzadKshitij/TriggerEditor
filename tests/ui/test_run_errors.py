"""Run failures become plain-language errors, not raw executor text."""

from __future__ import annotations

import duckdb

from trigger_designer.core.ExecutionCheck.executor import ExecutionResult
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.main_window import TriggerWindow


def _parser_error() -> BaseException:
    try:
        duckdb.connect().execute('select 1 + AS "x"')
    except BaseException as exc:  # noqa: BLE001 - the engine exception is the fixture
        return exc
    raise AssertionError("parser error not reproduced")


def _result(exc: BaseException) -> ExecutionResult:
    return ExecutionResult(
        success=False,
        error=str(exc),
        exception=exc,
        traceback_text="Traceback ...",
    )


def test_run_parser_error_is_plain_language(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    window._start_error_enrichment = lambda *_args: None  # keep this synchronous

    window._on_node_finished(node, _result(_parser_error()))

    assert node.current_error is not None
    assert node.current_error.code == "TD-EXP-001"
    assert "ends too early" in node.current_error.detail
    assert "Parser Error" not in node.grNode.toolTip()
    assert node.isInvalid()


def test_run_error_reaches_the_problems_store(qtbot) -> None:
    main = TriggerWindow()
    qtbot.addWidget(main)
    main.show()
    main.onFileNew()
    window = main.mdiArea.subWindowList()[0].widget()
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    window._start_error_enrichment = lambda *_args: None

    window._on_node_finished(node, _result(_parser_error()))

    assert window.problems.count("error") == 1
    _source, error = window.problems.entries()[0]
    assert error.code == "TD-EXP-001"
