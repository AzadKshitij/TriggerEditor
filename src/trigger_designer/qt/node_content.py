"""Node content bases and the Config Dock undo binding.

``DockBinding`` is the one object that wires a content widget's Config Dock
controls into the undo system: registration, layout traversal, tracked values
and teardown. :class:`TriggerChangeHandler` keeps the historical mixin surface
(``registerInputWidget`` and friends) as thin delegations, so every content
class that already inherits it keeps working unchanged.

This module never imports ``node_base``; ``TriggerNode`` is only a type here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from qtpy.QtCore import Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QLabel, QLayout, QScrollArea, QWidget

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

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene

    from trigger_designer.qt.node_base import TriggerNode

#: Where a content widget keeps its binding. Looked up through ``__dict__`` so
#: it works on a content class that never ran ``TriggerChangeHandler.__init__``.
_BINDING_ATTR = "_dock_binding"


class DockBinding:
    """Undo registration for one content widget's Config Dock controls.

    The Config Dock builds a node's widgets from scratch on every selection,
    so registrations here are re-made constantly and die with their widgets.
    There is nothing to tear down except what :meth:`clear` drops for nodes
    that manage their own commit timing.
    """

    def __init__(self, content: Any) -> None:
        self.content = content
        #: Widgets registered for change tracking.
        self.widgets: list = []

    @property
    def node(self) -> Any:
        return getattr(self.content, "node", None)

    # -- registration ------------------------------------------------------

    def tracked_values(self) -> dict:
        """Per-content map of last recorded widget values."""
        tracked = getattr(self.content, _TRACKED_ATTR, None)
        if tracked is None:
            tracked = {}
            setattr(self.content, _TRACKED_ATTR, tracked)
        return tracked

    def register(
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
        if widget in self.widgets:
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

        tracked = self.tracked_values()
        key = id(widget)
        if debounce_ms is None:
            debounce_ms = DEFAULT_DEBOUNCE_MS if immediate is None else None
        if immediate is None:
            immediate = isinstance(widget, _IMMEDIATE_WIDGET_TYPES)

        label = text or default_history_text(self.node)
        tracked[key] = seed

        connected = bind(
            self.content,
            widget,
            read=lambda k=key: tracked.get(k, _UNTRACKED),
            write=None,  # the node's own slot already mutated the model
            text=label,
            immediate=bool(immediate),
            debounce_ms=debounce_ms,
            merge_key=merge_key,
        )
        if connected:
            self.widgets.append(widget)
        return connected

    def register_all(self, layout: Optional[QLayout]) -> None:
        """Register every trackable widget in a layout tree.

        Cheap enough to call unconditionally at the end of ``create_layout``.
        """
        for widget in self.iter_widgets(layout):
            if widget_accepts_tracking(widget):
                self.register(widget)

    def register_unbound(self, layout: Optional[QLayout]) -> int:
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
        for widget in self.iter_widgets(layout):
            if not widget_accepts_tracking(widget):
                continue
            if getattr(widget, _BOUND_ATTR, False):
                continue
            if self._inside_composite(widget):
                continue
            if self.register(widget):
                added += 1
        return added

    # -- traversal ---------------------------------------------------------

    def iter_widgets(self, layout: Optional[QLayout]):
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
                yield from self.iter_widgets(widget.layout())
                inner = self._scroll_content(widget)
                if inner is not None:
                    yield inner
                    yield from self.iter_widgets(inner.layout())
            elif item.layout() is not None:
                yield from self.iter_widgets(item.layout())

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

    @staticmethod
    def _inside_composite(widget: QWidget) -> bool:
        """``True`` if ``widget`` is part of a composite that owns its signal."""
        parent = widget.parent()
        while parent is not None:
            if getattr(parent, _COMPOSITE_ATTR, False):
                return True
            parent = parent.parent()
        return False

    # -- fallbacks and teardown --------------------------------------------

    def record_fallback_change(self) -> None:
        """Snapshot fallback for widgets with no specific model binding.

        Records a real diff against the last known value rather than an
        unconditional "Input Modified", and honours the restore guard.
        """
        if getattr(self.content, "_suspend_input_tracking", False):
            return

        scene = getattr(self.node, "scene", None)
        if scene is None:
            return
        history = getattr(scene, "history", None)
        if history is None or history.is_restoring_history:
            return

        scene.has_been_modified = True
        history.storeHistory(default_history_text(self.node), setModified=False)

    @staticmethod
    def _disconnect(widget: QWidget) -> None:
        try:
            unbind(widget)
        except RuntimeError:
            return

    def clear(self) -> None:
        """Drop tracked widgets and their pending debounces.

        Nodes that manage their own commit timing - the formula editor, for
        one - call this so the generic tracker does not also record their
        edits.
        """
        for widget in self.widgets:
            self._disconnect(widget)
        self.widgets.clear()
        self.tracked_values().clear()

    def refresh_context(self) -> None:
        """Recompute the open dock's context strip from the model.

        The strip is a projection, like every other widget: the dock installs
        ``_dock_context_refresh`` while it owns this node's layout, and this is
        a no-op once the dock is gone or the node is destroyed.
        """
        # ``__dict__`` rather than ``getattr``: this callback is Python-side
        # bookkeeping, so read it without resolving descriptors or other
        # binding-provided attributes on an uninitialized or deleted widget.
        try:
            callback = self.content.__dict__.get("_dock_context_refresh")
        except RuntimeError:
            return
        if callback is None:
            return
        try:
            callback()
        except RuntimeError:
            # Widget already deleted (dock rebuilt or node removed).
            pass


def _binding_of(content: Any) -> DockBinding:
    """The content's :class:`DockBinding`, created on first use.

    Lazy rather than built in ``__init__`` because not every content class
    cooperates with cooperative ``super().__init__()`` - several build on
    ``(QDMNodeIconContentWidget, TriggerChangeHandler)`` and override
    ``__init__`` without chaining, so attributes set there never run.
    Reading a plain attribute then raised ``AttributeError`` from inside
    ``create_layout``, which ``ConfigDock`` catches broadly, leaving that
    node's config panel silently blank.
    """
    binding = content.__dict__.get(_BINDING_ATTR)
    if binding is None:
        binding = DockBinding(content)
        content.__dict__[_BINDING_ATTR] = binding
    return binding


class TriggerChangeHandler(TriggerContentUndoMixin):
    """Wires a node's Config Dock widgets into the undo system.

    Also the carrier for :class:`TriggerContentUndoMixin`: every content class
    inherits this, and the mixin supplies ``sync_from_model``,
    ``history_stamp_callback`` and the ``push_*_change`` helpers. Keeping that
    on this base means new nodes get undo support without opting in.

    The registration logic lives on :class:`DockBinding`; the methods here are
    the stable names nodes and the Config Dock call.
    """

    def __init__(self, scene: "Scene", node: "TriggerNode") -> None:
        self._scene = scene
        self._suspend_input_tracking = False
        self.node = node

    @property
    def binding(self) -> DockBinding:
        return _binding_of(self)

    @property
    def _input_widgets(self) -> list:
        """Widgets registered for change tracking."""
        return _binding_of(self).widgets

    def refresh_dock_context(self) -> None:
        _binding_of(self).refresh_context()

    def registerInputWidget(
        self,
        widget: QWidget,
        text: Optional[str] = None,
        immediate: Optional[bool] = None,
        debounce_ms: Optional[int] = None,
        merge_key: Optional[str] = None,
    ) -> bool:
        """Make edits to ``widget`` undoable (see :meth:`DockBinding.register`)."""
        return _binding_of(self).register(
            widget,
            text=text,
            immediate=immediate,
            debounce_ms=debounce_ms,
            merge_key=merge_key,
        )

    def _tracked_values(self) -> dict:
        return _binding_of(self).tracked_values()

    def is_input_widget(self, widget: QWidget) -> bool:
        """Check if a widget is an input widget we track."""
        return widget_accepts_tracking(widget)

    def iter_dock_widgets(self, layout: Optional[QLayout]):
        return _binding_of(self).iter_widgets(layout)

    def registerUnboundDockWidgets(self, layout: Optional[QLayout]) -> int:
        return _binding_of(self).register_unbound(layout)

    def recursively_find_widgets(self, layout: Optional[QLayout]) -> None:
        _binding_of(self).register_all(layout)

    def onInputChanged(self, *args: list) -> None:
        """Fallback for widgets with no specific model binding."""
        del args
        _binding_of(self).record_fallback_change()

    def clearInputWidgets(self) -> None:
        _binding_of(self).clear()


class ConfigContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """The one canonical base for Config Dock content widgets.

    Owns what every node family used to duplicate: an ``evaluate`` signal, the
    node getter/setter, the dock icon setup, the history reference and (through
    :class:`TriggerChangeHandler`) the :class:`DockBinding` and undo helpers.
    Node-specific data, widgets, serialization and code generation stay on the
    subclass.
    """

    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: QWidget | None = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, node.scene, node)
        self.history = node.scene.history

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, _icon: QPixmap | None = None) -> None:
        super().initUI(self.node.rsm.get(f"{self.node.icon}"))


class TriggerContent(ConfigContent):
    """Legacy default content: the node's label instead of its icon.

    Kept as a thin adapter over :class:`ConfigContent` for nodes that never
    declare their own content class. ``history_stamp_callback`` still resolves
    to :class:`TriggerContentUndoMixin` (the Qt base defines none), so a
    restore re-projects through ``sync_from_model``.
    """

    def initUI(self, icon: Optional[QPixmap] = None) -> Any:
        #: Recorded here as well as in the base: nodes that build on
        #: ``TriggerContent`` override the base's ``initUI``, and the low-zoom
        #: repaint blits this pixmap instead of rendering the widget.
        self.icon = icon
        lbl = QLabel(self.node.content_label, self)  # type: ignore
        lbl.setObjectName(self.node.content_label_objname)  # type: ignore
