"""Problems dock: one clickable row per node error."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor, QGuiApplication
from qtpy.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.errors import NodeError
from trigger_designer.qt.preferences import get_preferences
from trigger_designer.qt.theme_manager import get_theme_manager
from trigger_designer.qt.widgets.common import EmptyStateLabel, IconButton

if TYPE_CHECKING:
    from trigger_designer.qt.design_window import TriggerSubWindow

_TITLE = "Problems"


class ProblemsDock(QDockWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_TITLE, parent)
        self.setObjectName("ProblemsDock")
        self._window: TriggerSubWindow | None = None
        self._store = None
        self._entries: list[NodeError] = []
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(0)
        self._refresh_timer.timeout.connect(self.refresh)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(300)
        self._filter_timer.timeout.connect(self.refresh)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self._build()
        self.apply_theme()

    def _build(self) -> None:
        panel = QWidget(self)
        panel.setObjectName("ProblemsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        toolbar = QWidget(panel)
        toolbar.setFixedHeight(40)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(2)
        self.search = QLineEdit(toolbar)
        self.search.setPlaceholderText("Filter problems")
        self.search.setMinimumHeight(30)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_timer.start)
        toolbar_layout.addWidget(self.search, 1)

        self.copy_button = IconButton.themed(
            "Copy details",
            rsm_icon=None,
            qss_fallback=":/qss_icons/dark/rc/copy.png",
            parent=toolbar,
        )
        self.copy_button.clicked.connect(self._copy_details)
        toolbar_layout.addWidget(self.copy_button)

        self.technical_button = IconButton.themed(
            "Show technical details",
            rsm_icon=None,
            qss_fallback=":/qss_icons/dark/rc/arrow_down.png",
            parent=toolbar,
        )
        self.technical_button.setCheckable(True)
        self.technical_button.setChecked(
            bool(get_preferences().get("errors/show_technical", False))
        )
        self.technical_button.setAccessibleName("Technical details")
        self.technical_button.toggled.connect(self._on_technical_toggled)
        toolbar_layout.addWidget(self.technical_button)
        layout.addWidget(toolbar)

        self.tree = QTreeWidget(panel)
        self.tree.setObjectName("ProblemsTree")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Node", "Code", "Problem"])
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree, 1)

        self.empty = EmptyStateLabel("No problems", panel)
        layout.addWidget(self.empty)
        self.setWidget(panel)

    # -- follow the active document ---------------------------------------
    def switch_to_design_window(self, window: TriggerSubWindow | None) -> None:
        old = self._store
        if old is not None:
            try:
                old.changed.disconnect(self._schedule_refresh)
            except (TypeError, RuntimeError):
                pass
        self._window = window
        self._store = getattr(window, "problems", None)
        if self._store is not None:
            self._store.changed.connect(self._schedule_refresh)
        self.refresh()

    def remove_design_window(self, window_id: str) -> None:
        if self._window is not None and str(id(self._window)) == window_id:
            self.switch_to_design_window(None)

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    def refresh(self) -> None:
        store = self._store
        entries = [error for _source, error in store.entries()] if store else []
        needle = self.search.text().strip().casefold()
        if needle:
            entries = [
                error
                for error in entries
                if needle
                in f"{error.render_summary()} {error.code} {error.detail}".casefold()
            ]
        self._entries = entries
        self.tree.clear()
        show_technical = self.technical_button.isChecked()
        manager = get_theme_manager()
        for error in entries:
            node_label = error.node_label or error.node_title or "Node"
            top = QTreeWidgetItem([node_label, error.code, error.title])
            top.setData(0, Qt.ItemDataRole.UserRole, error.node_id)
            top.setForeground(
                0,
                QColor(
                    manager.color(
                        "warning" if error.severity == "warning" else "danger",
                        "#e0686c",
                    )
                ),
            )
            top.setToolTip(2, error.render_tooltip())
            self.tree.addTopLevelItem(top)
            if error.detail:
                QTreeWidgetItem(top, ["", "", error.detail])
            if error.hint:
                QTreeWidgetItem(top, ["", "", f"Fix: {error.hint}"])
            for fix in error.suggested_fixes[1:]:
                QTreeWidgetItem(top, ["", "", f"Other fix: {fix.text}"])
            if error.culprit_node_id is not None:
                culprit = error.culprit_node_title or f"node {error.culprit_node_id}"
                QTreeWidgetItem(
                    top,
                    ["", "", f"Caused by: {culprit} (node {error.culprit_node_id})"],
                )
            if show_technical and (error.technical or error.traceback):
                QTreeWidgetItem(
                    top,
                    ["", "", error.render_text(include_technical=True)],
                )
            top.setExpanded(False)
        self.tree.setVisible(bool(entries))
        self.empty.setVisible(not entries)
        count = store.count(roots_only=True) if store else 0
        self.setWindowTitle(f"{_TITLE} ({count})" if count else _TITLE)

    def _on_technical_toggled(self, checked: bool) -> None:
        get_preferences().set("errors/show_technical", bool(checked))
        self.refresh()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        top = item
        while top.parent() is not None:
            top = top.parent()
        node_id = top.data(0, Qt.ItemDataRole.UserRole)
        if node_id is None or self._window is None:
            return
        node = next(
            (item for item in self._window.getAllNodes() if item.id == node_id),
            None,
        )
        if node is None:
            return
        self._window.scene.doDeselectItems()
        node.grNode.setSelected(True)
        view = self._window.scene.getView()
        if view is not None:
            view.centerOn(node.grNode)

    def _copy_details(self) -> None:
        selected: list[NodeError] = []
        seen: set[str] = set()
        for item in self.tree.selectedItems():
            top = item
            while top.parent() is not None:
                top = top.parent()
            node_id = top.data(0, Qt.ItemDataRole.UserRole)
            for error in self._entries:
                if error.node_id == node_id and error.fingerprint not in seen:
                    seen.add(error.fingerprint)
                    selected.append(error)
        targets = selected or self._entries
        text = "\n\n".join(
            error.render_text(include_technical=self.technical_button.isChecked())
            for error in targets
        )
        QGuiApplication.clipboard().setText(text)

    def apply_theme(self) -> None:
        self.refresh()
