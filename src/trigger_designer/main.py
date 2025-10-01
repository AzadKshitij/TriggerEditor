"""Main entry point for Trigger Designer application."""

import os
import sys
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import QResource, Qt, QSettings
from qtpy.QtGui import QIcon, QPalette, QColor, QGuiApplication, QScreen
from loguru import logger

from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.splash import Splash
import trigger_designer.qt.darkstyle_rc  # noqa
import trigger_designer.resources.icons_rc  # noqa
from typing import Optional

# Configure logger
logger = logger.bind()
logger.level("DEBUG")

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
    # app: QApplication = QApplication(sys.argv)
    file_path: Optional[str] = sys.argv[1] if len(sys.argv) > 1 else None

    logger.info("Starting Trigger Designer...")
    logger.info(f"System arguments: {sys.argv}")
    
    # Initialize application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Get file path from command line arguments
    file_path: Optional[str] = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Application configuration
    name_company = "Trigger"
    name_product = "Trigger Designer"
    app.setApplicationName(name_company)
    app.setApplicationDisplayName(name_product)
    
    # Initialize resource manager and set up application
    resource_manager = ResourceManager()
    app.setWindowIcon(QIcon(str(resource_manager.get_full_path("app_icon"))))
    
    # Load settings and theme
    settings = QSettings(name_company, name_product)
    logger.debug(f"Available settings keys: {settings.allKeys()}")
    
    theme_qss = resource_manager.load_theme(settings.value("theme", "dark"))
    if theme_qss:
        app.setStyleSheet(theme_qss)
    
    # Get screen dimensions for splash screen
    primary_screen: Optional[QScreen] = QGuiApplication.primaryScreen()
    screen_width = primary_screen.geometry().width() if primary_screen else 800
    
    # Show splash screen
    splash = Splash(
        resource_manager=resource_manager,
        screen_width=screen_width,
        splash_name="splash_screen",
        device_ratio=app.devicePixelRatio(),
    )
    splash.show()
    
    # Create and show main window
    main_window = TriggerWindow(
        file_path=file_path,
        name_company=name_company,
        name_product=name_product,
    )
    main_window.show()
    main_window.activateWindow()
    
    # Hide splash screen
    splash.finish(main_window)
    
    logger.info("Trigger Designer started successfully")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
