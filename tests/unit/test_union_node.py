#!/usr/bin/env python3
"""Union node tests: 3-mode stacking on one multi-edge input socket."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtWidgets import QApplication, QVBoxLayout

APP = QApplication.instance() or QApplication([])


def _make_content(**kwargs):
    """Logic-only content (no scene): execute_union/get_code are pure."""
    from trigger_designer.qt.widgets.nodes.Join.union import UnionContent

    content = UnionContent.__new__(UnionContent)
    content.mode = kwargs.get("mode", "by_name")
    content.column_map = kwargs.get("column_map", [])
    content.input_frames = kwargs.get("input_frames", [])
    content.input_variables = kwargs.get("input_variables", [])
    content.variable_name = "var_union_test"
    content.coercion_warnings = []
    content.id = 999
    return content


def test_by_name_unions_columns_with_null_fill() -> None:
    content = _make_content(
        input_frames=[
            pl.DataFrame({"id": [1, 2], "name": ["x", "y"]}),
            pl.DataFrame({"name": ["z"], "extra": [9.5]}),
            pl.DataFrame({"ID": [7], "name": ["w"]}),
        ],
        input_variables=["in0", "in1", "in2"],
    )
    out = content.execute_union().collect()
    assert out.shape == (4, 4)
    assert out["id"].to_list() == [1, 2, None, None]
    assert out["extra"].to_list() == [None, None, 9.5, None]
    # Case-sensitive: 'id' and 'ID' stay separate columns.
    assert "ID" in out.columns and "id" in out.columns
    assert content.coercion_warnings == []


def test_by_position_ignores_names_pads_short_rows() -> None:
    content = _make_content(
        mode="by_position",
        input_frames=[
            pl.DataFrame({"a": [1], "b": [2]}),
            pl.DataFrame({"x": [3], "y": [4], "z": [5]}),
        ],
        input_variables=["in0", "in1"],
    )
    out = content.execute_union().collect()
    assert out.columns == ["a", "b", "Extra_3"]
    assert out.row(0) == (1, 2, None)
    assert out.row(1) == (3, 4, 5)


def test_manual_aligns_renamed_columns_and_nulls_unmapped() -> None:
    content = _make_content(
        mode="manual",
        input_frames=[
            pl.DataFrame({"ID": [1], "keep": ["k"]}),
            pl.DataFrame({"Customer_ID": [2]}),
        ],
        input_variables=["in0", "in1"],
        column_map=[
            {"output": "Customer_ID", "sources": ["ID", "Customer_ID"]},
            {"output": "keep", "sources": ["keep", None]},
        ],
    )
    out = content.execute_union().collect()
    assert out.columns == ["Customer_ID", "keep"]
    assert out["Customer_ID"].to_list() == [1, 2]
    assert out["keep"].to_list() == ["k", None]


def test_dtype_conflict_coerces_to_string_with_warning() -> None:
    content = _make_content(
        input_frames=[
            pl.DataFrame({"id": [1, 2]}),
            pl.DataFrame({"id": ["p"]}),
        ],
        input_variables=["in0", "in1"],
    )
    out = content.execute_union().collect()
    assert out["id"].dtype == pl.String
    assert out["id"].to_list() == ["1", "2", "p"]
    assert len(content.coercion_warnings) == 1
    assert "id" in content.coercion_warnings[0]


def test_empty_inputs_return_none() -> None:
    content = _make_content(input_frames=[])
    assert content.execute_union() is None


def _stub_node(scene, df, var):
    from trigger_designer.qt.node_base import TriggerNode

    class _Src(TriggerNode):
        def evalImplementation(self):
            return [{"data": self._df, "variable_name": self._var}]

    node = _Src(scene, inputs=[], outputs=[3])
    node._df, node._var = df, var
    node.markDirty(True)
    return node


def _wire_union(df_vars):
    """Union node with one edge per df, in list order. Returns (union, edges)."""
    from nodeeditor.node_edge import Edge

    from trigger_designer.qt.performance_scene import TriggerScene
    from trigger_designer.qt.widgets.nodes.Join.union import TriggerNode_Union

    scene = TriggerScene()
    union = TriggerNode_Union(scene)
    edges = []
    for df, var in df_vars:
        src = _stub_node(scene, df, var)
        edge = Edge(scene, src.outputs[0], union.inputs[0])
        union.onEdgeConnectionChanged(edge)
        edges.append(edge)
    return union, edges


def test_scene_eval_reads_edges_in_order() -> None:
    union, _ = _wire_union(
        [
            (pl.DataFrame({"v": [1], "src": ["A"]}), "in_a"),
            (pl.DataFrame({"v": [2], "src": ["B"]}), "in_b"),
        ]
    )
    param = union.eval()
    out = param[0]["data"].collect()
    assert out["src"].to_list() == ["A", "B"]
    assert union.content.input_variables == ["in_a", "in_b"]


def test_scene_reorder_changes_row_order() -> None:
    union, edges = _wire_union(
        [
            (pl.DataFrame({"v": [1], "src": ["A"]}), "in_a"),
            (pl.DataFrame({"v": [2], "src": ["B"]}), "in_b"),
        ]
    )
    union.eval()
    assert union.moveEdgeTo(edges[1], 0) is True
    out = union.eval()[0]["data"].collect()
    assert out["src"].to_list() == ["B", "A"]
    labels = sorted(e.getLabel() for e in union.getOrderedEdges())
    assert labels == ["#1", "#2"]


def test_scene_no_edges_is_invalid() -> None:
    from trigger_designer.qt.performance_scene import TriggerScene
    from trigger_designer.qt.widgets.nodes.Join.union import TriggerNode_Union

    union = TriggerNode_Union(TriggerScene())
    assert union.eval() is None
    assert union.isInvalid()


def test_serialize_round_trip() -> None:
    from trigger_designer.qt.performance_scene import TriggerScene
    from trigger_designer.qt.widgets.nodes.Join.union import TriggerNode_Union

    node = TriggerNode_Union(TriggerScene())
    node.content.mode = "manual"
    node.content.column_map = [{"output": "Customer_ID", "sources": ["ID", None]}]
    payload = node.content.serialize()

    node2 = TriggerNode_Union(TriggerScene())
    assert node2.content.deserialize(payload, hashmap={}) is not False
    assert node2.content.mode == "manual"
    assert node2.content.column_map == [
        {"output": "Customer_ID", "sources": ["ID", None]}
    ]


def test_get_code_executes() -> None:
    content = _make_content(
        input_frames=[
            pl.DataFrame({"id": [1], "name": ["x"]}),
            pl.DataFrame({"name": ["y"], "extra": [1.5]}),
        ],
        input_variables=["in0", "in1"],
    )
    code = content.get_code()
    assert "pl.concat" in code and "diagonal_relaxed" in code
    ns = {
        "in0": pl.DataFrame({"id": [1], "name": ["x"]}),
        "in1": pl.DataFrame({"name": ["y"], "extra": [1.5]}),
    }
    exec(code, ns)  # noqa: S102 - executing our own generated snippet
    out = ns["var_union_test"]
    assert out.collect().shape == (2, 3)


def test_create_layout_empty_state_and_mode() -> None:
    from trigger_designer.qt.performance_scene import TriggerScene
    from trigger_designer.qt.widgets.nodes.Join.union import TriggerNode_Union

    node = TriggerNode_Union(TriggerScene())
    node.content.input_frames = []
    layout = QVBoxLayout()
    node.content.create_layout(layout)
    assert layout.count() == 1

    node.content.input_frames = [pl.DataFrame({"a": [1]})]
    node.content.input_variables = ["in0"]
    layout2 = QVBoxLayout()
    node.content.create_layout(layout2)
    assert node.content.mode_combo is not None
    assert node.content.mode_combo.currentText() == "Auto by Name"


def main() -> None:
    test_by_name_unions_columns_with_null_fill()
    test_by_position_ignores_names_pads_short_rows()
    test_manual_aligns_renamed_columns_and_nulls_unmapped()
    test_dtype_conflict_coerces_to_string_with_warning()
    test_empty_inputs_return_none()
    test_scene_eval_reads_edges_in_order()
    test_scene_reorder_changes_row_order()
    test_scene_no_edges_is_invalid()
    test_serialize_round_trip()
    test_get_code_executes()
    test_create_layout_empty_state_and_mode()
    print("ok")


if __name__ == "__main__":
    main()
