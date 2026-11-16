"""Node palette entries are listed alpha-numerically by title (issue #42).

The palette used to follow registration/opcode order, so identically titled
nodes sat next to each other only by accident. Users scan the palette by the
label under each icon, so that label is the order that matters.
"""

from __future__ import annotations

from trigger_designer.core.node_configuration import NODE_REGISTRIES, NodeTypes
from trigger_designer.qt.widgets.node_drag_listbox import (
    QTRDragListbox,
    _alphanumeric_key,
)


def _titles(palette: QTRDragListbox) -> list[str]:
    titles = []
    for row in range(palette.count()):
        widget = palette.itemWidget(palette.item(row))
        titles.append(widget.text_label.text())
    return titles


def test_every_family_lists_nodes_by_title(qtbot) -> None:
    for node_type in NodeTypes:
        palette = QTRDragListbox(node_type=node_type)
        qtbot.addWidget(palette)

        titles = _titles(palette)
        assert len(titles) == len(NODE_REGISTRIES[node_type])
        assert titles == sorted(titles, key=str.casefold), (
            f"{node_type.value} palette is not alphabetical: {titles}"
        )


def test_alphanumeric_key_orders_numbers_by_value() -> None:
    values = ["Step 10", "alpha", "Step 2", "Beta"]
    assert sorted(values, key=_alphanumeric_key) == [
        "alpha",
        "Beta",
        "Step 2",
        "Step 10",
    ]
