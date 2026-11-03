"""Live error state, tooltip and badge on a real node."""

from __future__ import annotations

import math

import polars as pl
from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QColor, QImage, QPainter
from qtpy.QtWidgets import QStyleOptionGraphicsItem

from trigger_designer.core.errors import ErrorContext, make_error
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    return window, node


def _render_node(node) -> tuple[QImage, QRectF]:
    """Paint the node item alone, so only what ``paint`` draws is sampled."""
    gr_node = node.grNode
    rect = gr_node.boundingRect()
    image = QImage(
        math.ceil(rect.width()),
        math.ceil(rect.height()),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.translate(-rect.topLeft())
    gr_node.paint(painter, QStyleOptionGraphicsItem())
    painter.end()
    return image, rect


def _count_pixels(image: QImage, area: QRectF, origin: QRectF, test) -> int:
    left = math.floor(area.left() - origin.left())
    right = math.ceil(area.right() - origin.left())
    top = math.floor(area.top() - origin.top())
    bottom = math.ceil(area.bottom() - origin.top())
    count = 0
    for y in range(max(0, top), min(image.height(), bottom)):
        for x in range(max(0, left), min(image.width(), right)):
            if test(image.pixelColor(x, y)):
                count += 1
    return count


def _is_danger(color: QColor) -> bool:
    return (
        color.alpha() > 200
        and color.red() > color.green() + 60
        and color.red() > color.blue() + 60
    )


def _is_warning(color: QColor) -> bool:
    return (
        color.alpha() > 200 and color.red() > 150 and color.green() > color.blue() + 40
    )


def _badge_node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = SelectNode(window.scene)
    window.scene.nodes.append(node)
    return window, node


def test_an_error_draws_one_indicator_on_the_bottom_edge(qtbot) -> None:
    """Issue #4: the bottom badge and the top-right badge were both drawn."""
    _window, node = _badge_node(qtbot)
    node.set_error(make_error("TD-SYS-001", message="bad"), "live")
    image, rect = _render_node(node)
    gr_node = node.grNode

    assert _count_pixels(image, gr_node.statusBadgeRect(), rect, _is_danger) > 100

    old_top_right = QRectF(gr_node.width - 19.0, 5.0, 14.0, 14.0)
    assert _count_pixels(image, old_top_right, rect, lambda c: c.alpha() > 0) == 0


def test_a_warning_uses_the_same_single_indicator(qtbot) -> None:
    _window, node = _badge_node(qtbot)
    node.set_error(make_error("TD-RUN-004"), "live")
    image, rect = _render_node(node)
    gr_node = node.grNode

    assert _count_pixels(image, gr_node.statusBadgeRect(), rect, _is_warning) > 100
    assert _count_pixels(image, gr_node.statusBadgeRect(), rect, _is_danger) == 0

    old_top_right = QRectF(gr_node.width - 19.0, 5.0, 14.0, 14.0)
    assert _count_pixels(image, old_top_right, rect, lambda c: c.alpha() > 0) == 0


def test_hiding_the_status_badge_keeps_the_error_visible(qtbot) -> None:
    _window, node = _badge_node(qtbot)
    node.grNode._badge_visible = False
    node.set_error(make_error("TD-SYS-001", message="bad"), "live")
    image, rect = _render_node(node)

    assert _count_pixels(image, node.grNode.statusBadgeRect(), rect, _is_danger) > 100


def test_set_error_sets_tooltip_badge_and_problems(qtbot) -> None:
    window, node = _node(qtbot)
    error = make_error(
        "TD-SYS-001",
        ErrorContext.from_node(node, "live"),
        message="Both inputs must be connected",
    )
    node.set_error(error, "live")
    assert "Both inputs must be connected" in node.grNode.toolTip()
    assert node.grNode._error_badge == "error"
    assert node.current_error is error
    assert window.problems.count() == 1


def test_run_error_wins_then_live_reappears(qtbot) -> None:
    _window, node = _node(qtbot)
    live = make_error("TD-SYS-001", message="live problem")
    run = make_error("TD-RUN-001", seconds="30")
    node.set_error(live, "live")
    node.set_error(run, "run")
    assert node.current_error is run
    assert "30" in node.grNode.toolTip()
    node.clear_error("run")
    assert node.current_error is live


def test_clear_error_clears_tooltip_and_badge(qtbot) -> None:
    _window, node = _node(qtbot)
    node.set_error(make_error("TD-SYS-001", message="bad"), "live")
    node.clear_error()
    assert node.grNode.toolTip() == ""
    assert node.grNode._error_badge == ""


def test_live_eval_translates_an_exception(qtbot) -> None:
    _window, node = _node(qtbot)

    def broken(_inputs):
        raise ValueError("Both inputs must be connected")

    node.processInputs = broken
    node.markDirty(True)
    node.eval()
    assert node.current_error is not None
    assert node.current_error.code == "TD-SYS-001"
    assert "Both inputs must be connected" in node.grNode.toolTip()
    assert node.grNode._error_badge == "error"


def test_successful_eval_clears_the_live_error(qtbot) -> None:
    _window, node = _node(qtbot)
    node.set_error(make_error("TD-SYS-001", message="old"), "live")

    def ok(_inputs):
        return [{"data": pl.DataFrame({"a": [1]}), "variable_name": "x"}]

    node.processInputs = ok
    node.markDirty(True)
    node.eval()
    assert node.current_error is None
    assert node.grNode.toolTip() == ""
    assert node.grNode._error_badge == ""


def test_warning_severity_uses_warning_badge(qtbot) -> None:
    _window, node = _node(qtbot)
    node.set_error(make_error("TD-RUN-004"), "live")
    assert node.grNode._error_badge == "warning"
