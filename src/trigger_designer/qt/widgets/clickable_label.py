# Copyright (C) 2025 Kshitij Azad
# Licensed under the GPL-3.0 License.
# Created for TriggerDesigner: A tool for data processing
# URL: https://github.com/AzadKshitij/TriggerEditor


from qtpy.QtCore import Signal
from qtpy.QtWidgets import QLabel


class ClickableLabel(QLabel):
    """A clickable Label widget."""

    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit()
