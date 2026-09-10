"""Shared config-dock widgets: one style, no per-node UI rewrites."""

from typing import Callable, Iterable, Optional

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


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
