#!/usr/bin/env python3
"""Node names: palette, canvas and loaded files agree on one name.

Three node types were renamed to a shorter word - "Generate Rows" to "Rows",
"Normalize Columns" to "Normalize", "Count Records" to "Count". A file saved
before a rename carries the old title inside it, so loading must not resurrect
it, and the palette registry must not drift from the node classes.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtWidgets import QApplication, QMainWindow

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.performance_scene import TriggerScene
from trigger_designer.qt.widgets.nodes.unknown import TriggerNode_Unknown

APP = QApplication.instance() or QApplication([])

RENAMES = [
    (
        NodeTypes.PREPARATION,
        PreparationNodes.DYNAMIC_ROW_BUILDER,
        "Preparation.dynamic_row_builder",
        "Rows",
    ),
    (
        NodeTypes.PREPARATION,
        PreparationNodes.NORMALIZE_COLUMNS,
        "Preparation.normalize_columns",
        "Normalize",
    ),
    (
        NodeTypes.TRANSFORM,
        TransformNodes.COUNT_RECORDS,
        "Transform.count_records",
        "Count",
    ),
]


def _spec_titles() -> dict[str, str]:
    from trigger_designer.qt.widgets.nodes import _LAZY_NODE_SPECS

    return {spec["module_path"]: spec["node_title"] for spec in _LAZY_NODE_SPECS}


@pytest.mark.parametrize(("node_type", "node_code", "module_path", "title"), RENAMES)
def test_the_class_and_the_palette_registry_share_one_name(
    node_type, node_code, module_path, title
) -> None:
    assert get_class_from_opcode(node_code, node_type).node_title == title
    assert _spec_titles()[module_path] == title


def test_a_file_saved_under_the_old_name_loads_with_the_new_one() -> None:
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(TransformNodes.COUNT_RECORDS, NodeTypes.TRANSFORM)
    node = cls(window.scene)
    window.scene.nodes.append(node)

    data = dict(node.serialize())
    data["title"] = "Count Records"  # what a file saved before the rename says

    assert node.deserialize(data, hashmap={}) is not False
    assert node.title == "Count"


def test_an_unknown_node_keeps_the_title_the_file_saved() -> None:
    """The placeholder has no name of its own, so the file's stands."""
    node = TriggerNode_Unknown(TriggerScene())
    node.title = "Count Records"
    data = node.serialize()

    fresh = TriggerNode_Unknown(TriggerScene())
    assert fresh.deserialize(data, hashmap={}) is not False
    assert fresh.title == "Count Records"
