from collections.abc import Mapping

from qtpy.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from qtpy.QtWidgets import (
    QScrollArea,
    QWidget,
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QLayout,
)
from qtpy.QtCore import QRectF, Qt
from qtpy.QtWidgets import (
    QLabel,
)

from nodeeditor.node_node import Node

from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.node_icon_graphics_node import QDMIconGraphicsNode
from nodeeditor.node_socket import Socket
from nodeeditor.node_edge import Edge

from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER
from nodeeditor.utils import dumpException

from trigger_designer.core.errors import (
    ErrorContext,
    NodeError,
    make_error,
    translate_exception,
)
from trigger_designer.core.frames import frame_schema as frame_schema
from trigger_designer.core.frames import frame_shape as frame_shape
from trigger_designer.qt.helpers.rename_map import (
    upstream_rename_map as upstream_rename_map,
)
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.theme_manager import get_theme_manager
from trigger_designer.qt.helpers.eval_progress import (
    count_pending_recomputes,
    eval_progress_dialog,
)
from trigger_designer.qt.helpers.content_undo_mixin import (
    _COMPOSITE_ATTR,
    _IMMEDIATE_WIDGET_TYPES,
    _TRACKED_ATTR,
    _UNTRACKED,
    TriggerContentUndoMixin,
    default_history_text,
    widget_accepts_tracking,
)
from trigger_designer.qt.undo.binding import (
    _BOUND_ATTR,
    DEFAULT_DEBOUNCE_MS,
    bind,
    is_missing,
    safe_value_of,
    unbind,
)

from typing import TYPE_CHECKING, Any, List, Optional, OrderedDict

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene

from loguru import logger


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
        """The body, the status badge that hangs below it, and the state ring.

        Two things ``paint`` draws reach outside the body: the badge is centred
        on the bottom edge, so half of it is below, and the state ring strokes
        the body path with a 5px pen, so half of it is outside every edge. A
        ``boundingRect`` that stopped at the body was smaller than what the item
        drew; Qt repaints by the declared rectangle, so what fell outside was
        never cleared and every frame of a drag left another copy behind - the
        trail of green check badges and ring fragments under a dragged node.
        """
        if self._bounding_rect is None:
            margin = self.RING_PEN_WIDTH / 2.0 + 1.0
            rect = self.bodyRect().united(self.statusBadgeRect())
            self._bounding_rect = rect.adjusted(-margin, -margin, margin, margin)
        return self._bounding_rect

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
        else:
            # Draw node content
            super().paint(painter, option, widget)

        # The status badge is drawn on top of either, so it can outlive the
        # card and still tell a finished node from a broken one.
        if getattr(self, "_badge_visible", True):
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

        # The error badge is independent of the status badge: a hidden status
        # badge must not hide the reason the node failed.
        self._paint_error_badge(painter)

    def errorBadgeRect(self) -> QRectF:
        side = 14.0
        return QRectF(self.width - 19.0, 5.0, side, side)

    def set_error_badge(self, severity: str) -> None:
        value = severity if severity in {"error", "warning"} else ""
        if value == self._error_badge:
            return
        self._error_badge = value
        self.update()

    def _paint_error_badge(self, painter: QPainter) -> None:
        if not self._error_badge:
            return
        manager = get_theme_manager()
        token = "danger" if self._error_badge == "error" else "warning"
        fallback = "#e0686c" if token == "danger" else "#d9a441"
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(manager.color(token, fallback)))
        rect = self.errorBadgeRect()
        painter.drawEllipse(rect)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QPen(QColor(manager.color("text_on_accent", "#ffffff"))))
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


class TriggerContent(TriggerContentUndoMixin, QDMNodeIconContentWidget):
    """Base for node content widgets.

    :class:`TriggerContentUndoMixin` supplies the undo protocol methods, so
    every node can be restored without writing per-node bookkeeping. It is
    listed *before* the Qt base deliberately: ``QDMNodeContentWidget`` defines
    a no-op ``history_stamp_callback``, and a Qt base listed first would win
    the MRO and silently disable the real one.
    """

    # _node: 'TriggerNode'  # Define the actual storage

    def initUI(self, icon: Optional[QPixmap] = None) -> Any:
        #: Recorded here as well as in the base: nodes that build on
        #: ``TriggerContent`` override the base's ``initUI``, and the low-zoom
        #: repaint blits this pixmap instead of rendering the widget.
        self.icon = icon
        lbl = QLabel(self.node.content_label, self)  # type: ignore
        lbl.setObjectName(self.node.content_label_objname)  # type: ignore


class TriggerChangeHandler(TriggerContentUndoMixin):
    """Wires a node's Config Dock widgets into the undo system.

    Also the carrier for :class:`TriggerContentUndoMixin`: every content class
    inherits this, and the mixin supplies ``sync_from_model``,
    ``history_stamp_callback`` and the ``push_*_change`` helpers. Keeping that
    on this base means new nodes get undo support without opting in.

    The Config Dock builds a node's widgets from scratch on every selection,
    so registrations here are re-made constantly and die with their widgets.
    There is nothing to tear down.
    """

    def __init__(self, scene: "Scene", node: "TriggerNode") -> None:
        self._scene = scene
        self._input_widgets_store: list = []
        self._suspend_input_tracking = False
        self.node = node

    @property
    def _input_widgets(self) -> list:
        """Widgets registered for change tracking.

        Lazy rather than set in ``__init__`` because not every content class
        cooperates with cooperative ``super().__init__()`` - several build on
        ``(QDMNodeIconContentWidget, TriggerChangeHandler)`` and override
        ``__init__`` without chaining, so attributes set here never run.
        Reading a plain attribute then raised ``AttributeError`` from inside
        ``create_layout``, which ``ConfigDock`` catches broadly, leaving that
        node's config panel silently blank.
        """
        store = self.__dict__.get("_input_widgets_store")
        if store is None:
            store = []
            self.__dict__["_input_widgets_store"] = store
        return store

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def refresh_dock_context(self) -> None:
        """Recompute the open dock's context strip from the model.

        The strip is a projection, like every other widget: the dock installs
        ``_dock_context_refresh`` while it owns this node's layout, and this is
        a no-op once the dock is gone or the node is destroyed.
        """
        # ``__dict__`` rather than ``getattr``: on a widget whose C++ init never
        # ran (a ``__new__``-built content in tests) or one already deleted,
        # PyQt's attribute lookup itself raises RuntimeError, outside any
        # default the two-argument form could fall back to.
        try:
            callback = self.__dict__.get("_dock_context_refresh")
        except RuntimeError:
            return
        if callback is None:
            return
        try:
            callback()
        except RuntimeError:
            # Widget already deleted (dock rebuilt or node removed).
            pass

    def registerInputWidget(
        self,
        widget: QWidget,
        text: Optional[str] = None,
        immediate: Optional[bool] = None,
        debounce_ms: Optional[int] = None,
        merge_key: Optional[str] = None,
    ) -> bool:
        """Make edits to ``widget`` undoable.

        Each widget is seeded with its current value, so the first edit records
        a genuine before/after pair rather than an entry with nothing to
        return to.

        :param text: ``"Noun Verbed"`` label for the history entry. Defaults to
            ``Modified <Node Title>``, which at least names the node.
        :param immediate: commit on every change instead of debouncing.
            Defaults to ``True`` for buttons, spins, sliders and combos, which
            have no intermediate states worth keeping.
        :param debounce_ms: override the pause before committing.
        :param merge_key: fold a burst of edits into one undo step. Give each
            control its own key.
        """
        if widget in self._input_widgets:
            return False

        seed = safe_value_of(widget)
        if is_missing(seed):
            # Cannot read a starting value for this control, so a real diff is
            # impossible. Skipping keeps it untracked rather than letting the
            # failure escape create_layout and blank the node's whole panel.
            logger.debug(
                f"Skipping undo tracking for {type(widget).__name__}: unreadable value"
            )
            return False

        tracked = self._tracked_values()
        key = id(widget)
        if debounce_ms is None:
            debounce_ms = DEFAULT_DEBOUNCE_MS if immediate is None else None
        if immediate is None:
            immediate = isinstance(widget, _IMMEDIATE_WIDGET_TYPES)

        label = text or default_history_text(self.node)
        tracked[key] = seed

        connected = bind(
            self,
            widget,
            read=lambda k=key: tracked.get(k, _UNTRACKED),
            write=None,  # the node's own slot already mutated the model
            text=label,
            immediate=bool(immediate),
            debounce_ms=debounce_ms,
            merge_key=merge_key,
        )
        if connected:
            self._input_widgets.append(widget)
        return connected

    def _tracked_values(self) -> dict:
        """Per-content map of last recorded widget values."""
        tracked = getattr(self, _TRACKED_ATTR, None)
        if tracked is None:
            tracked = {}
            setattr(self, _TRACKED_ATTR, tracked)
        return tracked

    def is_input_widget(self, widget: QWidget) -> bool:
        """Check if a widget is an input widget we track."""
        return widget_accepts_tracking(widget)

    def iter_dock_widgets(self, layout: Optional[QLayout]):
        """Yield every widget in a layout tree, depth first.

        Descends into a scroll area's ``widget()`` as well as nested layouts.
        Several nodes wrap their whole panel in a ``QScrollArea``, whose
        children live under ``scrollArea.widget()`` and are not reachable from
        any layout on the dock - without this their controls are invisible to
        the registration sweep and stay untracked.
        """
        if layout is None:
            return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                yield widget
                yield from self.iter_dock_widgets(widget.layout())
                inner = self._scroll_content(widget)
                if inner is not None:
                    yield inner
                    yield from self.iter_dock_widgets(inner.layout())
            elif item.layout() is not None:
                yield from self.iter_dock_widgets(item.layout())

    @staticmethod
    def _scroll_content(widget: QWidget) -> Optional[QWidget]:
        """The content widget of a scroll area, or ``None``.

        Deliberately ``QScrollArea`` and not ``QAbstractScrollArea``: the
        ``widget()`` accessor only exists on the former, and the latter is also
        the base of ``QTextEdit`` and ``QTableView``, which have no content
        widget to descend into.
        """
        if isinstance(widget, QScrollArea):
            return widget.widget()
        return None

    def registerUnboundDockWidgets(self, layout: Optional[QLayout]) -> int:
        """Register any control the node did not register itself.

        Run by ``ConfigDock`` after ``create_layout`` so *every* Config Dock
        control is undoable by default, including in nodes that never opted
        in. Without this a node with no explicit registration - cleansing,
        groupby, count_records, graph, dynamic_row_builder - silently had no
        undo path at all.

        Widgets already bound are skipped, so a node that registered a
        control with a specific ``"Noun Verbed"`` label keeps that label and
        this sweep only picks up the ones it missed. Anything nested inside a
        composite is skipped too, because the composite owns its own signal
        and binding its children as well would record the same edit twice.
        """
        added = 0
        for widget in self.iter_dock_widgets(layout):
            if not widget_accepts_tracking(widget):
                continue
            if getattr(widget, _BOUND_ATTR, False):
                continue
            if self._inside_composite(widget):
                continue
            if self.registerInputWidget(widget):
                added += 1
        return added

    @staticmethod
    def _inside_composite(widget: QWidget) -> bool:
        """``True`` if ``widget`` is part of a composite that owns its signal."""
        parent = widget.parent()
        while parent is not None:
            if getattr(parent, _COMPOSITE_ATTR, False):
                return True
            parent = parent.parent()
        return False

    def recursively_find_widgets(self, layout: Optional[QLayout]) -> None:
        """Register every trackable widget in a layout tree.

        Cheap enough to call unconditionally at the end of ``create_layout``.
        """
        for widget in self.iter_dock_widgets(layout):
            if widget_accepts_tracking(widget):
                self.registerInputWidget(widget)

    def onInputChanged(self, *args: list) -> None:
        """Fallback for widgets with no specific model binding.

        Bound via :meth:`registerInputWidget` only where a node has not given
        a control an explicit label. Records a real diff against the last
        known value rather than an unconditional "Input Modified", and honours
        the debounce and the restore guard, so it can no longer flood the
        timeline or re-record its own restore.
        """
        del args
        if self._suspend_input_tracking:
            return

        scene = getattr(self.node, "scene", None)
        if scene is None:
            return
        history = getattr(scene, "history", None)
        if history is None or history.is_restoring_history:
            return

        scene.has_been_modified = True
        history.storeHistory(default_history_text(self.node), setModified=False)

    def _disconnect_input_widget(self, widget: QWidget) -> None:
        try:
            unbind(widget)
        except RuntimeError:
            return

    def clearInputWidgets(self) -> None:
        """Drop tracked widgets and their pending debounces.

        Nodes that manage their own commit timing - the formula editor, for
        one - call this so the generic tracker does not also record their
        edits.
        """
        for widget in self._input_widgets:
            self._disconnect_input_widget(widget)
        self._input_widgets.clear()
        self._tracked_values().clear()


class TriggerNode(Node):
    icon: str = ""
    node_code: int = 0
    node_title: str = "Undefined"
    node_type: str = ""
    content_label: str = ""
    content_label_objname: str = "calc_node_bg"
    style: dict[str, str] = {"brush_color": "#000000"}
    #: Input indexes that may stay unconnected; processInputs receives None.
    optional_inputs: frozenset = frozenset()

    # Explicitly define types for Node classes
    GraphicsNode_class: TriggerGraphicsNode = TriggerGraphicsNode  # type: ignore
    NodeContent_class: TriggerContent = TriggerContent  # type: ignore
    rsm: ResourceManager = ResourceManager()

    # evaluationRequested = Signal()

    @staticmethod
    def _normalize_socket_text(labels: List[str]) -> List[str]:
        """Render socket labels as a single capitalized character."""
        normalized_labels: List[str] = []
        for label in labels:
            if isinstance(label, str) and label:
                normalized_labels.append(label[0].upper())
            else:
                normalized_labels.append(label)
        return normalized_labels

    #: Set while this node is inside ``evalImplementation``. A push from one
    #: branch of a diamond reaches the shared join while that join is already
    #: computing; without the guard the join recomputes once per branch.
    _evaluating: bool = False

    def __init__(
        self,
        scene: "Scene",
        inputs: List[int] = [2, 2],
        outputs: List[int] = [1],
        input_text: List[str] = [],
        output_text: List[str] = [],
    ) -> None:
        # Subclasses (e.g. File Input) call eval() immediately after super(),
        # and a constructor-time exception must never leave the guard stuck.
        self._evaluating = False
        super().__init__(
            scene,
            self.__class__.node_title,
            inputs,
            outputs,
            input_text,
            self._normalize_socket_text(output_text),
        )

        self.value: Optional[Any] = None
        self.param: list = []

        # it's really important to mark all nodes Dirty by default
        self.markDirty()

    def initSettings(self) -> None:
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER
        # self.evaluationRequested.connect(self.onInputChanged)

    def setPos(self, x: float, y: float) -> None:
        if getattr(self.scene, "_bulk_loading", False):
            self.grNode.setPos(x, y)
            return

        super().setPos(x, y)

    def getSocketValue(
        self, socket_list: list["Socket"], target_node: "TriggerNode"
    ) -> int:
        """Get value based on socket connection"""
        for i, socket in enumerate(socket_list):
            if socket.edges:
                for edge in list(socket.edges):
                    other_socket = self._get_connected_socket(socket, edge)
                    if other_socket is None:
                        continue
                    if other_socket.node == target_node:
                        return i
        raise ValueError(
            f"No edge from {self.__class__.__name__} reaches "
            f"{target_node.__class__.__name__}"
        )

    def _get_connected_socket(
        self, socket: "Socket", edge: "Edge"
    ) -> Optional["Socket"]:
        if edge.start_socket is not socket and edge.end_socket is not socket:
            socket.removeEdge(edge)
            logger.warning(
                f"Removed stale edge reference from socket {socket.id} on {self.__class__.__name__}"
            )
            return None

        other_socket = edge.getOtherSocket(socket)
        if other_socket is None or getattr(other_socket, "node", None) is None:
            try:
                edge.remove(silent=True)
            except Exception as exc:
                dumpException(exc)
            logger.warning(
                f"Removed dangling edge while traversing {self.__class__.__name__}"
            )
            return None

        return other_socket

    def getChildrenNodes(self) -> list["Node"]:
        if self.outputs == []:
            return []

        other_nodes = []
        for socket in self.outputs:
            for edge in list(socket.edges):
                other_socket = self._get_connected_socket(socket, edge)
                if other_socket is None:
                    continue
                other_nodes.append(other_socket.node)
        return other_nodes

    def _refresh_selected_node_config(self) -> None:
        if getattr(self, "grNode", None) is None or not self.grNode.isSelected():
            return

        view = self.scene.getView() if hasattr(self.scene, "getView") else None
        owner = view.parentWidget() if view is not None else None

        while owner is not None and not hasattr(owner, "refreshConfigDock"):
            owner = owner.parentWidget()

        refresher = getattr(owner, "refreshConfigDock", None)
        if callable(refresher):
            refresher([self.grNode])

    def _set_node_tooltip(self, text: str) -> None:
        """Set the canvas tooltip, tolerating a missing graphics node.

        During file load / deserialization, eval can run on a node whose
        inputs are not wired yet and whose ``grNode`` is still ``None``.
        A routine "not connected yet" must not become an AttributeError -
        and the ``eval()`` handlers below must not crash while handling it.
        """
        gr = getattr(self, "grNode", None)
        if gr is None:
            return
        try:
            gr.setToolTip(text)
        except RuntimeError:
            pass

    def _node_tooltip(self) -> str:
        gr = getattr(self, "grNode", None)
        if gr is None:
            return ""
        try:
            return gr.toolTip() or ""
        except RuntimeError:
            return ""

    # -- structured error state -------------------------------------------
    _errors_by_source: dict[str, NodeError] | None = None

    def _errors_dict(self) -> dict[str, NodeError]:
        if self._errors_by_source is None:
            self._errors_by_source = {}
        return self._errors_by_source

    @property
    def current_error(self) -> NodeError | None:
        store = self._errors_dict()
        return store.get("run") or store.get("live")

    def set_error(self, error: NodeError, source: str = "live") -> None:
        store = self._errors_dict()
        old = store.get(source)
        store[source] = error
        self._apply_error_state()
        if old is None or old.fingerprint != error.fingerprint:
            self._log_new_error(error)
        problems = self._problems_store()
        if problems is not None and not (error.knock_on and source == "live"):
            problems.upsert(error, source)

    def clear_error(
        self, source: str | None = None, *, _seen: set[int] | None = None
    ) -> None:
        seen = set() if _seen is None else _seen
        if id(self) in seen:
            return
        seen.add(id(self))
        store = self._errors_dict()
        if source is None:
            removed = list(store)
            store.clear()
        else:
            removed = [source] if store.pop(source, None) is not None else []
        self._apply_error_state()
        problems = self._problems_store()
        if problems is not None:
            for item in removed:
                problems.remove(self.id, item)
        if source in (None, "run"):
            for child in self.getChildrenNodes():
                current = getattr(child, "current_error", None)
                if current is not None and current.knock_on:
                    child.clear_error("run", _seen=seen)

    def _apply_error_state(self) -> None:
        error = self.current_error
        self._set_node_tooltip(error.render_tooltip() if error else "")
        gr = getattr(self, "grNode", None)
        if gr is not None:
            try:
                gr.set_error_badge(error.severity if error else "")
            except RuntimeError:
                pass

    def _problems_store(self):
        try:
            view = self.scene.getView() if hasattr(self.scene, "getView") else None
        except (IndexError, RuntimeError, AttributeError):
            view = None
        owner = view.parentWidget() if view is not None else None
        while owner is not None and not hasattr(owner, "problems"):
            owner = owner.parentWidget()
        return getattr(owner, "problems", None)

    def _log_new_error(self, error: NodeError) -> None:
        try:
            logger.error(error.render_text(include_technical=True))
        except Exception:  # noqa: BLE001, S110 - logging must never break eval
            pass
        try:
            from trigger_designer.qt.helpers import global_logger

            global_logger.error(error.render_summary())
        except Exception:  # noqa: BLE001, S110 - dock may not exist in tests
            pass

    def evalOperation(self, input1: Any, input2: Any) -> int:
        return 123

    def processInputs(self, input_values: list[Any]) -> Optional[Any]:
        # Override this method in subclasses to process the input values
        return input_values

    def evalChildren(self) -> None:
        # During file load/restore the scene walks every node; eager push
        # evaluation reaches joins before their other parents have settled,
        # causing repeated invalid/partial recomputes. Pulls from inputs
        # still run as usual; ordinary interactive edits keep push semantics.
        if getattr(self.scene, "_batch_evaluating", False):
            return
        super().evalChildren()

    def evalImplementation(self) -> Any:
        input_values = []
        for i in range(len(self.inputs)):
            input_node = self.getInput(i)
            if not input_node:
                if i in self.optional_inputs:
                    input_values.append(None)
                    continue
                self.markInvalid()
                self.markDescendantsDirty()
                self.set_error(
                    make_error(
                        "TD-RUN-005",
                        ErrorContext.from_node(self, "live"),
                        input_number=i + 1,
                    ),
                    "live",
                )
                self._refresh_selected_node_config()
                return None

            val = input_node.eval()
            if val is None:
                self.markInvalid()
                self.markDescendantsDirty()
                upstream = ErrorContext.from_node(input_node, "live")
                self.set_error(
                    make_error(
                        "TD-RUN-003",
                        ErrorContext.from_node(self, "live"),
                        culprit_label=upstream.node_label,
                        culprit_node_id=getattr(input_node, "id", None),
                        culprit_node_title=upstream.node_label,
                    ),
                    "live",
                )
                self._refresh_selected_node_config()
                return None

            input_values.append(val)

        result = self.processInputs(input_values)
        if result is None:
            self.markInvalid()
            self.markDescendantsDirty()
            if self.current_error is None:
                message = self._node_tooltip() or "Invalid operation"
                self.set_error(
                    make_error(
                        "TD-SYS-001",
                        ErrorContext.from_node(self, "live"),
                        message=message,
                    ),
                    "live",
                )
            self._refresh_selected_node_config()
            return None

        self.value = result
        self.markInvalid(False)
        self.markDirty(False)
        self.clear_error("live")
        self.evalChildren()
        self._refresh_selected_node_config()
        return self.value

    # Uncomment if you want to use the default evalImplementation for calculator application
    # def evalImplementation(self):
    #     i1 = self.getInput(0)
    #     i2 = self.getInput(1)

    #     if i1 is None or i2 is None:
    #         self.markInvalid()
    #         self.markDescendantsDirty()
    #         self.grNode.setToolTip("Connect all inputs")
    #         return None

    #     else:
    #         val = self.evalOperation(i1.eval(), i2.eval())
    #         self.value = val
    #         self.markDirty(False)
    #         self.markInvalid(False)
    #         self.grNode.setToolTip("")

    #         self.markDescendantsDirty()
    #         self.evalChildren()

    #         return val

    def eval(self, index: Any = None) -> Any:
        scene = getattr(self, "scene", None)
        if scene is not None and getattr(scene, "_bulk_loading", False):
            # A node constructed mid-load has no file path or column config
            # yet, so a constructor-time eval would compute from empty inputs
            # and be recomputed anyway once deserialization finishes. Leave it
            # dirty; doEvalOutputs runs the single post-load pass.
            return self.value
        if self._evaluating:
            # A sibling branch pushed into this node while it was still
            # computing. The computation in progress will commit the complete
            # result and push again; recomputing here only repeats work.
            return self.value

        coordinator = getattr(scene, "evaluator", None)
        if coordinator is not None:
            coordinator.flush_now()  # a pending edge edit is newer than us

        if not self.isDirty() and not self.isInvalid():
            logger.debug(" _> returning cached {} value:", self.__class__.__name__)
            return self.value

        self._evaluating = True
        if scene is not None:
            scene._eval_depth = getattr(scene, "_eval_depth", 0) + 1
        try:
            try:
                self._report_eval_progress(finished=False)
            except Exception:  # noqa: BLE001 - UI listener must not break eval
                logger.exception("Evaluation progress callback failed")
            return self.evalImplementation()
        except ValueError as e:
            self.markInvalid()
            self.set_error(translate_exception(e, node=self, phase="live"), "live")
            self.markDescendantsDirty()
        except Exception as e:
            self.markInvalid()
            self.set_error(translate_exception(e, node=self, phase="live"), "live")
            dumpException(e)
            return None  # Add explicit return for exception case
        finally:
            # Clear the guard and depth before notifying listeners: a listener
            # that calls eval() must see a settled node, not a reentrant one.
            self._evaluating = False
            if scene is not None:
                scene._eval_depth = max(0, getattr(scene, "_eval_depth", 1) - 1)
            try:
                self._report_eval_progress(finished=True)
            except Exception:  # noqa: BLE001 - UI listener must not break eval
                logger.exception("Evaluation progress callback failed")
            # Scene-level notification so preview surfaces can follow a real
            # recompute; cached evaluations returned above. ``Scene`` is not a
            # QObject, so TriggerScene fans this out to its own listeners.
            try:
                notify = getattr(scene, "notifyNodeEvaluated", None)
                if callable(notify):
                    notify(self)
            except Exception:  # noqa: BLE001 - UI listener must not break eval
                logger.exception("Node evaluated listener failed")
            if scene is not None and getattr(scene, "_eval_depth", 0) == 0:
                coordinator = getattr(scene, "evaluator", None)
                if coordinator is not None:
                    coordinator.flush_now()

    def _report_eval_progress(self, finished: bool) -> None:
        """Notify the active progress dialog, if any (helpers/eval_progress.py).

        Called before and after a real recompute only - a cache hit returns
        above before this - so the dialog can name the node about to run and
        repaint before a slow step blocks the thread.
        """
        scene = getattr(self, "scene", None)
        callback = (
            getattr(scene, "_eval_progress_cb", None) if scene is not None else None
        )
        if callable(callback):
            callback(self, finished)

    def onEdgeConnectionChanged(self, new_edge: "Edge") -> None:
        # print("%s::__onEdgeConnectionChanged" % self.__class__.__name__)
        self.clear_error("run")
        self.markDirty()
        self.markDescendantsDirty()
        self.eval()

    def onInputChanged(self, socket: Optional["Socket"] = None) -> None:
        content = getattr(self, "content", None)
        if getattr(content, "_suspend_node_evaluation", False):
            return

        self.clear_error("run")
        self.markDirty()
        self.markDescendantsDirty()
        self.eval()

    def serialize(self) -> OrderedDict:
        res = super().serialize()
        res["node_code"] = self.__class__.node_code
        res["node_type"] = self.__class__.node_type
        # Stable identity: "<family>.<NAME>" from enum member names, so
        # renumbering/reordering members never breaks saved files.
        # The loader prefers "op" and only falls back to node_code ints
        # for pre-v2 files.
        try:
            res["op"] = (
                f"{self.__class__.node_type.value}"
                f".{self.__class__.node_code.name.lower()}"
            )
        except AttributeError:
            res["op"] = "unknown.unknown"
        return res

    def deserialize(
        self, data: dict, hashmap: dict = {}, restore_id: bool = True
    ) -> bool:
        res = super().deserialize(data, hashmap, restore_id)
        # print("Deserialized CalcNode '%s'" %
        #       self.__class__.__name__, "res:", res)
        # The file carries the title it was saved with, so a node type that has
        # since been renamed would come back under its old name. The class owns
        # the current name (TriggerNode_Unknown keeps the saved one instead).
        self.title = self.__class__.node_title
        return res

    def get_code(self) -> str:
        """
        Meant to be overridden in subclasses to provide the code for the node.
        """
        return ""
