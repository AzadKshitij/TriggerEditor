"""Standalone Data Preview window (alt-click on a node output socket).

Thin host: all rendering and worker handling lives in `DataPreviewPanel`,
which is the same surface the Data Preview dock embeds.
"""

from typing import Any

from qtpy.QtWidgets import QMainWindow, QWidget

from trigger_designer.qt.widgets.data_preview_panel import DataPreviewPanel


class DataPreviewWindow(QMainWindow):
    """A plain window around a `DataPreviewPanel`."""

    def __init__(
        self,
        data: Any,
        title: str = "Data Preview",
        parent: QWidget | None = None,
        max_rows: int = 1000,
        max_size_mb: float = 2.0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1200, 800)
        self.panel = DataPreviewPanel(self, max_rows=max_rows, max_size_mb=max_size_mb)
        self.setCentralWidget(self.panel)
        self.panel.set_source(data)
