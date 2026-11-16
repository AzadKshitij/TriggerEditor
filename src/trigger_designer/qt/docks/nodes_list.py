from qtpy.QtCore import QEvent, QTimer
from qtpy.QtGui import QShowEvent
from qtpy.QtWidgets import QDockWidget, QTabWidget, QWidget, QVBoxLayout, QSizePolicy
from trigger_designer.core.node_configuration import NodeTypes
from trigger_designer.qt.widgets.node_drag_listbox import QTRDragListbox
from typing import Optional

#: Height cap tuned to the compact tab bar of the QSS themes. A style with a
#: taller tab bar leaves the lists too short for their rows; _fit_height()
#: raises the cap by exactly that shortfall and never lowers it past this.
BASE_HEIGHT = 105


class NodesDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.initUI()
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setTitleBarWidget(QWidget())
        self.setFloating(False)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        # self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def initUI(self) -> None:
        # Create the tab widget
        tab_widget = QTabWidget()
        tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Create the tabs and drag list boxes dynamically
        tabs = {}
        drag_list_boxes = {}

        # Iterate through the NodeTypes enum
        for node_type in NodeTypes:
            tab = QWidget()
            list_widget = QTRDragListbox(node_type=node_type)
            list_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            tab_layout = QVBoxLayout()
            tab_layout.addWidget(list_widget)
            tab.setLayout(tab_layout)

            tabs[node_type] = tab
            drag_list_boxes[node_type] = list_widget

            # Use the enum member name as the tab name (you might want to customize this)
            tab_widget.addTab(tab, node_type.value.title())

        self._tab_widget = tab_widget
        self._lists = list(drag_list_boxes.values())
        self.setWidget(tab_widget)
        tab_widget.setMaximumHeight(BASE_HEIGHT)
        self.adjustSize()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self, self._fit_height)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.StyleChange and self.isVisible():
            QTimer.singleShot(0, self, self._fit_height)

    def _fit_height(self) -> None:
        """Make the height cap leave the visible list exactly one row tall.

        A positive slack means the list is taller than its rows need (after a
        switch back to a compact style); a negative one clips the rows.
        Measured on the live layout, so it is re-run once the cap changed.
        """
        tab_widget = self._tab_widget
        rows = [
            (lb.viewport().height(), lb.item(0).sizeHint().height())
            for lb in self._lists
            if lb.isVisible() and lb.count()
        ]
        if not rows:
            return
        slack = min(viewport - row for viewport, row in rows)
        cap = max(BASE_HEIGHT, tab_widget.maximumHeight() - slack)
        if cap != tab_widget.maximumHeight():
            tab_widget.setMaximumHeight(cap)
            QTimer.singleShot(0, self, self._fit_height)
