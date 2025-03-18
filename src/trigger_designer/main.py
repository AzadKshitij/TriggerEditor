import os
import sys
from qtpy.QtWidgets import QApplication, QStyleFactory, QMainWindow, QLabel, QWidget, QVBoxLayout, QPushButton
from qtpy.QtCore import QResource, Qt
from qtpy.QtGui import QIcon, QPalette, QColor
import qdarkstyle


from trigger_window import TriggerWindow
from test_style import StyleTestWindow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dark_stylesheet = qdarkstyle.load_stylesheet()

    app.setStyleSheet(dark_stylesheet)
    app.setStyle('Fusion')

    test_window = StyleTestWindow()
    test_window.show()

    wnd = TriggerWindow()
    wnd.show()

    sys.exit(app.exec_())
