from PyQt6.QtWidgets import QApplication, QMainWindow
import sys
from src.trigger_designer.qt.widgets.formula_text_box import FormulaTextBox


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.formula_box = FormulaTextBox()
        self.setCentralWidget(self.formula_box)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
