"""Arrangement maths and the undo step behind the Arrange menus.

Geometry is tested against stand-in nodes, so the numbers can be asserted
without a window; the history and canvas-flag tests at the bottom drive a real
:class:`TriggerScene` offscreen.
"""

from __future__ import annotations

import math
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

import pytest
from qtpy.QtCore import QPointF
from qtpy.QtGui import QColor, QPen
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.helpers import node_arrange
from trigger_designer.qt.performance_scene import TriggerScene
from trigger_designer.qt.theme_manager import apply_theme_to_scene
from trigger_designer.qt.undo.commands import MoveNodesCommand

APP = QApplication.instance() or QApplication([])


class FakeGraphics:
    """The graphics item: a real ``QGraphicsItem`` exposes ``pos()``."""

    def __init__(self, width: float = 120.0, height: float = 120.0) -> None:
        self.width = width
        self.height = height
        self._pos = QPointF(0.0, 0.0)

    def pos(self) -> QPointF:
        return QPointF(self._pos)

    def setPos(self, x: float, y: float) -> None:
        self._pos = QPointF(x, y)


class FakeNode:
    """Just enough of ``TriggerNode`` for the geometry helpers.

    ``TriggerNode.pos`` is a *property* forwarding to the graphics node, not a
    method. Keeping that shape here makes the doubles catch a call site that
    treats it as one.
    """

    def __init__(self, x: float, y: float, width: float = 120.0, height: float = 120.0):
        self.grNode = FakeGraphics(width, height)
        self.parent_group = None
        self.setPos(x, y)

    @property
    def pos(self) -> QPointF:
        return self.grNode.pos()

    def setPos(self, x: float, y: float) -> None:
        self.grNode.setPos(float(x), float(y))

    def position(self) -> tuple[float, float]:
        point = self.pos
        return point.x(), point.y()


def at(nodes, moves) -> dict[int, tuple[float, float]]:
    """Target positions keyed by ``id(node)``, read the way tests compare."""
    return {id(node): (point.x(), point.y()) for node, point in moves}


# -- geometry ------------------------------------------------------------


def test_node_rect_uses_the_body_not_the_origin():
    node = FakeNode(30.0, 40.0, width=140.0, height=90.0)
    rect = node_arrange.node_rect(node)
    assert (rect.left(), rect.top()) == (30.0, 40.0)
    assert (rect.width(), rect.height()) == (140.0, 90.0)


def test_align_horizontal_centers_shares_the_selection_centre():
    left = FakeNode(0.0, 0.0)
    right = FakeNode(300.0, 200.0)

    moves = node_arrange.align_centers([left, right], horizontal=True)

    # Bounds are 0..420 wide, so the shared centre is 210 and every body starts
    # at 150. Vertical positions are untouched.
    assert at([left, right], moves) == {
        id(left): (150.0, 0.0),
        id(right): (150.0, 200.0),
    }
    assert left.position()[1] == 0.0 and right.position()[1] == 200.0


def test_align_vertical_centers_shares_the_selection_centre():
    top = FakeNode(0.0, 0.0)
    bottom = FakeNode(300.0, 400.0)

    moves = node_arrange.align_centers([top, bottom], horizontal=False)

    assert at([top, bottom], moves) == {
        id(top): (0.0, 200.0),
        id(bottom): (300.0, 200.0),
    }


def test_align_of_already_aligned_nodes_changes_nothing():
    first = FakeNode(100.0, 0.0)
    second = FakeNode(100.0, 200.0)
    assert node_arrange.align_centers([first, second], horizontal=True) == []


def test_align_ignores_a_single_node():
    assert node_arrange.align_centers([FakeNode(0.0, 0.0)], horizontal=True) == []


def test_distribute_horizontal_keeps_the_outer_nodes_and_evens_the_gaps():
    first = FakeNode(0.0, 0.0)
    middle = FakeNode(140.0, 0.0)
    last = FakeNode(400.0, 0.0)

    moves = node_arrange.distribute([first, middle, last], horizontal=True)

    # Span 0..520, three 120-wide bodies: 80 units of gap split in two.
    assert at([first, middle, last], moves) == {id(middle): (200.0, 0.0)}


def test_distribute_vertical_sorts_by_position_not_by_argument_order():
    first = FakeNode(0.0, 300.0)
    middle = FakeNode(0.0, 0.0)
    last = FakeNode(0.0, 380.0)

    moves = node_arrange.distribute([first, middle, last], horizontal=False)

    # Sorted: middle (0), first (300), last (380). Span 0..500, 360 used,
    # gap 70, so the middle node stays and the second lands at 190.
    assert at([first, middle, last], moves) == {
        id(first): (0.0, 190.0),
    }


def test_distribute_clamps_a_negative_gap_to_zero():
    first = FakeNode(0.0, 0.0)
    middle = FakeNode(10.0, 0.0)
    last = FakeNode(20.0, 0.0)

    moves = node_arrange.distribute([first, middle, last], horizontal=True)

    assert at([first, middle, last], moves) == {
        id(middle): (120.0, 0.0),
        id(last): (240.0, 0.0),
    }


def test_distribute_needs_three_nodes():
    assert (
        node_arrange.distribute(
            [FakeNode(0.0, 0.0), FakeNode(9.0, 0.0)], horizontal=True
        )
        == []
    )


def test_arrange_row_starts_at_the_selection_top_left():
    second = FakeNode(0.0, 400.0)
    first = FakeNode(300.0, 0.0)

    moves = node_arrange.arrange([second, first], "row")

    # Bounds start at (0, 0); first in reading order is the top node.
    assert at([second, first], moves) == {
        id(first): (0.0, 0.0),
        id(second): (160.0, 0.0),
    }


def test_arrange_column_stacks_top_to_bottom_with_one_gap():
    first = FakeNode(0.0, 300.0)
    second = FakeNode(500.0, 0.0)

    moves = node_arrange.arrange([first, second], "column")

    assert at([first, second], moves) == {
        id(first): (0.0, 0.0),
        id(second): (0.0, 160.0),
    }


def test_arrange_grid_uses_a_square_ish_table():
    nodes = [FakeNode(float(index * 10), float(index * 7)) for index in range(5)]

    moves = node_arrange.arrange(nodes, "grid")
    targets = at(nodes, moves)

    columns = math.ceil(math.sqrt(len(nodes)))
    cell = 120.0 + node_arrange.GAP
    for index, node in enumerate(nodes):
        row, column = divmod(index, columns)
        if index == 0:
            # The first node is already at the grid origin.
            assert id(node) not in targets
            continue
        assert targets[id(node)] == (column * cell, row * cell)


def test_arrange_rejects_an_unknown_mode():
    with pytest.raises(ValueError):
        node_arrange.arrange([FakeNode(0.0, 0.0), FakeNode(1.0, 1.0)], "spiral")


def test_nearest_multiple_rounds_halves_up():
    assert node_arrange.nearest_multiple(29.9, 20) == 20.0
    assert node_arrange.nearest_multiple(30.0, 20) == 40.0
    assert node_arrange.nearest_multiple(-10.0, 20) == -0.0
    assert node_arrange.nearest_multiple(7.0, 0) == 7.0


def test_snap_moves_rounds_both_axes_and_skips_nodes_already_on_the_grid():
    aligned = FakeNode(40.0, 60.0)
    off = FakeNode(47.0, 11.0)

    moves = node_arrange.snap_moves([aligned, off], 20.0)

    assert len(moves) == 1
    node, target = moves[0]
    assert node is off
    assert (target.x(), target.y()) == (40.0, 20.0)


def test_moves_for_dispatches_each_command():
    nodes = [FakeNode(0.0, 0.0), FakeNode(0.0, 200.0)]
    for command in node_arrange.COMMANDS:
        moves = node_arrange.moves_for(command, nodes, 20.0)
        assert isinstance(moves, list)

    with pytest.raises(ValueError):
        node_arrange.moves_for(
            node_arrange.ArrangeCommand("nope", "Nope", "Nope", 1), nodes, 20.0
        )


def test_apply_command_refuses_a_selection_below_its_minimum():
    scene = SimpleNamespace(grScene=None)
    assert not node_arrange.apply_command(scene, "arrange_row", [FakeNode(0.0, 0.0)])


# -- undo ----------------------------------------------------------------


def test_move_nodes_command_undoes_and_redoes_one_batch():
    first = FakeNode(0.0, 0.0)
    second = FakeNode(100.0, 100.0)
    command = MoveNodesCommand(
        [
            (first, QPointF(0.0, 0.0), QPointF(20.0, 40.0)),
            (second, QPointF(100.0, 100.0), QPointF(120.0, 140.0)),
        ],
        "Arranged in Row",
    )

    command.redo()
    assert first.position() == (20.0, 40.0)
    assert second.position() == (120.0, 140.0)

    command.undo()
    assert first.position() == (0.0, 0.0)
    assert second.position() == (100.0, 100.0)


def test_move_nodes_command_keeps_its_own_copy_of_the_positions():
    node = FakeNode(0.0, 0.0)
    new = QPointF(60.0, 0.0)
    command = MoveNodesCommand([(node, QPointF(0.0, 0.0), new)], "Moved")
    new.setX(999.0)

    command.redo()

    assert node.position() == (60.0, 0.0)


def test_move_nodes_command_refits_a_parent_group():
    class FakeGroup:
        def __init__(self) -> None:
            self.updates = 0

        def updateBounds(self) -> None:
            self.updates += 1

    group = FakeGroup()
    node = FakeNode(0.0, 0.0)
    node.parent_group = group

    command = MoveNodesCommand(
        [(node, QPointF(0.0, 0.0), QPointF(10.0, 10.0))], "Moved"
    )
    command.redo()
    command.undo()

    assert group.updates == 2


# -- scene integration ---------------------------------------------------


@pytest.fixture
def scene() -> TriggerScene:
    return TriggerScene()


def test_apply_command_records_one_undo_step(scene: TriggerScene):
    left = FakeNode(0.0, 0.0)
    right = FakeNode(300.0, 100.0)

    assert node_arrange.apply_command(scene, "align_centers_h", [left, right])
    assert left.position() == (150.0, 0.0)
    assert right.position() == (150.0, 100.0)
    assert scene.has_been_modified

    assert scene.history.undo()
    assert left.position() == (0.0, 0.0)
    assert right.position() == (300.0, 100.0)

    assert scene.history.redo()
    assert left.position() == (150.0, 0.0)


def test_apply_command_does_not_record_a_no_op(scene: TriggerScene):
    first = FakeNode(100.0, 0.0)
    second = FakeNode(100.0, 200.0)

    assert not node_arrange.apply_command(scene, "align_centers_h", [first, second])
    assert not scene.history.canUndo()


def test_snap_enabled_defaults_on_and_follows_the_scene_flag(scene: TriggerScene):
    scene.grScene.snap_to_grid = True
    assert node_arrange.snap_enabled(scene)

    scene.grScene.snap_to_grid = False
    assert not node_arrange.snap_enabled(scene)


# -- canvas flag ---------------------------------------------------------


class FakePreferences:
    def __init__(self, values: dict) -> None:
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeManager:
    def __init__(self, prefs: FakePreferences) -> None:
        self.preferences = prefs

    def color(self, _key: str, default: str) -> str:
        return default


class FakeGraphicsScene:
    def __init__(self) -> None:
        self._pen_light = QPen(QColor("#000000"))
        self._pen_dark = QPen(QColor("#000000"))
        self._color_light = QColor("#000000")
        self._color_dark = QColor("#000000")
        self.gridSize = 0
        self.showGrid = False
        self.snap_to_grid = False

    def setBackgroundColor(self, _colour) -> None:
        pass

    def update(self) -> None:
        pass


def test_apply_theme_to_scene_pushes_the_snap_preference():
    graphics = FakeGraphicsScene()
    scene = SimpleNamespace(grScene=graphics)

    apply_theme_to_scene(
        scene, FakeManager(FakePreferences({"editor/snap_to_grid": False}))
    )

    assert graphics.snap_to_grid is False
    assert graphics.gridSize == 20
    assert graphics.showGrid is True


def test_apply_theme_to_scene_defaults_snapping_on():
    graphics = FakeGraphicsScene()
    scene = SimpleNamespace(grScene=graphics)

    apply_theme_to_scene(scene, FakeManager(FakePreferences({})))

    assert graphics.snap_to_grid is True
