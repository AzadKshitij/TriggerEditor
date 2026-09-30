from qtpy.QtGui import QPixmap, QColor, QPen, QPainter
from qtpy.QtWidgets import (
    QScrollArea,
    QWidget,
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QLayout,
)
from qtpy.QtCore import QRectF
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

from trigger_designer.qt.resource_manager import ResourceManager
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
import polars as pl


def frame_schema(frame) -> dict:
    """Column names and dtypes without collecting (lazy-safe).

    Live data may be a LazyFrame (e.g. downstream of Append/Join) — use
    this anywhere only names/types are needed instead of `.columns`/`.dtype`.
    """
    # ponytail: one shared helper, not per-node isinstance blocks
    if frame is None:
        return {}
    if isinstance(frame, pl.LazyFrame):
        schema = frame.collect_schema()
    else:
        schema = frame.schema
    return {name: dtype for name, dtype in schema.items()}


def frame_shape(frame) -> tuple:
    """(height, width) for logs; height is "lazy" without collecting."""
    width = len(frame_schema(frame))
    if isinstance(frame, pl.LazyFrame):
        return ("lazy", width)
    try:
        return (frame.height, width)
    except Exception:
        return ("?", width)


def upstream_rename_map(upstream_node) -> dict:
    """Column renames advertised by an upstream node (``{old: new}``).

    Lets a downstream node follow a rename instead of treating it as a
    drop + add: a config referencing ``old`` can be remapped to ``new``
    when ``new`` is present in the live upstream schema. Nodes that do
    not rename report ``{}``.
    """
    content = getattr(upstream_node, "content", None)
    if content is None:
        return {}
    # Select stores its renames in ``changes["rename_mapping"]``.
    changes = getattr(content, "changes", None)
    if isinstance(changes, dict):
        mapping = changes.get("rename_mapping")
        if isinstance(mapping, dict):
            return {str(old): str(new) for old, new in mapping.items() if new}
    # Normalize Columns derives its mapping from its rules.
    current_mapping = getattr(content, "_current_mapping", None)
    if callable(current_mapping):
        try:
            mapping = current_mapping()
        except Exception:  # noqa: BLE001 - any upstream error means no map
            return {}
        if isinstance(mapping, dict):
            return {str(old): str(new) for old, new in mapping.items() if new}
    return {}


class TriggerGraphicsNode(QDMIconGraphicsNode):
    # Add signal for evaluation requests

    rsm = ResourceManager()

    def __init__(
        self, node: "TriggerNode", parent: Optional[QGraphicsItem] = None
    ) -> None:
        super().__init__(node, parent)

        self._default_pen = QPen(QColor.fromRgb(0, 0, 0, 0))  # Black color
        self._default_pen.setWidth(5)
        self._selected_pen = QPen(QColor("#FFFFA637"))
        self._selected_pen.setWidth(5)
        self._executing_pen = QPen(QColor("#FF800080"))  # Purple color
        self._executing_pen.setWidth(5)
        self._executed_pen = QPen(QColor("#FF008000"))  # Green color
        self._executed_pen.setWidth(5)
        self._error_pen = QPen(QColor("#FFFF0000"))  # Red color
        self._error_pen.setWidth(5)

        self._pen = self._default_pen  # Current pen
        # self._brush_title = QBrush(QColor(style['brush_color']))

    def initSizes(self) -> None:
        super().initSizes()
        self.width = 120
        self.height = 120
        self.edge_roundness = 6
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10

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

        # Draw the border first
        path_outline = self.shape()  # Get the shape path
        painter.setPen(self._pen)
        painter.drawPath(path_outline)

        # Draw node content
        super().paint(painter, option, widget)

        offset = 24.0
        if self.node.isDirty():
            offset = 0.0
        if self.node.isInvalid():
            offset = 48.0

        # Calculate the position for bottom center
        icon_width = 24.0
        icon_x = (self.width - icon_width) / 2
        icon_y = self.height - 12  # 5 pixels padding from the bottom

        painter.drawImage(
            QRectF(icon_x, icon_y, 24.0, 24.0),
            self.icons,
            QRectF(offset, 0, 24.0, 24.0),
        )

    def setPenExecuting(self) -> None:
        """Set node border to purple while executing"""
        self._pen = self._executing_pen
        self.update()

    def setPenExecuted(self) -> None:
        """Set node border to green after execution"""
        self._pen = self._executed_pen
        self.update()

    def setPenError(self) -> None:
        """Set node border to red on execution error"""
        self._pen = self._error_pen
        self.update()

    def resetPen(self) -> None:
        """Reset to default border color"""
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

    def __init__(
        self,
        scene: "Scene",
        inputs: List[int] = [2, 2],
        outputs: List[int] = [1],
        input_text: List[str] = [],
        output_text: List[str] = [],
    ) -> None:
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
                self.markInvalid()
                self.markDescendantsDirty()
                self._set_node_tooltip(f"Input {i} is not connected")
                self._refresh_selected_node_config()
                return None

            val = input_node.eval()
            if val is None:
                self.markInvalid()
                self.markDescendantsDirty()
                self._set_node_tooltip(f"Input {i}: upstream node produced no output")
                self._refresh_selected_node_config()
                return None

            input_values.append(val)

        result = self.processInputs(input_values)
        if result is None:
            self.markInvalid()
            self.markDescendantsDirty()
            if not self._node_tooltip():
                self._set_node_tooltip("Invalid operation")
            self._refresh_selected_node_config()
            return None

        self.value = result
        self.markInvalid(False)
        self.markDirty(False)
        self._set_node_tooltip("")
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
        if not self.isDirty() and not self.isInvalid():
            logger.debug(" _> returning cached {} value:", self.__class__.__name__)
            return self.value
        self._report_eval_progress(finished=False)
        try:
            val = self.evalImplementation()
            return val
        except ValueError as e:
            self.markInvalid()
            self._set_node_tooltip(str(e))
            self.markDescendantsDirty()
        except Exception as e:
            self.markInvalid()
            self._set_node_tooltip(str(e))
            dumpException(e)
            return None  # Add explicit return for exception case
        finally:
            self._report_eval_progress(finished=True)

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
        self.markDirty()
        self.markDescendantsDirty()
        self.eval()

    def onInputChanged(self, socket: Optional["Socket"] = None) -> None:
        content = getattr(self, "content", None)
        if getattr(content, "_suspend_node_evaluation", False):
            return

        self.markDirty()
        self.markDescendantsDirty()

        total = count_pending_recomputes(self)
        view = self.scene.getView() if hasattr(self.scene, "getView") else None
        parent = view.window() if view is not None else None
        with eval_progress_dialog(self.scene, parent, total, "Updating workflow…"):
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
        return res

    def get_code(self) -> str:
        """
        Meant to be overridden in subclasses to provide the code for the node.
        """
        return ""
