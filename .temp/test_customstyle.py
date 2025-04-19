import sys
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QPushButton, QWidget
from PyQt6.QtCore import pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QPainter


class ColorGridWidget(QWidget):
    gridColorLightChanged = pyqtSignal()
    gridColorDarkChanged = pyqtSignal()
    backgroundColorChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gridColorLight = QColor("#dddddd")
        self._gridColorDark = QColor("#999999")
        self._backgroundColor = QColor("#ffffff")

    def getGridColorLight(self): return self._gridColorLight

    def setGridColorLight(self, value):
        if self._gridColorLight != value:
            self._gridColorLight = value
            self.gridColorLightChanged.emit()
            self.update()

    def getGridColorDark(self): return self._gridColorDark

    def setGridColorDark(self, value):
        if self._gridColorDark != value:
            self._gridColorDark = value
            self.gridColorDarkChanged.emit()
            self.update()

    def getBackgroundColor(self): return self._backgroundColor

    def setBackgroundColor(self, value):
        if self._backgroundColor != value:
            self._backgroundColor = value
            self.backgroundColorChanged.emit()
            self.update()

    gridColorLight = pyqtProperty(
        QColor, fget=getGridColorLight, fset=setGridColorLight, notify=gridColorLightChanged)
    gridColorDark = pyqtProperty(
        QColor, fget=getGridColorDark, fset=setGridColorDark, notify=gridColorDarkChanged)
    backgroundColor = pyqtProperty(
        QColor, fget=getBackgroundColor, fset=setBackgroundColor, notify=backgroundColorChanged)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._backgroundColor)

        width = self.width()
        height = self.height()

        painter.setPen(self._gridColorLight)
        for x in range(0, width, 20):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, 20):
            painter.drawLine(0, y, width, y)

        painter.setPen(self._gridColorDark)
        for x in range(0, width, 100):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, 100):
            painter.drawLine(0, y, width, y)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.grid = ColorGridWidget()
        button = QPushButton("Apply Light Theme")
        button.clicked.connect(self.apply_light_theme)

        layout = QVBoxLayout()
        layout.addWidget(self.grid)
        layout.addWidget(button)
        self.setLayout(layout)

        self.setMinimumSize(400, 300)

        self.apply_dark_theme()  # start with a theme

    def apply_dark_theme(self):
        self.setStyleSheet("""
            ColorGridWidget {
                qproperty-gridColorLight: #f3f3f3;
                qproperty-gridColorDark: #cccccc;
                qproperty-backgroundColor: #111111;
            }
        """)

    def apply_light_theme(self):
        self.setStyleSheet("""
            ColorGridWidget {
                qproperty-gridColorLight: #f3f3f3;
                qproperty-gridColorDark: #cccccc;
                qproperty-backgroundColor: #ffffff;
            }
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("qproperty Styling via QSS")
    window.show()
    sys.exit(app.exec())
