"""Shared config-dock widgets: one style, no per-node UI rewrites."""

from collections.abc import Callable, Iterable
from typing import Optional

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon, QPixmap
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class IconButton(QPushButton):
    """Icon-only button: 30x30, 12px icon, tooltip + accessible name required.

    Resolves the icon via ResourceManager id first, then a compiled
    ``:/qss_icons`` fallback, then ``QIcon.fromTheme`` (last resort —
    blank on Windows, see docs/DESIGN_SYSTEM.md §4).
    """

    def __init__(
        self,
        tooltip: str,
        icon: QIcon | QPixmap | str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setText("")
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setFixedSize(QSize(30, 30))
        self.setIconSize(QSize(12, 12))
        if isinstance(icon, QIcon):
            self.setIcon(icon)
        elif isinstance(icon, QPixmap):
            self.setIcon(QIcon(icon))
        elif isinstance(icon, str):
            self.setIcon(QIcon(icon))

    @classmethod
    def themed(
        cls,
        tooltip: str,
        rsm_icon: QIcon | QPixmap | None = None,
        qss_fallback: str | None = None,
        theme_fallback: str | None = None,
        parent: QWidget | None = None,
    ) -> "IconButton":
        """Build an IconButton trying rsm -> :/qss_icons -> fromTheme."""
        icon: QIcon | None = None
        if isinstance(rsm_icon, QPixmap):
            icon = QIcon(rsm_icon)
        elif isinstance(rsm_icon, QIcon) and not rsm_icon.isNull():
            icon = rsm_icon
        if icon is None and qss_fallback:
            candidate = QIcon(qss_fallback)
            if not candidate.isNull():
                icon = candidate
        if icon is None and theme_fallback:
            candidate = QIcon.fromTheme(theme_fallback)
            if not candidate.isNull():
                icon = candidate
        return cls(tooltip, icon, parent)


class TextButton(QPushButton):
    """Labelled button for bulk actions whose icon alone is ambiguous.

    Reserved for pairs like "All" / "None" (select-all vs deselect-all) where
    two near-identical checkbox glyphs cannot be told apart at a glance.
    Everything else in the Config Dock stays icon-only; see
    docs/DESIGN_SYSTEM.md §4.3.
    """

    def __init__(
        self,
        text: str,
        tooltip: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("TextButton")
        self.setToolTip(tooltip or text)
        self.setAccessibleName(tooltip or text)
        self.setMinimumHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class NoWheelComboBox(QComboBox):
    """Combo box that ignores the mouse wheel unless its popup is open.

    Prevents accidental selection changes when scrolling a sidebar with
    the cursor resting over a dropdown (a focused combo would otherwise
    keep stealing wheel events long after it was touched).
    """

    def wheelEvent(self, event) -> None:
        try:
            popup_open = self.view().isVisible()
        except RuntimeError:
            popup_open = False
        if not popup_open:
            event.ignore()
            return
        super().wheelEvent(event)


class ConfigSection(QGroupBox):
    """Bold group box with optional info line. Style via QSS objectNames."""

    def __init__(
        self, title: str, info: Optional[str] = None, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(title, parent)
        self.setObjectName("ConfigSection")
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(2)
        if info:
            info_label = QLabel(info, self)
            info_label.setObjectName("ConfigSectionInfo")
            info_label.setWordWrap(True)
            self._layout.addWidget(info_label)
        self.setLayout(self._layout)

    def addWidget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def addLayout(self, layout: QLayout) -> None:
        self._layout.addLayout(layout)


class ColumnChecklist(QWidget):
    """Scrollable checkbox list. Emits checked column names on change."""

    changed = Signal(list)

    def __init__(
        self,
        columns: Iterable[str] = (),
        checked: Iterable[str] = (),
        label_fn: Optional[Callable[[str], str]] = None,
        max_height: int = 150,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ColumnChecklist")
        self._label_fn = label_fn or (lambda col: col)
        self._suspend = False
        self.checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(max_height)
        self._inner = QWidget(scroll)
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner.setLayout(self._inner_layout)
        scroll.setWidget(self._inner)
        layout.addWidget(scroll)
        self.setLayout(layout)

        self.setColumns(columns, checked)

    def setColumns(self, columns: Iterable[str], checked: Iterable[str] = ()) -> None:
        self._suspend = True
        try:
            while self._inner_layout.count():
                item = self._inner_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.checkboxes.clear()
            checked_set = set(checked)
            for col in columns:
                checkbox = QCheckBox(self._label_fn(col))
                checkbox.setChecked(col in checked_set)
                checkbox.stateChanged.connect(self._on_state_changed)
                self.checkboxes[col] = checkbox
                self._inner_layout.addWidget(checkbox)
        finally:
            self._suspend = False

    def setChecked(self, checked: Iterable[str]) -> None:
        self._suspend = True
        try:
            checked_set = set(checked)
            for col, checkbox in self.checkboxes.items():
                checkbox.setChecked(col in checked_set)
        finally:
            self._suspend = False

    def checked(self) -> list[str]:
        return [col for col, cb in self.checkboxes.items() if cb.isChecked()]

    def _on_state_changed(self, _state: int) -> None:
        if not self._suspend:
            self.changed.emit(self.checked())


class EmptyStateLabel(QLabel):
    """Centered gray placeholder for nodes with no incoming data."""

    def __init__(
        self,
        text: str = "No incoming data available",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("EmptyStateLabel")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
