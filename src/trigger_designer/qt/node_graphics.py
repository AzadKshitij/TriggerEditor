"""Canvas painting and theme state for a node.

``TriggerGraphicsNode`` owns geometry (body, badge and ring rectangles), the
state-ring pens, the status and error badges and the low-detail fallback. It
never imports ``node_base``; the node is only a type here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Optional

from nodeeditor.node_icon_graphics_node import QDMIconGraphicsNode
from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from qtpy.QtWidgets import (
    QGraphicsItem,
    QLabel,
    QStyleOptionGraphicsItem,
    QWidget,
)

from trigger_designer.qt.helpers.node_arrange import EPSILON, nearest_multiple
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.theme_manager import get_theme_manager

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class TriggerGraphicsNode(QDMIconGraphicsNode):
    # Add signal for evaluation requests

    rsm = ResourceManager()

    #: Side of the status badge ``paint`` draws on the node's bottom edge.
    STATUS_BADGE_SIDE = 24.0

    #: Width of the state ring ``paint`` strokes the body with. Named because the
    #: declared rectangle has to account for half of it.
    RING_PEN_WIDTH = 5.0

    def __init__(
        self, node: "TriggerNode", parent: Optional[QGraphicsItem] = None
    ) -> None:
        # Set before super().__init__: Qt may ask for shape() during setup.
        self._shape_path: QPainterPath | None = None
        self._bounding_rect: QRectF | None = None
        self._detail_pixmap: QPixmap | None = None
        self._detail_pixmap_resolved = False
        self._error_badge = ""
        super().__init__(node, parent)
        self._pen_role = "default"
        self._rebuild_theme_pens()

    def bodyRect(self) -> QRectF:
        """The node body: title, content widget and state ring live here."""
        return QRectF(0.0, 0.0, self.width, self.height)

    def statusBadgeRect(self) -> QRectF:
        """Where ``paint`` draws the status badge, centred on the bottom edge."""
        side = self.STATUS_BADGE_SIDE
        return QRectF((self.width - side) / 2.0, self.height - side / 2.0, side, side)

    def boundingRect(self) -> QRectF:
        """The body, the badge below it, the state ring, and the floating label.

        Two things ``paint`` draws reach outside the body: the badge is centred
        on the bottom edge, so half of it is below, and the state ring strokes
        the body path with a 5px pen, so half of it is outside every edge. A
        ``boundingRect`` that stopped at the body was smaller than what the item
        drew; Qt repaints by the declared rectangle, so what fell outside was
        never cleared and every frame of a drag left another copy behind - the
        trail of green check badges and ring fragments under a dragged node.

        The label above the node counts for the same reason, and it cannot be
        part of the cached rectangle because its text sets its width. Qt dirties
        a moved item by its rectangle at the old position and its children only
        at the new one, so a label left out of it stayed painted where the node
        had been: the stack of plates above a dragged node.
        """
        if self._bounding_rect is None:
            margin = self.RING_PEN_WIDTH / 2.0 + 1.0
            rect = self.bodyRect().united(self.statusBadgeRect())
            self._bounding_rect = rect.adjusted(-margin, -margin, margin, margin)
        # A copy: callers treat the result as a value (``fitView`` used to call
        # ``moveTopLeft`` on it). Handing out the cached object let such a call
        # rewrite the item's bounds, and Qt then culled the item as if it sat at
        # twice its position.
        rect = QRectF(self._bounding_rect)
        # Only the body/badge/ring rectangle is cached here. ``labelRect``
        # caches itself in nodeeditor and drops that cache whenever the text,
        # visibility or font changes, so the union stays cheap but current.
        label_rect = getattr(self, "labelRect", None)
        if label_rect is not None:  # nodeeditor before 0.8.2
            rect = rect.united(label_rect())
        return rect

    def shape(self) -> QPainterPath:
        """The node's hit/selection shape, built once.

        ``QGraphicsItem``'s default ``shape()`` allocates a fresh
        ``QPainterPath`` from ``boundingRect()`` on every call, and a rubber-band
        selection or a full repaint calls it once per node per pass. The
        geometry never changes after ``initSizes``.

        It is the body, not the bounding rect: the state ring is drawn from this
        path, and the ring has to follow the node, not the badge.
        """
        if self._shape_path is None:
            path = QPainterPath()
            path.addRect(self.bodyRect())
            self._shape_path = path
        return self._shape_path

    def _pen_from_token(self, token: str, fallback: str) -> QPen:
        pen = QPen(get_theme_manager().color(token, fallback))
        pen.setWidthF(self.RING_PEN_WIDTH)
        return pen

    def _rebuild_theme_pens(self) -> None:
        """State rings come from theme tokens, never hardcoded hex."""
        # Transparent so an idle node draws no ring at all.
        self._default_pen = QPen(QColor.fromRgb(0, 0, 0, 0))
        self._default_pen.setWidthF(self.RING_PEN_WIDTH)

        self._selected_pen = self._pen_from_token("node_selection", "#ffa637")
        self._executing_pen = self._pen_from_token("activity", "#9b7bd4")
        self._executed_pen = self._pen_from_token("success", "#48a878")
        self._error_pen = self._pen_from_token("danger", "#e0686c")
        self._pen = {
            "default": self._default_pen,
            "selected": self._selected_pen,
            "executing": self._executing_pen,
            "executed": self._executed_pen,
            "error": self._error_pen,
        }.get(self._pen_role, self._default_pen)

    def apply_theme(self) -> None:
        """Re-read state-ring colours after a theme change."""
        self._rebuild_theme_pens()
        self._detail_pixmap = None
        self._detail_pixmap_resolved = False
        self.update()

    def initSizes(self) -> None:
        super().initSizes()
        self.width = 120
        self.height = 120
        self.edge_roundness = 6
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10
        #: Whether the status badge may be drawn. The scene resolves the
        #: user's choice into this flag (see ``render_settings``).
        self._badge_visible = True
        # Derived geometry: drop anything cached against the previous size.
        self._bounding_rect = None
        self._shape_path = None

    def initAssets(self) -> None:
        super().initAssets()
        self.icons = self.rsm.get("status_icons")

        # Selection and hover outlines are UI furniture: keep them the same
        # width on screen at every zoom instead of letting a scene-space pen
        # fade to a sub-pixel line when the canvas is zoomed out.
        self._pen_selected.setCosmetic(True)
        self._pen_hovered.setCosmetic(True)

    def mouseMoveEvent(self, event) -> None:
        """Drag the node, then put it back on the grid.

        Qt moves every selected item by the same delta before this returns,
        so rounding only the grabbed node would shear the selection away from
        its neighbours. The same correction is applied to the rest of the
        selection, which keeps their relative offsets intact. Holding Alt
        leaves the node wherever the pointer is.
        """
        super().mouseMoveEvent(event)

        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            return

        scene = self.scene()
        if scene is None or not getattr(scene, "snap_to_grid", False):
            return
        try:
            grid = float(getattr(scene, "gridSize", 0) or 0)
        except TypeError, ValueError:
            return
        if grid <= 0:
            return

        position = self.pos()
        dx = nearest_multiple(position.x(), grid) - position.x()
        dy = nearest_multiple(position.y(), grid) - position.y()
        if abs(dx) < EPSILON and abs(dy) < EPSILON:
            return

        targets = scene.selectedItems()
        if self not in targets:
            # A drag normally selects the node first, but the correction must
            # not depend on that.
            targets.append(self)
        for item in targets:
            if not isinstance(item, TriggerGraphicsNode) or not item.isVisible():
                continue
            item.moveBy(dx, dy)

    def paint(
        self,
        painter: Optional[QPainter],
        option: Optional[QStyleOptionGraphicsItem],
        widget: Optional[QWidget] = None,
    ) -> None:

        if painter is None:
            return

        # Draw the border first. The default state ring is fully transparent
        # (an idle node draws none), and painting a transparent 120x120 path
        # per node per frame is pure cost - skip it unless a state ring is
        # actually visible.
        if self._pen.color().alpha() != 0:
            painter.setPen(self._pen)
            painter.drawPath(self.shape())

        # The card is the expensive half of a node: rendering a proxy widget
        # per node is what a zoomed-out frame is spent on. The node's whole
        # look is the icon pixmap that widget holds, so one scaled blit keeps
        # the graph readable for a fraction of the cost. Which of the two is
        # drawn is the user's call (see ``render_settings``).
        if not getattr(self, "_content_visible", True):
            self._paintLowDetail(painter)
            self._paintLowDetailHighlight(painter)
        else:
            # Draw node content
            super().paint(painter, option, widget)

        # Exactly one badge, in one place. A node with an error replaces the
        # normal status badge with the severity badge rather than drawing a
        # second copy at the top-right corner (issue #4).
        if self._error_badge:
            self._paint_error_badge(painter)
        elif getattr(self, "_badge_visible", True):
            offset = 24.0
            if self.node.isDirty():
                offset = 0.0
            if self.node.isInvalid():
                offset = 48.0

            side = self.STATUS_BADGE_SIDE
            painter.drawImage(
                self.statusBadgeRect(),
                self.icons,
                QRectF(offset, 0, side, side),
            )

    def set_error_badge(self, severity: str) -> None:
        value = severity if severity in {"error", "warning", "pending"} else ""
        if value == self._error_badge:
            return
        self._error_badge = value
        self.update()

    def _paint_error_badge(self, painter: QPainter) -> None:
        """Draw the one error indicator, in the status badge's place.

        It sits on the bottom edge like the normal badge, so an error never
        doubles up with a second glyph in the top-right corner. The colour
        keeps the severity: danger for a failed node, warning for a skipped
        one. A hidden status badge does not hide it - the reason a node failed
        stays visible.
        """
        if not self._error_badge:
            return
        manager = get_theme_manager()
        # "pending" (edited, not yet run) uses the warning colour too.
        token = "danger" if self._error_badge == "error" else "warning"
        fallback = "#e0686c" if token == "danger" else "#d9a441"
        fill = QColor(manager.color(token, fallback))
        rect = self.statusBadgeRect()
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawEllipse(rect)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(14)
        painter.setFont(font)
        # White on danger, as the status sprite uses. The warning gold is light
        # in every shipped theme, so its glyph is a darkened shade of the same
        # token - ``background_primary`` is itself light in the light themes.
        if token == "danger":
            text = QColor(manager.color("text_on_accent", "#ffffff"))
        else:
            text = fill.darker(300)
        painter.setPen(QPen(text))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "!")
        painter.restore()

    def _detailPixmap(self) -> QPixmap | None:
        """The pixmap that stands in for this node once the detail is off.

        Cached, because the fallback walks the content widget's children and
        this runs inside the paint pass.
        """
        if not self._detail_pixmap_resolved:
            self._detail_pixmap_resolved = True
            pixmap = getattr(getattr(self.node, "content", None), "icon", None)
            if pixmap is None or pixmap.isNull():
                pixmap = self._findContentPixmap()
            self._detail_pixmap = pixmap
        return self._detail_pixmap

    def _findContentPixmap(self) -> QPixmap | None:
        """Last resort: the first pixmap a label inside the content widget holds."""
        gr_content = getattr(self, "grContent", None)
        widget = gr_content.widget() if gr_content is not None else None
        if widget is None:
            return None
        for label in widget.findChildren(QLabel):
            pixmap = label.pixmap()
            if pixmap is not None and not pixmap.isNull():
                return pixmap
        return None

    def _paintLowDetail(self, painter: QPainter) -> None:
        """Draw the zoomed-out stand-in: one unscaled-smooth blit of the node icon."""
        pixmap = self._detailPixmap()
        if pixmap is None:
            return

        ratio = pixmap.devicePixelRatio() or 1.0
        width = pixmap.width() / ratio
        height = pixmap.height() / ratio
        target = QRectF(
            (self.width - width) / 2.0,
            (self.height - height) / 2.0,
            width,
            height,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        painter.restore()

    def _paintLowDetailHighlight(self, painter: QPainter) -> None:
        """Keep the selection/hover outline visible after the card is dropped.

        ``QDMIconGraphicsNode.paint`` is the only place the ring is drawn, and
        the low-detail branch never calls it. Its pens are cosmetic (see
        ``initAssets``), so the ring keeps the same on-screen width at every
        zoom; this only has to draw it in the branch that paints the icon
        instead of the card.
        """
        if not (self.hovered or self.isSelected()):
            return

        # Match ``QDMIconGraphicsNode.paint``: hover wins over selection. The
        # base pen is already cosmetic, so its width is in device pixels.
        pen = self._pen_hovered if self.hovered else self._pen_selected
        width = pen.widthF()

        # Draw the stroke just inside the base outline. The pen is measured in
        # device pixels, so convert half its width back into scene units and
        # inset the path by that much. Painting inward from the body edge keeps
        # the ring from straddling ``boundingRect``, where Qt would clip it or
        # leave drag trails.
        scale = abs(painter.worldTransform().m11()) or 1.0
        inset = min(
            (width / 2.0) / scale,
            min(self.width, self.height) / 2.0,
        )
        rect = QRectF(
            -1.0 + inset,
            -1.0 + inset,
            self.width + 2.0 - 2.0 * inset,
            self.height + 2.0 - 2.0 * inset,
        )
        radius = min(self.edge_roundness, rect.width() / 2.0, rect.height() / 2.0)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(pen)
        painter.drawPath(path.simplified())
        painter.restore()

    def setDetailState(self, state: Mapping[str, bool]) -> None:
        """Keep the status badge under the user's own control.

        The scene resolves the detail policy into one on/off map per element
        and hands it to every node. The card, the label and the sockets are
        the library's own; the status badge is painted here, so this node
        picks its flag out of the same map.
        """
        self._badge_visible = bool(state.get("badge", True))
        super().setDetailState(state)

    def setPenExecuting(self) -> None:
        """Set node border to the running-state token while executing"""
        self._pen_role = "executing"
        self._pen = self._executing_pen
        self.update()

    def setPenExecuted(self) -> None:
        """Set node border to the success token after execution"""
        self._pen_role = "executed"
        self._pen = self._executed_pen
        self.update()

    def setPenError(self) -> None:
        """Set node border to the danger token on execution error"""
        self._pen_role = "error"
        self._pen = self._error_pen
        self.update()

    def resetPen(self) -> None:
        """Reset to default (invisible) border"""
        self._pen_role = "default"
        self._pen = self._default_pen
        self.update()
