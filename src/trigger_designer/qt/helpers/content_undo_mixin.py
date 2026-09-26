from typing import Any, Optional

from qtpy.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QDateTimeEdit,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QSlider,
    QTableWidget,
    QTextEdit,
    QWidget,
)

from trigger_designer.qt.undo.protocol import sync_from_model

#: Attribute holding the last recorded value per bound widget, keyed by widget
#: identity. Seeded when a widget is registered so the first edit has a real
#: "before" value to record against.
_TRACKED_ATTR = "_undo_tracked_values"

#: Marks a composite widget that owns its own change signal. Controls nested
#: inside one are skipped by the Config Dock's registration sweep, otherwise
#: the composite's signal and its children would record the same edit twice.
_COMPOSITE_ATTR = "_undo_composite"

#: Attribute holding a widget's undo/redo label and timing preferences.
_BINDING_META_ATTR = "_undo_binding_meta"

#: Widget types the Config Dock is expected to contain. Kept deliberately wide:
#: the old tuple omitted double spins, text editors and list/table widgets,
#: which silently went untracked.
_TRACKED_WIDGET_TYPES = (
    QAbstractSpinBox,  # QSpinBox, QDoubleSpinBox
    QDateTimeEdit,
    QSlider,
    QComboBox,
    QAbstractButton,  # QCheckBox, QRadioButton, QToolButton
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QListWidget,
    QTableWidget,
)

#: Controls whose every intermediate value is meaningful, so they commit
#: immediately rather than waiting out a debounce.
_IMMEDIATE_WIDGET_TYPES = (
    QAbstractSpinBox,
    QDateTimeEdit,
    QSlider,
    QComboBox,
    QAbstractButton,
)


class _Untracked:
    """Sentinel for "this widget has no recorded value yet"."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<untracked>"


_UNTRACKED = _Untracked()


def widget_accepts_tracking(widget: QWidget) -> bool:
    """Whether ``widget`` is a kind the Config Dock builds and we can track.

    Spans more widget types than before: double spins, text editors and
    list/table widgets were all silently untracked, so changes to them were
    not undoable.
    """
    return isinstance(widget, _TRACKED_WIDGET_TYPES)


def default_history_text(node: Any) -> str:
    """Fallback ``"Noun Verbed"`` label for an unlabelled control.

    Better than a flat "Input Modified" because the menu entry then names
    the node the change belongs to.
    """
    title = ""
    for obj in (getattr(node, "node", None), node):
        candidate = getattr(obj, "title", None) or getattr(obj, "node_title", None)
        if isinstance(candidate, str) and candidate.strip():
            title = candidate.strip()
            break
    return f"Modified {title}" if title else "Modified Settings"


class TriggerContentUndoMixin:
    """Undo/redo participation for node content widgets.

    Content classes opt in by implementing whichever of these they need:

    * ``_sync_widgets_from_model()`` - push model values into the live widgets,
      preserving widget identity so a focused editor is not torn down. Called
      after every undo/redo and after any live refresh.
    * ``_rebuild_widgets()`` - recreate widget *structure* from the model.
      Needed when the change alters how many widgets exist, such as adding or
      removing a formula section.

    Both are optional; :meth:`sync_from_model` degrades to a no-op when they
    are absent. The Config Dock is force-rebuilt after a history restore, which
    covers the widget state even when a node implements neither.
    """

    def _sync_widgets_from_model(self) -> None:
        """Refresh widget values from the model. Override when useful."""

    def _rebuild_widgets(self) -> None:
        """Rebuild widget structure from the model. Override when useful."""

    def sync_from_model(self, rebuild: bool = False, evaluate: bool = True) -> bool:
        """Re-project the model onto this node's widgets.

        Safe to call from anywhere: it is a no-op while the widgets are already
        being written from the model.
        """
        return sync_from_model(self, rebuild=rebuild, evaluate=evaluate)

    def history_stamp_callback(self, history_data: dict, is_undo: bool) -> None:
        """Reconcile widgets after a snapshot restore.

        The scene snapshot has already put the model back by the time this
        runs, so the only job left is the widget projection. Routing it
        through :meth:`sync_from_model` means one code path serves both
        snapshot commands and fine grained ones, instead of every node
        hand-rolling its own restore.
        """
        del history_data, is_undo
        self.sync_from_model()

    def push_property_change(
        self,
        path,
        old: Any,
        new: Any,
        text: str,
        *,
        rebuild: bool = False,
        merge_key: Optional[str] = None,
    ) -> bool:
        """Record a change to one setting, as a fine grained undo step.

        Prefer this over :meth:`storeHistory` for node settings: it captures
        only the affected value and re-projects the widgets on restore,
        instead of serializing the whole scene.
        """
        from trigger_designer.qt.undo.commands import PropertyChangeCommand

        history = getattr(self, "history", None)
        if history is None or not hasattr(history, "push_edit"):
            return False
        return history.push_edit(
            PropertyChangeCommand(
                getattr(self, "node", None),
                path,
                old,
                new,
                text,
                rebuild=rebuild,
                merge_key=merge_key,
            )
        )

    def push_list_change(
        self,
        path,
        old,
        new,
        text: str,
        *,
        merge_key: Optional[str] = None,
    ) -> bool:
        """Record a change to a collection of settings, e.g. formula sections.

        Rebuilds the widgets on restore, since adding or removing a row
        changes how many editors exist rather than just their contents.
        """
        from trigger_designer.qt.undo.commands import ListStructureCommand

        history = getattr(self, "history", None)
        if history is None or not hasattr(history, "push_edit"):
            return False
        return history.push_edit(
            ListStructureCommand(
                getattr(self, "node", None),
                path,
                old,
                new,
                text,
                merge_key=merge_key,
            )
        )
