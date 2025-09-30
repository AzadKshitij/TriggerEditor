# SQL Formula Editor Widget

A comprehensive SQL formula editing widget for the TriggerEditor with advanced features including syntax highlighting, error detection, and real-time validation.

## Features

### 🎨 Syntax Highlighting
- **SQL Keywords**: `SELECT`, `FROM`, `WHERE`, `CASE`, `WHEN`, `THEN`, `ELSE`, `END`, etc.
- **String Literals**: Single-quoted strings highlighted in orange
- **Numeric Values**: Numbers highlighted in light green  
- **Column References**: `[column_name]` highlighted in light blue
- **Functions**: Function names highlighted in yellow
- **Comments**: `-- comments` highlighted in green

### ❌ Error Detection
- **Real-time Validation**: Errors detected 500ms after typing stops
- **Visual Indicators**: Red wavy underlines for errors
- **Error Messages**: Detailed error descriptions with line/column info
- **Common Validations**:
  - Unmatched quotes and parentheses
  - Missing END keywords in CASE statements
  - Invalid column references
  - Syntax errors

### 📝 Enhanced Editing
- **Line Numbers**: Professional code editor experience
- **Current Line Highlighting**: Active line highlighted for visibility
- **Auto-indentation**: Smart indentation on new lines
- **Dark Theme**: Optimized for dark development environments
- **Bracket Matching**: Visual bracket pair highlighting

## Usage

### Basic Usage

```python
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaWidget

# Create the widget
formula_editor = SQLFormulaWidget()

# Set available column names for validation
column_names = ['customer_id', 'name', 'age', 'email', 'salary']
formula_editor.set_column_names(column_names)

# Set initial formula text
formula_editor.set_text("""
CASE 
    WHEN [age] > 65 THEN 'Senior'
    WHEN [age] > 30 THEN 'Adult' 
    ELSE 'Young'
END
""")

# Get current formula text
formula = formula_editor.get_text()

# Connect to signals
formula_editor.formulaChanged.connect(on_formula_changed)
formula_editor.editor.errorDetected.connect(on_error_detected)
```

### Advanced Editor Usage

```python
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaEditor

# Create standalone editor
editor = SQLFormulaEditor()

# Set column names for validation and highlighting
editor.set_column_names(['col1', 'col2', 'col3'])

# Connect to signals
editor.textChanged.connect(on_text_changed)
editor.errorDetected.connect(on_error_detected)

def on_error_detected(message, line, column):
    print(f"Error at line {line}, column {column}: {message}")
```

## Integration with Formula Node

To integrate into the existing formula.py file:

### 1. Update Imports

```python
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaWidget
```

### 2. Replace QTextEdit with SQLFormulaWidget

```python
# OLD CODE:
# self.formula_input = QTextEdit()
# self.formula_input.setPlaceholderText("Enter formula...")

# NEW CODE:
self.formula_input = SQLFormulaWidget() 
self.formula_input.set_column_names(list(self.incom_data.columns))
```

### 3. Update Method Calls

```python
# OLD: self.formula_input.toPlainText()
# NEW: self.formula_input.get_text()

# OLD: self.formula_input.setPlainText(text)
# NEW: self.formula_input.set_text(text)

# OLD: self.formula_input.textChanged.connect(...)
# NEW: self.formula_input.formulaChanged.connect(...)
```

### 4. Add Error Handling (Optional)

```python
def on_formula_error(self, message, line, column):
    """Handle SQL formula errors."""
    self.node.grNode.setToolTip(f"Formula Error: {message}")
    
# Connect the signal
self.formula_input.editor.errorDetected.connect(self.on_formula_error)
```

## Testing

Run the test application to see all features in action:

```bash
python test_sql_editor.py
```

This will open a demo window with:
- Sample SQL formulas
- Error detection examples  
- Syntax highlighting demonstration
- Interactive testing buttons

## Technical Details

### Components

1. **SQLSyntaxHighlighter**: Handles syntax highlighting using QSyntaxHighlighter
2. **LineNumberArea**: Displays line numbers alongside the editor
3. **SQLFormulaEditor**: Core editor widget with all advanced features
4. **SQLFormulaWidget**: Complete widget with editor + error display

### Error Detection

The widget performs several types of validation:

- **Syntax Validation**: Checks for basic SQL syntax errors
- **Quote Matching**: Ensures all quotes are properly closed
- **Parentheses Matching**: Validates balanced parentheses
- **Column Validation**: Verifies column references against provided column list
- **CASE Statement Validation**: Ensures CASE statements have corresponding END

### Customization

The widget can be customized by:

- Modifying color schemes in the highlighter
- Adding new validation rules
- Extending syntax highlighting rules
- Customizing error message formatting

## Dependencies

- QtPy (Qt abstraction layer)
- Python 3.7+
- Qt5/Qt6 (via QtPy)

## Future Enhancements

Potential improvements:
- Auto-completion dropdown for SQL keywords and column names
- Code folding for complex CASE statements  
- SQL formatting/beautification
- Integration with SQL parsing libraries for advanced validation
- Customizable themes and color schemes
