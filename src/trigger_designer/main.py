import os
import sys
from qtpy.QtWidgets import QApplication, QStyleFactory, QMainWindow, QLabel, QWidget, QVBoxLayout, QPushButton
from qtpy.QtCore import QResource, Qt, QSettings
from qtpy.QtGui import QIcon, QPalette, QColor, QGuiApplication, QScreen
from loguru import logger

from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.splash import Splash
import trigger_designer.qt.darkstyle_rc  # noqa
import trigger_designer.resources.icons_rc  # noqa
from typing import TYPE_CHECKING, Optional, Union


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


def main() -> None:
    rsm: ResourceManager = ResourceManager()
    app: QApplication = QApplication(sys.argv)
    file_path: Optional[str] = sys.argv[1] if len(sys.argv) > 1 else None

    logger.info("Starting Trigger Designer...")
    logger.info(f"System arguments:{sys.argv}")

    app.setStyle('Fusion')

    name_company = "Trigger"
    name_product = "Trigger Designer"
    app.setApplicationName(name_company)
    app.setApplicationDisplayName(name_product)
    app.setWindowIcon(QIcon(str(rsm.get_full_path("app_icon"))))

    settings: QSettings = QSettings(name_company, name_product)
    print("🐍 File: trigger_designer/main.py | Line: 48 | main ~ settings",
          settings.allKeys())

    theme_qss = rsm.load_theme(settings.value('theme', 'dark'))
    # theme_qss = None

    if theme_qss:
        app.setStyleSheet(theme_qss)

    # Fix for QScreen geometry access
    primary_screen: Optional[QScreen] = QGuiApplication.primaryScreen()
    screen_width: int = primary_screen.geometry().width(
    ) if primary_screen else 800  # fallback width

    splash: Splash = Splash(
        resource_manager=rsm,
        screen_width=screen_width,
        splash_name="splash_screen",
        device_ratio=app.devicePixelRatio()
    )
    splash.show()

    # test_window = StyleTestWindow()
    trigger_window: TriggerWindow = TriggerWindow(
        file_path=file_path, name_company=name_company, name_product=name_product)

    trigger_window.show()
    trigger_window.activateWindow()

    splash.finish(trigger_window)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
