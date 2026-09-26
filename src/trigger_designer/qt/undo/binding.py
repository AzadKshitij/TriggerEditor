"""Widget-to-model bindings.

The Config Dock builds a node's widgets from scratch every time the node is
selected, so bindings are created in ``create_layout`` and die with their
widgets. There is nothing to unregister.

Each binding owns three responsibilities the old generic ``onInputChanged``
hook did not:

* **Debounce.** Text and search inputs commit after a pause (~300ms per the
  design system) instead of one history entry per keystroke.
* **Real diffs only.** A signal that does not change the model is dropped, so
  re-selecting a combo's current item or any programmatic no-op never lands
  on the timeline.
* **Silence while the model drives.** Everything is skipped when the widgets
  are being written *from* the model
  (:func:`~trigger_designer.qt.undo.protocol.is_syncing`), when the Config
  Dock is mid-rebuild, or during an undo. Without this a restore records the
  change it is restoring and the user can never undo past it.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from loguru import logger as global_logger
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QDateTimeEdit,
    QDoubleSpinBox,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QSlider,
    QTableWidget,
    QTextEdit,
    QWidget,
)

from trigger_designer.qt.undo.commands import (
    PropertyChangeCommand,
    keep_old_side,
)
from trigger_designer.qt.undo.protocol import (
    history_of,
    is_suspended,
    is_syncing,
)

#: Pause before a text or search edit is committed to the timeline.
DEFAULT_DEBOUNCE_MS = 300

#: Attribute holding a binding's debounce timer on its widget.
_TIMER_ATTR = "_undo_debounce_timer"

#: Attribute marking a widget as already bound, so a rebuild that happens to
#: reuse a widget does not stack duplicate connections.
_BOUND_ATTR = "_undo_bound"

#: Change signals in priority order, most specific first.
_SIGNAL_CANDIDATES: tuple[str, ...] = (
    "textChanged",
    "valueChanged",
    "currentTextChanged",
    "currentIndexChanged",
    "dateTimeChanged",
    "itemChanged",
    "cellChanged",
    "stateChanged",
    "toggled",
    "currentRowChanged",
    "sliderMoved",
)


def value_of(widget: QWidget) -> Any:
    """Read a widget's current value as a plain Python object.

    Spins and sliders become ``int``/``float``, checkboxes and tristate
    buttons ``bool``, text controls their string. Normalising here is what
    lets the diff in :func:`bind` compare like with like.
    """
    if isinstance(widget, QAbstractButton):
        # A tristate button reports a partial state that is neither the old
        # nor the new value, so treat anything non-zero as checked.
        return bool(widget.isChecked())
    if isinstance(widget, QAbstractSpinBox):
        if isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        return int(widget.value())
    if isinstance(widget, QSlider):
        return int(widget.value())
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, QDateTimeEdit):
        return widget.dateTime().toString(Qt.ISODate)
    if isinstance(widget, QPlainTextEdit):
        return widget.toPlainText()
    if isinstance(widget, QTextEdit):
        return widget.toPlainText()
    if isinstance(widget, QLineEdit):
        return widget.text()
    if isinstance(widget, QTableWidget):
        return [
            [
                widget.item(row, col).text() if widget.item(row, col) else ""
                for col in range(widget.columnCount())
            ]
            for row in range(widget.rowCount())
        ]
    if isinstance(widget, QListWidget):
        # QListWidget counts with count(), not rowCount() - the latter is
        # QTableWidget's API and raises AttributeError here.
        return [
            widget.item(i).text() if widget.item(i) else ""
            for i in range(widget.count())
        ]

    for name in ("text", "value", "isChecked"):
        if hasattr(widget, name):
            attr = getattr(widget, name)
            return attr() if callable(attr) else attr
    return None


def safe_value_of(widget: QWidget) -> Any:
    """:func:`value_of`, but returns the ``_MISSING`` sentinel on failure.

    Callers must tolerate a sentinel because this runs while the Config Dock is
    building: ``value_of`` is duck-typed over Qt widget types, and an
    AttributeError escaping from here propagates out of ``create_layout`` and
    leaves the node's whole config panel blank.
    """
    try:
        return value_of(widget)
    except Exception as exc:
        global_logger.debug(f"Cannot read a value from {type(widget).__name__}: {exc}")
        return _MISSING


def is_missing(value: Any) -> bool:
    """Whether ``value`` is the "unreadable" sentinel from :func:`safe_value_of`.

    A distinct sentinel rather than ``None``, because ``None`` is a perfectly
    legitimate value for a combo with nothing selected.
    """
    return isinstance(value, _Missing)


def pick_signal(widget: QWidget) -> Optional[str]:
    """Choose the most specific change signal ``widget`` offers.

    :return: a signal name, or ``None`` when the widget exposes nothing
        recognisable and needs :func:`bind_payload`.
    """
    for name in _SIGNAL_CANDIDATES:
        if hasattr(widget, name):
            return name
    return None


def bind(
    content: Any,
    widget: QWidget,
    *,
    read: Callable[[], Any],
    write: Optional[Callable[[Any], None]] = None,
    text: str = "Value Changed",
    debounce_ms: Optional[int] = DEFAULT_DEBOUNCE_MS,
    immediate: bool = False,
    merge_key: Optional[str] = None,
    path: Optional[Sequence[str]] = None,
    to_model: Optional[Callable[[QWidget], Any]] = None,
    rebuild: bool = False,
) -> bool:
    """Record user edits to ``widget`` as undoable changes.

    :param content: the node's content widget. Bindings are skipped while it
        is being rebuilt, and its model is what ``read``/``path`` describe.
    :param read: returns the model's current value for this setting.
    :param write: applies a new value to the model, called *before* the
        command is recorded so evaluation sees the new state. Omit it when the
        caller has already mutated the model.
    :param text: history label, ``"Noun Verbed"`` per the design system.
    :param debounce_ms: pause before committing. ``None``, or ``immediate``,
        commits synchronously - which is what non-text controls want, since
        a checkbox or spin box has no intermediate states worth keeping.
    :param merge_key: collapse a burst of edits into one undo step. Use one
        key per control; a key shared across controls would merge unrelated
        edits.
    :param path: dotted attribute path on ``content``. Supplying it records a
        :class:`PropertyChangeCommand`, which is cheap and restores the
        widgets in place. Omit it to fall back to a whole-scene snapshot -
        always correct, but heavier and reliant on the dock rebuild.
    :param to_model: converts the widget into a model value. Defaults to
        :func:`value_of`.
    :param rebuild: the restore changes widget *structure* rather than just
        values.
    :return: ``True`` if a signal was found and connected.
    """
    if getattr(widget, _BOUND_ATTR, False):
        return False

    signal_name = pick_signal(widget)
    if signal_name is None:
        return False

    reader = _safe_reader(read)
    to_value = to_model if to_model is not None else safe_value_of

    pending: list[Any] = []

    def commit(value: Any) -> None:
        old = reader()
        if isinstance(old, _Missing) or old == value:
            # Not a real change: the signal fired without altering the model,
            # or the model is mid-rebuild and unreadable.
            return

        node = getattr(content, "node", None)
        history = history_of(content)

        if write is not None:
            write(value)

        if path is not None and hasattr(history, "push_edit"):
            history.push_edit(
                PropertyChangeCommand(
                    node,
                    path,
                    old,
                    value,
                    text,
                    merge_key=merge_key,
                    rebuild=rebuild,
                )
            )
            return

        # Snapshot fallback: still correct, just heavier.
        if history is not None:
            history.storeHistory(
                desc=text,
                setModified=True,
                data={"node": node, "old_state": old, "new_state": value},
                merge_key=merge_key,
                merge=keep_old_side,
            )

    def flush() -> None:
        if pending:
            commit(pending.pop())

    def on_changed(*_args: Any) -> None:
        if is_syncing(content) or is_suspended(content):
            return
        history = history_of(content)
        if getattr(history, "is_restoring_history", False):
            return

        value = to_value(widget)
        current = reader()
        if is_missing(current) or is_missing(value):
            # The model is mid-rebuild, or this widget's value cannot be read.
            # Either way there is nothing trustworthy to record.
            return
        if current == value:
            return

        if immediate or debounce_ms is None:
            commit(value)
            return

        pending[:] = [value]
        timer = getattr(widget, _TIMER_ATTR, None)
        if timer is None:
            timer = QTimer(widget)
            timer.setSingleShot(True)
            timer.timeout.connect(flush)
            setattr(widget, _TIMER_ATTR, timer)
        timer.start(debounce_ms)

    getattr(widget, signal_name).connect(on_changed)
    setattr(widget, _BOUND_ATTR, True)
    return True


def bind_payload(
    content: Any,
    widget: QWidget,
    signal_name: str,
    *,
    write: Callable[[Any], None],
    text: str,
    read: Optional[Callable[[], Any]] = None,
    merge_key: Optional[str] = None,
) -> bool:
    """Bind a custom widget that emits its own new value.

    For the widgets that do not fit the standard signal set: a column
    checklist emitting the list of checked columns, a table emitting a list of
    row dicts. The signal's argument *is* the model value, so ``write``
    receives it directly and ``read`` is only used to skip no-op emissions.
    """
    if getattr(widget, _BOUND_ATTR, False):
        return False

    signal = getattr(widget, signal_name, None)
    if signal is None or not hasattr(signal, "connect"):
        return False

    reader = _safe_reader(read) if read is not None else None

    def on_changed(value: Any) -> None:
        if is_syncing(content) or is_suspended(content):
            return
        history = history_of(content)
        if getattr(history, "is_restoring_history", False):
            return
        if reader is not None and reader() == value:
            return
        write(value)

    signal.connect(on_changed)
    setattr(widget, _BOUND_ATTR, True)
    return True


def unbind(widget: QWidget) -> None:
    """Cancel a binding's pending debounce. Optional; bindings die with widgets."""
    timer = getattr(widget, _TIMER_ATTR, None)
    if timer is not None:
        timer.stop()
        setattr(widget, _TIMER_ATTR, None)


def _safe_reader(read: Optional[Callable[[], Any]]) -> Callable[[], Any]:
    """Wrap ``read`` so a half-built widget cannot break the signal handler.

    During a Config Dock rebuild the model can be mid-update; a reader that
    raises must not propagate out of a Qt slot.
    """
    if read is None:
        return lambda: None

    def reader() -> Any:
        try:
            return read()
        except Exception:
            return _MISSING

    return reader


class _Missing:
    """Sentinel for "the model is not readable right now"."""

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Missing)

    def __hash__(self) -> int:
        return hash("undo.missing")


_MISSING = _Missing()
