from typing import Optional
from qtpy.QtCore import QObject

from PyQt6.QtCore import pyqtSignal as Signal


class SignalHandler(QObject):
    # Singleton instance
    _instance: Optional["SignalHandler"] = None
    sub_window_activated = Signal(str)

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance  # Return instance, not cls

    def __init__(self):
        super().__init__()
        if SignalHandler._instance is not None:
            raise Exception("This class is a singleton!")

        # Define signals as instance attributes

        SignalHandler._instance = self

    def emit_sub_window_activated(self, design_window_id: str) -> None:
        """Emit the sub_window_activated signal."""
        self.sub_window_activated.emit(design_window_id)
