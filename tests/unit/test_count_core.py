"""Count core: total rows, dtype, empty input and Qt-free execution."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import polars as pl
from nodeeditor.node_edge import Edge
from polars.testing import assert_frame_equal

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping import count as core
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame) -> None:
        self._frame = frame
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def test_count_counts_every_row() -> None:
    frame = pl.DataFrame({"a": [1, 2, 3]})
    out = core.run_node([frame], {}).pop().collect()
    assert out.columns == ["Count"]
    assert out.rows() == [(3,)]
    assert out.schema["Count"] == pl.Int64


def test_count_includes_null_rows_and_accepts_lazy_input() -> None:
    frame = pl.DataFrame({"a": [1, None, None]}).lazy()
    out = core.run_node([frame], {}).pop().collect()
    assert out["Count"].to_list() == [3]


def test_count_empty_frame_is_zero() -> None:
    frame = pl.DataFrame(schema={"a": pl.String})
    out = core.run_node([frame], {}).pop().collect()
    assert out.rows() == [(0,)]
    assert out.schema["Count"] == pl.Int64


def test_count_returns_one_lazy_frame_and_imports_no_qt() -> None:
    outs = core.run_node([pl.DataFrame({"a": [1]})], {})
    assert len(outs) == 1
    assert isinstance(outs[0], pl.LazyFrame)

    root = Path(__file__).resolve().parents[2]
    code = (
        "import sys;"
        f"sys.path.insert(0, {str(root / 'src')!r});"
        "import trigger_designer.core.shaping.count;"
        "print(any(m.startswith(('qtpy', 'PyQt6')) for m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"


def test_count_live_and_generated_code_match() -> None:
    window = TriggerSubWindow()
    frame = pl.DataFrame({"a": [1, 2], "b": [None, 5]}).lazy()
    source = Source(window.scene, frame)
    cls = get_class_from_opcode(TransformNodes.COUNT_RECORDS, NodeTypes.TRANSFORM)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    live = node.eval()
    assert live is not None and not node.isInvalid()

    content = node.content
    namespace = {"var_src": frame}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert_frame_equal(generated, live[0]["data"].collect())
