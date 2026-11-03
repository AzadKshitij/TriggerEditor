"""Arrangement maths and the commands behind the Arrange menus.

The functions here only move ``TriggerNode`` objects. A node's footprint is
its body rectangle: the scene position plus the graphics node's declared
``width`` and ``height``. Everything returns ``(node, new_position)`` pairs so
the caller can decide when to apply them, and so the geometry can be tested
without opening a window.

Two rules the commands share:

* The selection keeps its place. Align centres on the selection's bounding
  box and arrange starts at its top-left corner, so a command tidies a group
  of nodes without also dragging it somewhere else.
* Nothing moves when the result equals the current layout. A pressed command
  that changes nothing must not push an undo step.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, sqrt
from typing import Any, Iterable, Optional, Sequence

from loguru import logger
from qtpy.QtCore import QPointF, QRectF

#: Space left between neighbouring nodes by the arrange commands.
GAP = 40.0

#: Qt positions are floats; anything smaller than this is the same place.
EPSILON = 1e-6


@dataclass(frozen=True)
class ArrangeCommand:
    """One entry of the Arrange menu, and what it does."""

    id: str
    label: str
    undo_label: str
    minimum: int
    default_shortcut: str = ""
    #: Attribute name of the ``QAction`` the main window creates for it.
    action: str = ""
    group: str = "Arrange"


COMMANDS: tuple[ArrangeCommand, ...] = (
    ArrangeCommand(
        "align_centers_h",
        "Align Horizontal Centers",
        "Aligned Horizontal Centers",
        2,
        default_shortcut="Ctrl+Shift+H",
        action="actArrangeAlignH",
    ),
    ArrangeCommand(
        "align_centers_v",
        "Align Vertical Centers",
        "Aligned Vertical Centers",
        2,
        default_shortcut="Ctrl+Shift+V",
        action="actArrangeAlignV",
    ),
    ArrangeCommand(
        "distribute_h",
        "Distribute Horizontally",
        "Distributed Horizontally",
        3,
        action="actArrangeDistributeH",
    ),
    ArrangeCommand(
        "distribute_v",
        "Distribute Vertically",
        "Distributed Vertically",
        3,
        action="actArrangeDistributeV",
    ),
    ArrangeCommand(
        "arrange_row", "Arrange in Row", "Arranged in Row", 2, action="actArrangeRow"
    ),
    ArrangeCommand(
        "arrange_column",
        "Arrange in Column",
        "Arranged in Column",
        2,
        action="actArrangeColumn",
    ),
    ArrangeCommand(
        "arrange_grid",
        "Arrange in Grid",
        "Arranged in Grid",
        2,
        action="actArrangeGrid",
    ),
    ArrangeCommand(
        "snap_selection",
        "Snap Selection to Grid",
        "Snapped Nodes to Grid",
        2,
        action="actArrangeSnapSelection",
    ),
)

#: The snapping toggle. It is not an arrangement, so it has no minimum
#: selection, but it appears on the same shortcuts page.
TOGGLE_ID = "toggle_snap"
TOGGLE_ACTION = "actToggleSnap"
TOGGLE_COMMAND = ArrangeCommand(
    TOGGLE_ID,
    "Snap to Grid",
    "Snap to Grid",
    0,
    action=TOGGLE_ACTION,
    group="Grid",
)

COMMAND_BY_ID: dict[str, ArrangeCommand] = {command.id: command for command in COMMANDS}
SHORTCUT_COMMANDS: tuple[ArrangeCommand, ...] = COMMANDS + (TOGGLE_COMMAND,)


# ----------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------


def node_position(node: Any) -> QPointF:
    """A node's scene position, whichever API it exposes.

    ``TriggerNode`` defines ``pos`` as a *property* that forwards to its
    graphics node, while a ``QGraphicsItem`` exposes ``pos()`` as a method.
    Reading the graphics item directly works for both and keeps a stand-in
    node in the tests honest.
    """
    graphics = getattr(node, "grNode", None)
    position = getattr(graphics, "pos", None)
    if callable(position):
        return QPointF(position())
    position = getattr(node, "pos", None)
    if isinstance(position, QPointF):
        return QPointF(position)
    if callable(position):
        return QPointF(position())
    return QPointF()


def node_rect(node: Any) -> QRectF:
    """The node's body in scene coordinates."""
    graphics = getattr(node, "grNode", None)
    width = float(getattr(graphics, "width", 120.0) or 120.0)
    height = float(getattr(graphics, "height", 120.0) or 120.0)
    position = node_position(node)
    return QRectF(float(position.x()), float(position.y()), width, height)


def nearest_multiple(value: float, grid: float) -> float:
    """Round ``value`` to the closest multiple of ``grid``, halves upward."""
    if grid <= 0:
        return float(value)
    return floor(float(value) / grid + 0.5) * grid


def _moved(node: Any, x: float, y: float) -> bool:
    position = node_position(node)
    return (
        abs(float(position.x()) - x) > EPSILON or abs(float(position.y()) - y) > EPSILON
    )


def _moves(pairs: Iterable[tuple[Any, float, float]]) -> list[tuple[Any, QPointF]]:
    """Keep only the nodes a command actually moves."""
    moves: list[tuple[Any, QPointF]] = []
    for node, x, y in pairs:
        if _moved(node, x, y):
            moves.append((node, QPointF(x, y)))
    return moves


def selection_bounds(nodes: Sequence[Any]) -> QRectF:
    """Bounding box of the nodes' bodies."""
    rects = [node_rect(node) for node in nodes]
    bounds = QRectF(rects[0])
    for rect in rects[1:]:
        bounds = bounds.united(rect)
    return bounds


def align_centers(
    nodes: Sequence[Any], *, horizontal: bool
) -> list[tuple[Any, QPointF]]:
    """Give every node the same centre.

    ``horizontal`` shares the X centre (the nodes stack vertically);
    otherwise the Y centre is shared (the nodes line up across). The shared
    value is the centre of the whole selection, not of any one node.
    """
    if len(nodes) < 2:
        return []
    bounds = selection_bounds(nodes)
    pairs = []
    for node in nodes:
        rect = node_rect(node)
        if horizontal:
            pairs.append((node, bounds.center().x() - rect.width() / 2.0, rect.top()))
        else:
            pairs.append((node, rect.left(), bounds.center().y() - rect.height() / 2.0))
    return _moves(pairs)


def distribute(nodes: Sequence[Any], *, horizontal: bool) -> list[tuple[Any, QPointF]]:
    """Even out the gaps between node edges.

    The outermost two nodes stay where they are and the rest are spread
    between them with one equal gap. When the selection is too tight to hold
    its neighbours without overlapping, the gap bottoms out at zero instead
    of turning negative.
    """
    if len(nodes) < 3:
        return []
    items = [(node, node_rect(node)) for node in nodes]
    if horizontal:
        items.sort(key=lambda pair: (pair[1].left(), pair[1].top()))
        span = items[-1][1].right() - items[0][1].left()
        used = sum(rect.width() for _, rect in items)
        gap = max((span - used) / (len(items) - 1), 0.0)
        cursor = items[0][1].left()
        pairs = []
        for node, rect in items:
            pairs.append((node, cursor, rect.top()))
            cursor += rect.width() + gap
        return _moves(pairs)

    items.sort(key=lambda pair: (pair[1].top(), pair[1].left()))
    span = items[-1][1].bottom() - items[0][1].top()
    used = sum(rect.height() for _, rect in items)
    gap = max((span - used) / (len(items) - 1), 0.0)
    cursor_y = items[0][1].top()
    pairs = []
    for node, rect in items:
        pairs.append((node, rect.left(), cursor_y))
        cursor_y += rect.height() + gap
    return _moves(pairs)


def arrange(nodes: Sequence[Any], mode: str) -> list[tuple[Any, QPointF]]:
    """Lay the selection out as a row, a column or a grid.

    Order follows the positions the user already sees: top-to-bottom then
    left-to-right for rows and grids, left-to-right then top-to-bottom for
    columns. A grid uses ``ceil(sqrt(n))`` columns.
    """
    if len(nodes) < 2:
        return []
    items = [(node, node_rect(node)) for node in nodes]
    bounds = selection_bounds(nodes)
    left, top = bounds.left(), bounds.top()

    if mode == "row":
        ordered = sorted(items, key=lambda pair: (pair[1].top(), pair[1].left()))
        cursor = left
        pairs = []
        for node, rect in ordered:
            pairs.append((node, cursor, top))
            cursor += rect.width() + GAP
        return _moves(pairs)

    if mode == "column":
        ordered = sorted(items, key=lambda pair: (pair[1].left(), pair[1].top()))
        cursor = top
        pairs = []
        for node, rect in ordered:
            pairs.append((node, left, cursor))
            cursor += rect.height() + GAP
        return _moves(pairs)

    if mode != "grid":
        raise ValueError(f"unknown arrange mode: {mode!r}")

    ordered = sorted(items, key=lambda pair: (pair[1].top(), pair[1].left()))
    columns = max(1, ceil(sqrt(len(ordered))))
    cell_width = max(rect.width() for _, rect in ordered)
    cell_height = max(rect.height() for _, rect in ordered)
    pairs = []
    for index, (node, _rect) in enumerate(ordered):
        row, column = divmod(index, columns)
        pairs.append(
            (
                node,
                left + column * (cell_width + GAP),
                top + row * (cell_height + GAP),
            )
        )
    return _moves(pairs)


def snap_position(position: QPointF, grid: float) -> QPointF:
    return QPointF(
        nearest_multiple(position.x(), grid), nearest_multiple(position.y(), grid)
    )


def snap_moves(nodes: Sequence[Any], grid: float) -> list[tuple[Any, QPointF]]:
    """Round every node's position onto the grid."""
    if grid <= 0:
        return []
    pairs = []
    for node in nodes:
        target = snap_position(node_position(node), grid)
        pairs.append((node, target.x(), target.y()))
    return _moves(pairs)


def moves_for(
    command: ArrangeCommand, nodes: Sequence[Any], grid: float
) -> list[tuple[Any, QPointF]]:
    """The positions ``command`` wants, for this selection."""
    if command.id == "align_centers_h":
        return align_centers(nodes, horizontal=True)
    if command.id == "align_centers_v":
        return align_centers(nodes, horizontal=False)
    if command.id == "distribute_h":
        return distribute(nodes, horizontal=True)
    if command.id == "distribute_v":
        return distribute(nodes, horizontal=False)
    if command.id == "arrange_row":
        return arrange(nodes, "row")
    if command.id == "arrange_column":
        return arrange(nodes, "column")
    if command.id == "arrange_grid":
        return arrange(nodes, "grid")
    if command.id == "snap_selection":
        return snap_moves(nodes, grid)
    raise ValueError(f"unknown arrange command: {command.id!r}")


# ----------------------------------------------------------------------
# Scene helpers
# ----------------------------------------------------------------------


def selected_nodes(scene: Any) -> list[Any]:
    """The scene's selected nodes, in selection order and without repeats."""
    nodes: list[Any] = []
    try:
        items = scene.getSelectedItems()
    except Exception:
        return nodes
    for item in items:
        node = getattr(item, "node", None)
        if node is not None and node not in nodes:
            nodes.append(node)
    return nodes


def grid_size(scene: Any) -> float:
    graphics = getattr(scene, "grScene", None)
    try:
        return float(getattr(graphics, "gridSize", 20) or 20)
    except TypeError, ValueError:
        return 20.0


def snap_enabled(scene: Any) -> bool:
    """Whether dragging a node snaps. Defaults on, like the preference."""
    graphics = getattr(scene, "grScene", None)
    if graphics is None:
        return False
    return bool(getattr(graphics, "snap_to_grid", True))


def _apply_snap_flag(scene: Any, enabled: bool) -> None:
    graphics = getattr(scene, "grScene", None)
    if graphics is None:
        return
    try:
        graphics.snap_to_grid = bool(enabled)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Unable to set snapping on the canvas: {exc}")


def _open_scenes() -> list[Any]:
    """Every open editor scene, so a preference change reaches all windows."""
    from qtpy.QtWidgets import QApplication

    scenes: list[Any] = []
    for widget in QApplication.allWidgets():
        scene = getattr(widget, "scene", None)
        if scene is None or not hasattr(scene, "grScene"):
            continue
        if scene not in scenes:
            scenes.append(scene)
    return scenes


def set_snap_enabled(
    scene: Optional[Any] = None, enabled: bool = True, *, persist: bool = True
) -> None:
    """Turn snapping on or off for every open canvas, and remember the choice.

    ``scene`` may be omitted when the caller is the preferences dialog and
    has no canvas of its own; every open canvas is found instead.
    """
    if persist:
        try:
            from trigger_designer.qt.preferences import get_preferences

            get_preferences().set("editor/snap_to_grid", bool(enabled))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Unable to save the snapping preference: {exc}")

    targets = [scene]
    for other in _open_scenes():
        if other not in targets:
            targets.append(other)
    for target in targets:
        _apply_snap_flag(target, enabled)


def push_moves(scene: Any, moves: Sequence[tuple[Any, QPointF]], text: str) -> bool:
    """Record ``moves`` as one undo step and apply them.

    Falls back to applying the positions directly when the scene has no
    undo timeline (a bare ``Scene`` in a test, for instance).
    """
    moves = [(node, node_position(node), QPointF(target)) for node, target in moves]
    history = getattr(scene, "history", None)
    if history is None or not hasattr(history, "push_edit"):
        for node, _old, new in moves:
            node.setPos(new.x(), new.y())
        return True

    from trigger_designer.qt.undo.commands import MoveNodesCommand

    pushed = history.push_edit(MoveNodesCommand(moves, text), modified=True)
    return bool(pushed)


def apply_command(
    scene: Any, command_id: str, nodes: Optional[Sequence[Any]] = None
) -> bool:
    """Run one Arrange command on ``nodes`` (default: the selection).

    :return: ``True`` when the layout changed and an undo step was recorded.
    """
    command = COMMAND_BY_ID.get(command_id)
    if command is None:
        logger.warning(f"Unknown arrange command: {command_id!r}")
        return False

    selection = list(nodes) if nodes is not None else selected_nodes(scene)
    selection = [
        node
        for node in dict.fromkeys(selection)
        if node is not None and getattr(node, "grNode", None) is not None
    ]
    if len(selection) < command.minimum:
        return False

    moves = moves_for(command, selection, grid_size(scene))
    if not moves:
        return False
    return push_moves(scene, moves, command.undo_label)


def snap_node_to_grid(node: Any, grid: float) -> None:
    """Place a freshly created node on the grid."""
    if grid <= 0 or node is None:
        return
    target = snap_position(node_position(node), grid)
    if _moved(node, target.x(), target.y()):
        node.setPos(target.x(), target.y())
