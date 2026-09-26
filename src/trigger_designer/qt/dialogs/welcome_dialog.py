"""Startup welcome dialog: recents plus New and Browse actions."""

from __future__ import annotations

from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WelcomeDialog(QDialog):
    """Pick a recent project, start a new one, or browse for a file.

    After :meth:`exec`, read :attr:`action` (``"open"``, ``"new"``,
    ``"browse"``, or ``None`` when cancelled) and :attr:`selected_path`.
    The checkbox state is exposed via :attr:`show_on_startup`; callers
    persist it through ``RecentFilesManager``.
    """

    def __init__(
        self,
        recents: list[str],
        show_on_startup: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to Trigger Designer")
        self.setMinimumWidth(520)
        self.setObjectName("WelcomeDialog")

        self.action: str | None = None
        self.selected_path: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        header = QLabel("Open recent project", self)
        header.setObjectName("WelcomeHeader")
        layout.addWidget(header)

        self.recents_list = QListWidget(self)
        self.recents_list.setObjectName("WelcomeRecents")
        self.recents_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        for path in recents:
            item = QListWidgetItem(path, self.recents_list)
            item.setToolTip(path)
            item.setData(256, path)
        if recents:
            self.recents_list.setCurrentRow(0)
        self.recents_list.itemDoubleClicked.connect(lambda _item: self._on_open())
        layout.addWidget(self.recents_list, 1)

        if not recents:
            self.empty_label = QLabel("No recent projects yet", self)
            self.empty_label.setObjectName("EmptyStateLabel")
            layout.addWidget(self.empty_label)
        else:
            self.empty_label = None

        self.show_checkbox = QCheckBox("Show this dialog on startup", self)
        self.show_checkbox.setChecked(show_on_startup)
        layout.addWidget(self.show_checkbox)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        self.new_button = QPushButton("New Project", self)
        self.new_button.setMinimumHeight(30)
        self.new_button.clicked.connect(self._on_new)
        self.browse_button = QPushButton("Browse...", self)
        self.browse_button.setMinimumHeight(30)
        self.browse_button.clicked.connect(self._on_browse)
        button_row.addWidget(self.new_button)
        button_row.addWidget(self.browse_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Open).setText("Open")
        self.button_box.accepted.connect(self._on_open)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    @property
    def show_on_startup(self) -> bool:
        return self.show_checkbox.isChecked()

    def _current_path(self) -> str | None:
        item = self.recents_list.currentItem()
        if item is None:
            return None
        data = item.data(256)
        return str(data) if data else item.text()

    def _on_open(self) -> None:
        path = self._current_path()
        if not path:
            return
        self.action = "open"
        self.selected_path = path
        self.accept()

    def _on_new(self) -> None:
        self.action = "new"
        self.selected_path = None
        self.accept()

    def _on_browse(self) -> None:
        self.action = "browse"
        self.selected_path = None
        self.accept()
