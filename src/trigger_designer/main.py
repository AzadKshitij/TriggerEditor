import os
import sys
from qtpy.QtWidgets import QApplication, QStyleFactory, QMainWindow, QLabel, QWidget, QVBoxLayout, QPushButton
from qtpy.QtCore import QResource, Qt
from qtpy.QtGui import QIcon, QPalette, QColor, QGuiApplication
from loguru import logger

from trigger_designer.qt import main_window
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.splash import Splash

logger = logger.bind()
logger.level('DEBUG')
logger.debug("Running Trigger Designer!")

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# To make sure we load after registering src directory
s = True
if s:
    from trigger_designer.qt.main_window import TriggerWindow
    from trigger_designer.test_style import StyleTestWindow

# sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


if __name__ == '__main__':
    rsm: ResourceManager = ResourceManager()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("trigger designer")
    app.setApplicationDisplayName("Trigger Designer")

    splash: Splash = Splash(
        resource_manager=rsm,
        screen_width=QGuiApplication.primaryScreen().geometry().width(),
        splash_name="splash_screen",
        device_ratio=app.devicePixelRatio()
    )

    splash.show()

    test_window = StyleTestWindow()
    trigger_window = TriggerWindow()

    trigger_window.show()
    trigger_window.activateWindow()

    splash.finish(trigger_window)

    sys.exit(app.exec_())
