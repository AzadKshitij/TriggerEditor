"""
Test and demonstration of the SQL Formula Editor Widget

Run this script to test the SQL formula editor with various features:
- Syntax highlighting
- Error detection
- Line numbers
- Auto-completion hints
"""

import sys
import os

# Add the parent directory to the path to import the widget
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qtpy.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QHBoxLayout
from qtpy.QtCore import Qt
from sql_formula_editor import SQLFormulaWidget


class SQLEditorTestWindow(QMainWindow):
    """Test window for the SQL Formula Editor."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQL Formula Editor - Test Application")
        self.setGeometry(100, 100, 1000, 700)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QLabel {
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:pressed {
                background-color: #2c2c2c;
            }
        """)
        
        self.setup_ui()
        self.setup_test_data()
    
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("SQL Formula Editor with Syntax Highlighting & Error Detection")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; margin: 10px;")
        layout.addWidget(title)
        
        # SQL Formula Widget
        self.sql_widget = SQLFormulaWidget()
        layout.addWidget(self.sql_widget)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.test_valid_button = QPushButton("Load Valid SQL")
        self.test_error_button = QPushButton("Load SQL with Errors")
        self.test_complex_button = QPushButton("Load Complex Example")
        self.clear_button = QPushButton("Clear")
        
        button_layout.addWidget(self.test_valid_button)
        button_layout.addWidget(self.test_error_button)
        button_layout.addWidget(self.test_complex_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("Ready - Type or load example SQL formulas")
        self.status_label.setStyleSheet("color: #888888; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Connect signals
        self.test_valid_button.clicked.connect(self.load_valid_sql)
        self.test_error_button.clicked.connect(self.load_error_sql)
        self.test_complex_button.clicked.connect(self.load_complex_sql)
        self.clear_button.clicked.connect(self.clear_editor)
        
        self.sql_widget.formulaChanged.connect(self.on_formula_changed)
        self.sql_widget.editor.errorDetected.connect(self.on_error_detected)
    
    def setup_test_data(self):
        """Set up test column names for validation."""
        sample_columns = [
            'customer_id', 'customer_name', 'age', 'email', 'phone',
            'salary', 'department', 'hire_date', 'is_active', 'city',
            'state', 'country', 'order_total', 'last_login', 'score'
        ]
        self.sql_widget.set_column_names(sample_columns)
    
    def load_valid_sql(self):
        """Load a valid SQL formula example."""
        valid_sql = """CASE 
    WHEN [age] >= 65 THEN 'Senior Citizen'
    WHEN [age] >= 18 THEN 'Adult'
    ELSE 'Minor'
END"""
        self.sql_widget.set_text(valid_sql)
        self.status_label.setText("Loaded valid SQL example")
    
    def load_error_sql(self):
        """Load SQL with intentional errors for testing."""
        error_sql = """CASE 
    WHEN [age] >= 65 THEN 'Senior Citizen
    WHEN [unknown_column] >= 18 THEN 'Adult'
    WHEN ([salary > 50000 THEN 'High Earner'
    ELSE 'Other'"""
        self.sql_widget.set_text(error_sql)
        self.status_label.setText("Loaded SQL with errors - check the red underlines")
    
    def load_complex_sql(self):
        """Load a complex SQL formula example."""
        complex_sql = """CASE 
    WHEN [department] = 'Sales' AND [salary] > 75000 THEN 'Senior Sales Rep'
    WHEN [department] = 'Engineering' AND [salary] > 90000 THEN 'Senior Engineer' 
    WHEN [hire_date] < '2020-01-01' AND [is_active] = true THEN 'Veteran Employee'
    WHEN [age] > 50 AND [salary] < 40000 THEN 'Underpaid Senior'
    WHEN UPPER([city]) = 'NEW YORK' OR UPPER([city]) = 'SAN FRANCISCO' THEN 'High Cost Area'
    ELSE 'Standard Employee'
END"""
        self.sql_widget.set_text(complex_sql)
        self.status_label.setText("Loaded complex SQL example with multiple conditions")
    
    def clear_editor(self):
        """Clear the editor content."""
        self.sql_widget.set_text("")
        self.sql_widget.clear_errors()
        self.status_label.setText("Editor cleared")
    
    def on_formula_changed(self, formula: str):
        """Handle formula changes."""
        if formula.strip():
            self.status_label.setText(f"Formula length: {len(formula)} characters")
        else:
            self.status_label.setText("Ready - Type or load example SQL formulas")
    
    def on_error_detected(self, message: str, line: int, column: int):
        """Handle error detection."""
        self.status_label.setText(f"Error detected - Line {line}: {message}")


def main():
    """Main function to run the test application."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("SQL Formula Editor Test")
    app.setApplicationVersion("1.0")
    
    # Create and show the main window
    window = SQLEditorTestWindow()
    window.show()
    
    # Load a default example
    window.load_valid_sql()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
