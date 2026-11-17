"""Banner and review dialog for a workflow rewritten outside the editor.

When an external tool (an AI agent, a script) rewrites an open ``.tds`` file,
the document window shows :class:`ExternalEditBanner` above the canvas. It is
non-modal: the user keeps working, and can reload, keep the in-editor version,
or review what changed. :class:`ExternalChangeDialog` lists the diff lines.

The banner only presents a change. It never reads the file or touches the
document: the owner connects the four signals to the document window
(docs/DESIGN_SYSTEM.md §1, §4, §17).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.theme_manager import repolish
from trigger_designer.qt.widgets.common.config_widgets import (
    ICON_SIZE,
    STRIP_H,
    ElidedLabel,
    IconButton,
    TextButton,
)

if TYPE_CHECKING:
    from trigger_designer.core.authoring.external_edit import ExternalChange

#: The banner's status glyph. resources.json has no edit glyph, so it is
#: registered as a Material Symbol; an entry that resources.json already has
#: always wins (``ResourceManager.register_material`` uses ``setdefault``).
_BANNER_ICON = "icon_external_edit"
#: "Keep my version" glyph. ``icon_clear`` is a delete-sweep and would read as
#: discarding data, so a dismiss cross is registered instead.
_KEEP_ICON = "icon_external_keep"
_MATERIAL_GLYPHS = {_BANNER_ICON: "edit_note", _KEEP_ICON: "close"}

_REVIEW_ICON = "icon_compare"
_RELOAD_ICON = "icon_refresh"
_REVIEWED_ICON = "icon_verify"

_REVIEW_TIP = "Review changes"
_RELOAD_TIP = "Reload from disk"
_KEEP_TIP = "Keep my version, ignore this change"
_REVIEWED_TIP = "Mark all as reviewed"

_TONE_INFO = "info"
_TONE_WARNING = "warning"

_DIALOG_TITLE = "Changes made outside Trigger Designer"
_NO_CHANGES = "(no node changes)"
_PROBLEMS_HEADING = "Problems:"


def _register_glyphs() -> None:
    for resource_id, name in _MATERIAL_GLYPHS.items():
        ResourceManager.register_material(resource_id, name)


def _glyph(resource_id: str) -> QPixmap | None:
    """The theme-tinted glyph at the status-icon size, or None if unresolved."""
    pixmap = ResourceManager().get(resource_id)
    if not isinstance(pixmap, QPixmap) or pixmap.isNull():
        return None
    return pixmap.scaled(
        ICON_SIZE,
        ICON_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _pending_message(change: ExternalChange, unsaved: bool) -> str:
    if not unsaved:
        return change.summary
    return f"{change.summary}. You also have unsaved changes; you can undo the reload."


def _applied_message(count: int, removed: int) -> str:
    noun = "node" if count == 1 else "nodes"
    message = f"{count} {noun} changed by an external tool"
    if removed:
        message += f", {removed} removed"
    return message


def _change_lines(change: Any) -> list[str]:
    """The diff lines of ``change``, followed by its problems when it has any."""
    lines = [str(line) for line in (getattr(change, "lines", ()) or ())]
    problems = [str(problem) for problem in (getattr(change, "problems", ()) or ())]
    if not problems:
        return lines
    if lines:
        return [*lines, "", _PROBLEMS_HEADING, *problems]
    return problems


class ExternalEditBanner(QFrame):
    """Non-modal strip telling the user an external tool changed the file.

    ``mode`` is one of ``hidden``, ``pending`` (a change awaits a decision),
    ``applied`` (the change is in the editor and awaits review) or ``invalid``
    (the external file could not be read). Each mode shows only the actions it
    needs. The signals report the user's choice; the owner does the work.
    """

    reloadRequested = Signal()
    reviewRequested = Signal()
    keepRequested = Signal()
    reviewedRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ExternalEditBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(STRIP_H)
        self._mode = "hidden"
        _register_glyphs()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(4)

        self._icon = QLabel(self)
        self._icon.setObjectName("ExternalEditIcon")
        self._icon.setFixedSize(QSize(ICON_SIZE, ICON_SIZE))
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self._message = ElidedLabel("", self)
        self._message.setObjectName("ExternalEditMessage")
        layout.addWidget(self._message, 1)

        self._review = self._action(_REVIEW_TIP, _REVIEW_ICON)
        self._reload = self._action(_RELOAD_TIP, _RELOAD_ICON)
        self._keep = self._action(_KEEP_TIP, _KEEP_ICON)
        self._reviewed = self._action(_REVIEWED_TIP, _REVIEWED_ICON)
        for button in self._buttons():
            layout.addWidget(button)

        self._review.clicked.connect(self.reviewRequested.emit)
        self._reload.clicked.connect(self.reloadRequested.emit)
        self._keep.clicked.connect(self.keepRequested.emit)
        self._reviewed.clicked.connect(self.reviewedRequested.emit)

        self.setProperty("mode", self._mode)
        self.setProperty("tone", _TONE_INFO)
        glyph = _glyph(_BANNER_ICON)
        if glyph is not None:
            self._icon.setPixmap(glyph)
        self._set_actions(review=False, reload=False, keep=False, reviewed=False)
        self.setVisible(False)

    # -- state -------------------------------------------------------------
    @property
    def mode(self) -> str:
        """``hidden``, ``pending``, ``applied`` or ``invalid``."""
        return self._mode

    def show_change(self, change: ExternalChange, *, unsaved: bool) -> None:
        """An external change awaits a decision: reload it or keep the editor's."""
        self._present(
            "pending",
            _pending_message(change, unsaved),
            _TONE_WARNING if unsaved else _TONE_INFO,
            review=bool(change.lines),
            reload=True,
            keep=True,
            reviewed=False,
        )

    def show_applied(self, count: int, removed: int = 0) -> None:
        """Changes are in the editor and wait for the user to review them."""
        self._present(
            "applied",
            _applied_message(count, removed),
            _TONE_INFO,
            review=True,
            reload=False,
            keep=False,
            reviewed=True,
        )

    def show_invalid(self, message: str) -> None:
        """The external file could not be read; the only action is to dismiss."""
        self._present(
            "invalid",
            message,
            _TONE_WARNING,
            review=False,
            reload=False,
            keep=True,
            reviewed=False,
        )

    def clear(self) -> None:
        """Hide the banner and every action."""
        self._mode = "hidden"
        self.setProperty("mode", "hidden")
        self.setProperty("tone", _TONE_INFO)
        self._message.set_full_text("")
        self._set_actions(review=False, reload=False, keep=False, reviewed=False)
        self.setVisible(False)

    def apply_theme(self) -> None:
        """Re-resolve the glyphs after a theme change (see IconButton.apply_theme)."""
        glyph = _glyph(_BANNER_ICON)
        if glyph is not None:
            self._icon.setPixmap(glyph)
        for button in self._buttons():
            button.apply_theme()
        repolish(self)

    # -- internals ---------------------------------------------------------
    def _action(self, tooltip: str, resource_id: str) -> IconButton:
        return IconButton.themed(
            tooltip,
            rsm_icon=ResourceManager().get(resource_id),
            parent=self,
        )

    def _buttons(self) -> tuple[IconButton, ...]:
        return (self._review, self._reload, self._keep, self._reviewed)

    def _set_actions(
        self, *, review: bool, reload: bool, keep: bool, reviewed: bool
    ) -> None:
        self._review.setVisible(review)
        self._reload.setVisible(reload)
        self._keep.setVisible(keep)
        self._reviewed.setVisible(reviewed)

    def _present(
        self,
        mode: str,
        message: str,
        tone: str,
        *,
        review: bool,
        reload: bool,
        keep: bool,
        reviewed: bool,
    ) -> None:
        self._mode = mode
        self.setProperty("mode", mode)
        self.setProperty("tone", tone)
        self._message.set_full_text(message)
        self._set_actions(review=review, reload=reload, keep=keep, reviewed=reviewed)
        repolish(self)
        self.setVisible(True)


class ExternalChangeDialog(QDialog):
    """Read-only list of the lines an external tool changed.

    Opened from the banner's Review action. The text is the lines as given;
    :meth:`for_change` builds them from an ``ExternalChange``.
    """

    def __init__(self, lines: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ExternalChangeDialog")
        self.setWindowTitle(_DIALOG_TITLE)
        self.setMinimumSize(560, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(8)

        self._text = QPlainTextEdit(self)
        self._text.setObjectName("ExternalChangeText")
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._text.setPlainText("\n".join(lines) if lines else _NO_CHANGES)
        layout.addWidget(self._text, 1)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        close = TextButton("Close")
        close.clicked.connect(self.accept)
        footer.addStretch(1)
        footer.addWidget(close)
        layout.addLayout(footer)

    @classmethod
    def for_change(
        cls, change: ExternalChange, parent: QWidget | None = None
    ) -> ExternalChangeDialog:
        """The dialog for one change: its diff lines, then any problems."""
        return cls(_change_lines(change), parent)
