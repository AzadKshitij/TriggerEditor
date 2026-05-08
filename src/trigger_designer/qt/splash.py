import math
from loguru import logger

from qtpy.QtCore import QRect, Qt
from qtpy.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from qtpy.QtWidgets import QSplashScreen, QWidget

from trigger_designer.core.constants import VERSION, VERSION_BRANCH
from trigger_designer.qt.resource_manager import ResourceManager


class Splash:
    """THe Custom Splash Screen widget for TriggerDesigner"""

    COPYRIGHT_YEARS: str = "2024-2025"
    COPYRIGHT_STR: str = f"© {COPYRIGHT_YEARS} Azad Kshitij"
    VERSION_STR: str = (
        f"Version {VERSION} {(' (' + VERSION_BRANCH + ')') if VERSION_BRANCH else ''}"
    )

    def __init__(
        self,
        resource_manager: ResourceManager,
        screen_width: int,
        splash_name: str,
        device_ratio: float = 1,
    ) -> None:
        self.rm = resource_manager
        self.screen_width = screen_width
        self.ratio: float = device_ratio
        self.splash_screen: QSplashScreen | None = None
        self.splash_name: str = splash_name

    def get_pixmap(self) -> QPixmap:
        """Get the pixmap used for the splash screen."""
        pixmap: QPixmap | None = self.rm.get(f"{self.splash_name}")
        if not pixmap:
            logger.error(f"[Splash] Splash screen not found: {self.splash_name}")
            pixmap = QPixmap(960, 540)
            pixmap.fill(QColor("black"))
        painter = QPainter(pixmap)
        point_size_scale: float = 1.0
        match painter.font().family():
            case "Segoe UI":
                point_size_scale = 0.75

        # Copyright
        font = painter.font()
        font.setPointSize(math.floor(22 * point_size_scale))
        painter.setFont(font)
        pen = QPen(QColor("#9782ff"))
        painter.setPen(pen)
        painter.drawText(
            QRect(0, -50, 960, 540),
            int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
            Splash.COPYRIGHT_STR,
        )
        # Version
        pen = QPen(QColor("#809782ff"))
        painter.setPen(pen)
        painter.drawText(
            QRect(0, -25, 960, 540),
            int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
            Splash.VERSION_STR,
        )

        pixmap.setDevicePixelRatio(self.ratio)
        pixmap = pixmap.scaledToWidth(
            math.floor(
                min(
                    (self.screen_width * self.ratio) / 4,
                    pixmap.width(),
                )
            ),
            Qt.TransformationMode.SmoothTransformation,
        )

        return pixmap

    def _build_splash_screen(self) -> None:
        """Build the internal splash screen."""
        self.splash_screen = QSplashScreen(
            self.get_pixmap(), Qt.WindowType.WindowStaysOnTopHint
        )

    def show(self) -> None:
        """Show the splash screen."""
        if not self.splash_screen:
            self._build_splash_screen()
        if self.splash_screen:
            self.splash_screen.show()

    def finish(self, widget: QWidget) -> None:
        """Hide the splash screen with this widget is finished displaying."""
        if self.splash_screen:
            self.splash_screen.finish(widget)
