"""The node base class.

``TriggerNode`` is identity, sockets, persistence and code generation. The
rest lives in focused modules and is re-exported here, so every historical
``from trigger_designer.qt.node_base import ...`` keeps working:

* evaluation and errors: ``qt/node_runtime`` (``NodeEvaluator``, ``NodeErrorState``)
* content widgets and undo binding: ``qt/node_content``
* painting: ``qt/node_graphics``
* frame and rename helpers: ``core/frames``, ``qt/helpers/rename_map``
"""

from typing import TYPE_CHECKING, Any, List, Optional, OrderedDict

from loguru import logger
from nodeeditor.node_node import Node
from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER
from nodeeditor.utils import dumpException

from trigger_designer.core.errors import NodeError
from trigger_designer.core.frames import frame_schema as frame_schema
from trigger_designer.core.frames import frame_shape as frame_shape
from trigger_designer.qt.helpers.rename_map import (
    upstream_rename_map as upstream_rename_map,
)
from trigger_designer.qt.node_content import (
    ConfigContent as ConfigContent,
    DockBinding as DockBinding,
    TriggerChangeHandler as TriggerChangeHandler,
    TriggerContent as TriggerContent,
)
from trigger_designer.qt.node_graphics import (
    TriggerGraphicsNode as TriggerGraphicsNode,
)
from trigger_designer.qt.node_runtime import NodeErrorState, NodeEvaluator
from trigger_designer.qt.resource_manager import ResourceManager

if TYPE_CHECKING:
    from nodeeditor.node_edge import Edge
    from nodeeditor.node_scene import Scene
    from nodeeditor.node_socket import Socket


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

    def setPos(self, x: float, y: float) -> None:
        if getattr(self.scene, "_bulk_loading", False):
            self.grNode.setPos(x, y)
            return

        super().setPos(x, y)

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

    # -- structured error state (see NodeErrorState in node_runtime) --------
    @property
    def errors(self) -> NodeErrorState:
        """Created on first use, so a subclass that touches errors before
        ``super().__init__`` finishes still works."""
        state = self.__dict__.get("_error_state")
        if state is None:
            state = NodeErrorState(self)
            self.__dict__["_error_state"] = state
        return state

    def _errors_dict(self) -> dict[str, NodeError]:
        return self.errors.by_source

    @property
    def current_error(self) -> NodeError | None:
        return self.errors.current

    def set_error(self, error: NodeError, source: str = "live") -> None:
        self.errors.set(error, source)

    def clear_error(
        self, source: str | None = None, *, _seen: set[int] | None = None
    ) -> None:
        self.errors.clear(source, _seen=_seen)

    def set_changes_pending(self, pending: bool) -> None:
        """Show (or clear) the yellow "!" for edits that have not run yet."""
        self.errors.set_changes_pending(pending)

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

    @property
    def evaluator(self) -> NodeEvaluator:
        """Created on first use, like :attr:`errors`."""
        runner = self.__dict__.get("_node_evaluator")
        if runner is None:
            runner = NodeEvaluator(self)
            self.__dict__["_node_evaluator"] = runner
        return runner

    def evalImplementation(self) -> Any:
        return self.evaluator.run_base_implementation()

    def eval(self, index: Any = None) -> Any:
        return self.evaluator.evaluate()

    def onEdgeConnectionChanged(self, new_edge: "Edge") -> None:
        self.evaluator.on_edge_connection_changed(new_edge)

    def onInputChanged(self, socket: Optional["Socket"] = None) -> None:
        self.evaluator.on_input_changed(socket)

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
