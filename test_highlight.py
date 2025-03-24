from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
import sys
from src.trigger_designer.qt.widgets.formula_text_box import FormulaTextBox


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Formula Validator Test")
        self.setGeometry(100, 100, 800, 400)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.editor = FormulaTextBox()
        layout.addWidget(self.editor)

        # Set some test formulas - try these one at a time
        test_formulas = [
            "[FirstName] + [LastName",  # Missing closing bracket
            "IF [Age] > THEN 'Adult'",  # Missing condition value
            "[Age] BETWEEN 20 30",      # Missing AND
            "[Department] IN ('Sales', 'Marketing')"  # Valid formula
        ]

        # self.editor.setPlainText(test_formulas[-1])  # Try different indices


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
