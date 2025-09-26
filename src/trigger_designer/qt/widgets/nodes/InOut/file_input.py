import polars as pl
import os
import fastexcel
from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLayout,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QCheckBox,
    QDialog,
    QListWidget,
    QDialogButtonBox,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.core.node_configuration import register_node, IONodes, NodeTypes
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils_no_qt import dumpException
from loguru import logger
from typing import Any, Optional, OrderedDict, TYPE_CHECKING, Type, TypeVar, Union, cast


if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    from trigger_designer.qt.node_base import TriggerNode
    from nodeeditor.node_node import Node


class FileInputContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        """Initialize the FileInputContent widget.

        Args:
            node (TriggerNode): The node this content belongs to
            parent (Optional[QWidget], optional): Parent widget. Defaults to None.
        """
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)
        # local Variables
        self.history = self.node.scene.history
        self.filePath = ""
        self.preview_rows = (
            10  # Reduce to just 3 rows for absolute minimal memory usage
        )
        self.node = node
        self.file_type = "csv"  # Default file type

        # New properties for the enhanced functionality
        self.record_limit = 0  # 0 means no limit
        self.output_filename_as_field = False
        self.delimiter = ","  # Default delimiter for CSV/TXT files
        self.first_row_contains_field_names = True
        self.selected_sheet = ""  # For Excel files
        self.available_sheets = []  # List of all available sheets
        self.start_row = 1  # Row to start reading from (1-based)

        # pass on variables
        self.data: pl.DataFrame = pl.DataFrame()
        self.variable_name = f"var_file_input_{self.id}"

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, _icon: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:

        # File path input (top)
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setPlaceholderText("Enter file path")
        self.filePathEdit.textChanged.connect(self._on_filePathEdit_textChanged)
        self.registerInputWidget(self.filePathEdit)
        dock_layout.addWidget(self.filePathEdit)

        # Load button (top)
        self.loadButton = QPushButton("Load File", self)
        self.loadButton.clicked.connect(self.openFileDialog)
        dock_layout.addWidget(self.loadButton)

        # Settings form layout
        from qtpy.QtWidgets import QFormLayout

        # Create a widget to hold the settings form (so we can hide the entire section)
        self.settings_widget = QWidget()
        settings_form = QFormLayout()
        self.settings_widget.setLayout(settings_form)

        # Record Limit
        self.recordLimitSpinBox = QSpinBox(self)
        self.recordLimitSpinBox.setMinimum(0)
        self.recordLimitSpinBox.setMaximum(999999999)
        self.recordLimitSpinBox.setValue(self.record_limit)
        self.recordLimitSpinBox.setSpecialValueText("No Limit")
        self.recordLimitSpinBox.valueChanged.connect(self._on_record_limit_changed)
        self.registerInputWidget(self.recordLimitSpinBox)
        settings_form.addRow(QLabel("Record Limit:"), self.recordLimitSpinBox)
        self.record_limit_widget = self.recordLimitSpinBox

        # Output Filename as Field
        self.outputFilenameCheckBox = QCheckBox()
        self.outputFilenameCheckBox.setChecked(self.output_filename_as_field)
        self.outputFilenameCheckBox.toggled.connect(self._on_output_filename_changed)
        self.registerInputWidget(self.outputFilenameCheckBox)
        settings_form.addRow(
            QLabel("Output Filename as Field"), self.outputFilenameCheckBox
        )
        self.output_filename_widget = self.outputFilenameCheckBox

        # Delimiter (for CSV/TXT files)
        self.delimiterEdit = QLineEdit(self)
        self.delimiterEdit.setText(self.delimiter)
        self.delimiterEdit.setPlaceholderText("e.g., , ; | \\t")
        self.delimiterEdit.textChanged.connect(self._on_delimiter_changed)
        self.registerInputWidget(self.delimiterEdit)
        settings_form.addRow(QLabel("Delimiter:"), self.delimiterEdit)
        self.delimiter_widget = self.delimiterEdit

        # First Row Contains Field Names
        self.firstRowFieldNamesCheckBox = QCheckBox()
        self.firstRowFieldNamesCheckBox.setChecked(self.first_row_contains_field_names)
        self.firstRowFieldNamesCheckBox.toggled.connect(
            self._on_first_row_field_names_changed
        )
        self.registerInputWidget(self.firstRowFieldNamesCheckBox)
        settings_form.addRow(
            QLabel("First Row Contains Field Names"), self.firstRowFieldNamesCheckBox
        )
        self.first_row_widget = self.firstRowFieldNamesCheckBox

        # Selected Sheet (for Excel files)
        self.selectedSheetCombo = QComboBox(self)
        self.selectedSheetCombo.currentTextChanged.connect(
            self._on_selected_sheet_changed
        )
        self.registerInputWidget(self.selectedSheetCombo)
        settings_form.addRow(QLabel("Selected Sheet:"), self.selectedSheetCombo)
        self.selected_sheet_widget = self.selectedSheetCombo

        # Start Row (for Excel files)
        self.startRowSpinBox = QSpinBox(self)
        self.startRowSpinBox.setMinimum(1)
        self.startRowSpinBox.setMaximum(999999)
        self.startRowSpinBox.setValue(self.start_row)
        self.startRowSpinBox.valueChanged.connect(self._on_start_row_changed)
        self.registerInputWidget(self.startRowSpinBox)
        settings_form.addRow(QLabel("Start Row:"), self.startRowSpinBox)
        self.start_row_widget = self.startRowSpinBox

        # Add the settings widget to the main layout
        dock_layout.addWidget(self.settings_widget)

        # Table widget for preview
        self.tableWidget = QTableWidget(self)
        dock_layout.addWidget(self.tableWidget)

        # Initially hide all options until a file is selected
        self._hide_all_options()
        if self.filePath:
            self.filePathEdit.setText(self.filePath)
            file_type = self._auto_detect_file_type(self.filePath)
            self._update_ui_visibility(file_type)
            if self.data.is_empty() or self.data.is_null() or self.data is None:
                self.loadFile(self.filePath)

    def _on_filePathEdit_textChanged(self) -> None:
        self.filePath = self.filePathEdit.text()
        if not self.filePath:
            # Hide all options when file path is cleared
            self._hide_all_options()
        self.evaluate.emit()

    def _on_record_limit_changed(self, value: int) -> None:
        self.record_limit = value
        self.evaluate.emit()

    def _on_output_filename_changed(self, checked: bool) -> None:
        self.output_filename_as_field = checked
        self.evaluate.emit()

    def _on_delimiter_changed(self) -> None:
        delimiter_text = self.delimiterEdit.text()
        # Handle special cases like \t for tab
        if delimiter_text == "\\t":
            self.delimiter = "\t"
        elif delimiter_text == "\\n":
            self.delimiter = "\n"
        elif delimiter_text == "\\r":
            self.delimiter = "\r"
        else:
            self.delimiter = delimiter_text
        self.evaluate.emit()

    def _on_first_row_field_names_changed(self, checked: bool) -> None:
        self.first_row_contains_field_names = checked
        self.evaluate.emit()

    def _on_selected_sheet_changed(self, sheet_name: str) -> None:
        if sheet_name and sheet_name != self.selected_sheet:
            self.selected_sheet = sheet_name
            logger.info(f"Selected sheet changed to: {sheet_name}")
            # Reload data with new sheet
            if self.filePath:
                self.loadFile(self.filePath)
            self.evaluate.emit()

    def _on_start_row_changed(self, value: int) -> None:
        self.start_row = value
        logger.info(f"Start row changed to: {value}")
        # Reload data with new start row
        if self.filePath:
            self.loadFile(self.filePath)
        self.evaluate.emit()

    def check_file_path(self) -> bool:
        if not self.filePath:
            return False
        # self.evaluate.emit()

        # Check if the file exists
        if not os.path.exists(self.filePath):
            print(f"Error: File '{self.filePath}' does not exist.")
            self.node.grNode.setToolTip("File does not exist")
            self.node.markInvalid(True)
            return False
        else:
            print(f"File '{self.filePath}' exists.")
            self.node.grNode.setToolTip("")
            self.node.markInvalid(False)

        self.loadFile(self.filePath)
        return True

    def openFileDialog(self) -> None:
        """Open file dialog with support for multiple file types"""
        options = QFileDialog.Options()
        file_filters = (
            "All Supported Files (*.csv *.txt *.xlsx *.xls);;"
            "CSV Files (*.csv);;"
            "Text Files (*.txt);;"
            "Excel Files (*.xlsx *.xls);;"
            "All Files (*)"
        )
        fileName, _ = QFileDialog.getOpenFileName(
            self.parent(), "Open Data File", "", file_filters, options=options
        )
        if fileName:
            # Clear existing data first to free memory
            if hasattr(self, "data") and self.data is not None:
                del self.data
                self.data = None

            self.filePath = fileName
            self.filePathEdit.setText(fileName)

            # Auto-detect file type and handle Excel sheet selection
            file_type = self._auto_detect_file_type(fileName)

            if file_type == "excel":
                # Show sheet selection dialog for Excel files
                self._show_sheet_selection_dialog(fileName)
            else:
                # Update UI visibility for non-Excel files
                self._update_ui_visibility(file_type)

            self.evaluate.emit()
        else:
            # No file selected, hide all options
            self.filePath = ""
            self.filePathEdit.setText("")
            self._hide_all_options()

    def _auto_detect_file_type(self, fileName: str) -> str:
        """Auto-detect file type based on file extension"""
        extension = os.path.splitext(fileName)[1].lower()
        if extension in [".xlsx", ".xls"]:
            file_type = "excel"
        elif extension == ".txt":
            file_type = "txt"
        else:  # .csv or others default to CSV
            file_type = "csv"

        self.file_type = file_type
        return file_type

    def _show_sheet_selection_dialog(self, fileName: str) -> None:
        """Get available sheets and set up the dropdown"""
        try:
            # Get available sheet names using fastexcel
            import fastexcel

            try:
                # Use fastexcel to read Excel file and get sheet names
                reader = fastexcel.read_excel(fileName)
                self.available_sheets = reader.sheet_names
                logger.info(
                    f"Found sheet names using fastexcel: {self.available_sheets}"
                )

                # Set the first sheet as default if no sheet is selected
                if not self.selected_sheet and self.available_sheets:
                    self.selected_sheet = self.available_sheets[0]

                # Update UI to show Excel options
                self._update_ui_visibility("excel")

            except Exception as e:
                logger.error(f"fastexcel failed to read Excel file {fileName}: {e}")
                # Reset file selection on error
                self.filePath = ""
                self.filePathEdit.setText("")
                self._hide_all_options()

        except Exception as e:
            logger.error(f"Error reading Excel file for sheet selection: {e}")
            # Reset file selection on error
            self.filePath = ""
            self.filePathEdit.setText("")
            self._hide_all_options()

    def _hide_all_options(self) -> None:
        # Hide the entire settings widget when no file is loaded
        if hasattr(self, "settings_widget"):
            self.settings_widget.setVisible(False)

    def _update_ui_visibility(self, file_type: str) -> None:
        """Update UI element visibility based on file type"""
        # Show the settings widget when a file is loaded
        if hasattr(self, "settings_widget"):
            self.settings_widget.setVisible(True)

        # Show common options for all file types
        if hasattr(self, "record_limit_widget"):
            self.record_limit_widget.setVisible(True)
        if hasattr(self, "output_filename_widget"):
            self.output_filename_widget.setVisible(True)
        if hasattr(self, "first_row_widget"):
            self.first_row_widget.setVisible(True)

        # Delimiter: only for CSV/TXT
        if hasattr(self, "delimiter_widget"):
            self.delimiter_widget.setVisible(file_type in ["csv", "txt"])

        # Selected Sheet: only for Excel - need to hide both label and widget
        if hasattr(self, "selected_sheet_widget"):
            is_excel = file_type == "excel"
            self.selected_sheet_widget.setVisible(is_excel)
            # Also hide the label by finding it in the form layout
            if hasattr(self, "settings_widget") and self.settings_widget.layout():
                form_layout = self.settings_widget.layout()
                for i in range(form_layout.rowCount()):
                    label_item = form_layout.itemAt(i, form_layout.LabelRole)
                    field_item = form_layout.itemAt(i, form_layout.FieldRole)
                    if field_item and field_item.widget() == self.selected_sheet_widget:
                        if label_item and label_item.widget():
                            label_item.widget().setVisible(is_excel)
                        break

            if file_type == "excel" and hasattr(self, "selectedSheetCombo"):
                self.selectedSheetCombo.clear()
                if self.available_sheets:
                    self.selectedSheetCombo.addItems(self.available_sheets)
                    if self.selected_sheet in self.available_sheets:
                        self.selectedSheetCombo.setCurrentText(self.selected_sheet)

        # Start Row: only for Excel - need to hide both label and widget
        if hasattr(self, "start_row_widget"):
            is_excel = file_type == "excel"
            self.start_row_widget.setVisible(is_excel)
            # Also hide the label by finding it in the form layout
            if hasattr(self, "settings_widget") and self.settings_widget.layout():
                form_layout = self.settings_widget.layout()
                for i in range(form_layout.rowCount()):
                    label_item = form_layout.itemAt(i, form_layout.LabelRole)
                    field_item = form_layout.itemAt(i, form_layout.FieldRole)
                    if field_item and field_item.widget() == self.start_row_widget:
                        if label_item and label_item.widget():
                            label_item.widget().setVisible(is_excel)
                        break

    def _read_csv(self, fileName: str, n_rows: Optional[int] = None) -> pl.DataFrame:
        """Read CSV/TXT file preview using polars - for preview purposes only"""
        try:
            read_options = {
                "separator": self.delimiter,
                "has_header": self.first_row_contains_field_names,
                "infer_schema": False,  # Read all as strings initially
                "low_memory": True,  # Enable low memory mode
                "rechunk": False,  # Don't rechunk to save memory
            }

            # Only read the specified preview rows (no record limit applied)
            if n_rows is not None and n_rows > 0:
                read_options["n_rows"] = n_rows

            # Use direct read for small preview data
            df = pl.read_csv(fileName, **read_options)

            logger.debug(f"Successfully read CSV preview with {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Error reading CSV preview {fileName}: {e}")
            return pl.DataFrame()

    def _read_excel(self, fileName: str, n_rows: Optional[int] = None) -> pl.DataFrame:
        """Read Excel file preview using fastexcel - for preview purposes only"""
        try:
            logger.debug(
                f"Reading Excel preview: {fileName}, Selected sheet: {self.selected_sheet}"
            )

            reader = fastexcel.read_excel(fileName)

            # Handle start row and header row logic
            skip_rows = self.start_row - 1  # Convert to 0-based index
            header_row = None

            if self.first_row_contains_field_names:
                # If first row contains field names, use the start row as header
                header_row = skip_rows
                skip_rows = 0  # Don't skip additional rows when header is specified

            # Only read the specified preview rows (no record limit applied)
            read_limit = n_rows if n_rows is not None and n_rows > 0 else None

            # Read sheet directly to polars
            try:
                excel_df = reader.load_sheet(
                    idx_or_name=self.selected_sheet,
                    header_row=header_row,
                    skip_rows=skip_rows,
                    n_rows=read_limit,
                )

                # Convert to polars DataFrame
                if hasattr(excel_df, "to_polars"):
                    df = excel_df.to_polars()
                else:
                    df = pl.from_arrow(excel_df.to_arrow())

                logger.debug(
                    f"Successfully read Excel preview '{self.selected_sheet}' with {len(df)} rows"
                )
                return df

            except Exception as fastexcel_error:
                logger.error(
                    f"Failed to read Excel preview with fastexcel: {fastexcel_error}"
                )
                # Fallback to polars native Excel reading
                try:
                    logger.debug("Trying fallback with polars native Excel reading")
                    df = pl.read_excel(fileName, sheet_id=0)
                    if read_limit and len(df) > read_limit:
                        df = df.head(read_limit)
                    logger.debug(
                        f"Fallback: Successfully read Excel preview with polars"
                    )
                    return df
                except Exception as fallback_error:
                    logger.error(
                        f"All Excel preview reading methods failed: {fallback_error}"
                    )
                    return pl.DataFrame()

        except Exception as e:
            logger.error(f"Error reading Excel preview {fileName}: {e}")
            return pl.DataFrame()

    def _read_file_based_on_type(self, fileName: str) -> pl.DataFrame:
        """Read file based on the selected file type"""
        try:
            if self.file_type == "excel":
                df = self._read_excel(fileName, self.preview_rows)
            elif self.file_type in ["csv", "txt"]:
                df = self._read_csv(fileName, self.preview_rows)
            else:
                # Default to CSV with memory optimization
                df = pl.read_csv(
                    fileName, infer_schema=False, low_memory=True, rechunk=False
                )

            # Add filename as field if requested
            if self.output_filename_as_field:
                filename_only = os.path.basename(fileName)
                df = df.with_columns(pl.lit(filename_only).alias("FileName"))

            return df

        except Exception as e:
            logger.error(f"Error reading file {fileName}: {e}")
            # Return empty DataFrame on error
            return pl.DataFrame()

    def loadFile(self, fileName: str) -> None:
        """Ultra-lightweight file loading for preview - minimal memory footprint"""
        # Clear any existing data to free memory first
        if hasattr(self, "data"):
            del self.data

        # Create table widget only if it doesn't exist
        if not hasattr(self, "tableWidget") or self.tableWidget is None:
            self.tableWidget = QTableWidget(self)

        try:
            # Load preview data using the new simplified functions
            preview_df = self._read_file_based_on_type(fileName)

            if preview_df.height == 0:
                self.tableWidget.setRowCount(0)
                self.tableWidget.setColumnCount(0)
                return

            columns = list(preview_df.columns)
            rows = preview_df.rows()
            row_count = len(rows)
            col_count = len(columns)

            # Set table dimensions
            self.tableWidget.setRowCount(row_count)
            self.tableWidget.setColumnCount(col_count)
            self.tableWidget.setHorizontalHeaderLabels(columns)

            # Fill table directly from DataFrame rows
            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    if col_idx < len(columns):
                        item = QTableWidgetItem(str(value) if value is not None else "")
                        self.tableWidget.setItem(row_idx, col_idx, item)

            # Store the preview DataFrame as data for later use
            self.data = preview_df

            # Configure table with minimal memory settings
            header = self.tableWidget.horizontalHeader()
            header.setStretchLastSection(False)
            for i in range(min(10, col_count)):  # Limit to first 10 columns
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
                if header.sectionSize(i) > 150:  # Even smaller column limit
                    header.resizeSection(i, 150)

            logger.info(f"Loaded preview: {row_count} rows, {col_count} columns")

        except Exception as e:
            logger.error(f"Error loading file {fileName}: {e}")
            # Set data to empty DataFrame on error
            self.data = pl.DataFrame()
            # Create empty table
            if hasattr(self, "tableWidget"):
                self.tableWidget.setRowCount(1)
                self.tableWidget.setColumnCount(1)
                self.tableWidget.setHorizontalHeaderLabels(["Error"])
                error_item = QTableWidgetItem(f"Error loading file: {str(e)}")
                self.tableWidget.setItem(0, 0, error_item)

    def get_code(self) -> str:
        if not self.filePath:
            return ""

        code_lines = []
        code_lines.append("import polars as pl")
        code_lines.append("import os")

        if self.file_type == "excel":
            # Excel file code generation using fastexcel with direct polars conversion
            code_lines.append("import fastexcel")
            code_lines.append(
                f"reader_{self.id} = fastexcel.read_excel('{self.filePath}')"
            )

            # Build load_sheet parameters
            load_params = []
            load_params.append(f"idx_or_name='{self.selected_sheet}'")

            # Handle start row and header row logic
            skip_rows = self.start_row - 1
            if self.first_row_contains_field_names:
                load_params.append(f"header_row={skip_rows}")
                # Don't add skip_rows when header_row is specified
            else:
                load_params.append("header_row=None")
                if skip_rows > 0:
                    load_params.append(f"skip_rows={skip_rows}")

            # Add record limit if specified
            if self.record_limit > 0:
                load_params.append(f"n_rows={self.record_limit}")

            load_call = f"reader_{self.id}.load_sheet({', '.join(load_params)})"

            # Generate code for direct conversion to polars
            code_lines.append(f"excel_df_{self.id} = {load_call}")
            code_lines.append(f"# Convert to polars efficiently")
            code_lines.append(f"try:")
            code_lines.append(
                f"    {self.variable_name} = excel_df_{self.id}.to_polars()"
            )
            code_lines.append(f"except AttributeError:")
            code_lines.append(
                f"    {self.variable_name} = pl.from_arrow(excel_df_{self.id}.to_arrow())"
            )

        elif self.file_type in ["csv", "txt"]:
            # CSV/TXT file code generation with memory optimization
            read_params = ["infer_schema=False"]
            if self.delimiter != ",":
                read_params.append(f"separator='{self.delimiter}'")
            if not self.first_row_contains_field_names:
                read_params.append("has_header=False")

            # Use lazy evaluation for memory efficiency when no record limit
            if self.record_limit > 0:
                read_params.append(f"n_rows={self.record_limit}")
                read_call = f"pl.read_csv('{self.filePath}'"
                if read_params:
                    read_call += f", {', '.join(read_params)}"
                read_call += ")"
                code_lines.append(f"{self.variable_name} = {read_call}")
            else:
                # Use lazy reading for large files
                code_lines.append("# Using lazy evaluation for memory efficiency")
                lazy_call = f"pl.scan_csv('{self.filePath}'"
                if read_params:
                    lazy_call += f", {', '.join(read_params)}"
                lazy_call += ")"
                code_lines.append(f"lazy_{self.variable_name} = {lazy_call}")
                code_lines.append(f"try:")
                code_lines.append(
                    f"    {self.variable_name} = lazy_{self.variable_name}.collect()"
                )
                code_lines.append(f"except Exception as e:")
                code_lines.append(f"    # Fallback to direct reading if lazy fails")
                fallback_call = f"pl.read_csv('{self.filePath}'"
                if read_params:
                    fallback_call += f", {', '.join(read_params)}"
                fallback_call += ")"
                code_lines.append(f"    {self.variable_name} = {fallback_call}")
        else:
            # Default to CSV
            code_lines.append(
                f"{self.variable_name} = pl.read_csv('{self.filePath}', infer_schema=False)"
            )

        # Add filename as field if requested
        if self.output_filename_as_field:
            filename_var = f"filename_{self.id}"
            code_lines.append(f"{filename_var} = os.path.basename('{self.filePath}')")
            code_lines.append(
                f"{self.variable_name} = {self.variable_name}.with_columns(pl.lit({filename_var}).alias('FileName'))"
            )

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> OrderedDict[Any, Any]:
        res = super().serialize()
        res["filePath"] = self.filePath
        res["file_type"] = self.file_type
        res["record_limit"] = self.record_limit
        res["output_filename_as_field"] = self.output_filename_as_field
        res["delimiter"] = self.delimiter
        res["first_row_contains_field_names"] = self.first_row_contains_field_names
        res["selected_sheet"] = self.selected_sheet
        res["available_sheets"] = self.available_sheets
        res["start_row"] = self.start_row
        return res

    def deserialize(
        self, data: dict, hashmap: dict = {}, restore_id: Optional[bool] = True
    ) -> bool:
        res = super().deserialize(data, hashmap)

        try:
            self.filePath = data.get("filePath", "")
            self.file_type = data.get("file_type", "csv")
            self.record_limit = data.get("record_limit", 0)
            self.output_filename_as_field = data.get("output_filename_as_field", False)
            self.delimiter = data.get("delimiter", ",")
            self.first_row_contains_field_names = data.get(
                "first_row_contains_field_names", True
            )
            self.selected_sheet = data.get("selected_sheet", "")
            self.available_sheets = data.get("available_sheets", [])
            self.start_row = data.get("start_row", 1)

            # Update UI elements if they exist
            if hasattr(self, "recordLimitSpinBox"):
                self.recordLimitSpinBox.setValue(self.record_limit)
            if hasattr(self, "outputFilenameCheckBox"):
                self.outputFilenameCheckBox.setChecked(self.output_filename_as_field)
            if hasattr(self, "delimiterEdit"):
                self.delimiterEdit.setText(self.delimiter)
            if hasattr(self, "firstRowFieldNamesCheckBox"):
                self.firstRowFieldNamesCheckBox.setChecked(
                    self.first_row_contains_field_names
                )
            if hasattr(self, "selectedSheetCombo"):
                if self.available_sheets:
                    self.selectedSheetCombo.clear()
                    self.selectedSheetCombo.addItems(self.available_sheets)
                    if self.selected_sheet in self.available_sheets:
                        self.selectedSheetCombo.setCurrentText(self.selected_sheet)
            if hasattr(self, "startRowSpinBox"):
                self.startRowSpinBox.setValue(self.start_row)

            # Update UI visibility based on whether file exists and file type
            if self.filePath and self.file_type:
                self._update_ui_visibility(self.file_type)
            else:
                self._hide_all_options()

            return res
        except Exception as e:
            dumpException(e)
        return res


@register_node(IONodes.FILE_INPUT, NodeTypes.IO)
class TriggerNode_FileInput(TriggerNode):
    icon = "node_file_input"
    node_code = IONodes.FILE_INPUT
    node_type = NodeTypes.IO
    node_title = "File Input"
    content_label_objname = "trigger_node_file_input"
    style = {}

    def __init__(self, scene: "Scene") -> None:
        super().__init__(scene, inputs=[], outputs=[3])
        self.eval()
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        self.content: FileInputContent = FileInputContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    # def evalImplementation(self):
    #     param = {
    #         "data": self.content.data,
    #         "variable_name": self.content.variable_name
    #     }
    #     # variable = self.content.variable_name
    #     return param

    def processInputs(self, input_values: list[Any]) -> Optional[list[dict[str, Any]]]:
        print("⚠️⚠️⚠️ File Input ⚠️⚠️⚠️")
        # Custom processing logic for the File Input node
        if not self.content.filePath:
            self.grNode.setToolTip("No file selected")
            self.markInvalid(True)
            return None

        self.markDirty(False)
        self.markInvalid(False)
        self.content.check_file_path()

        # # Load full data for processing (not just preview)
        # if (
        #     self.content.data is None
        #     or self.content.data.height <= self.content.preview_rows
        # ):
        #     # Current data is just preview, need to load full data
        #     self.content.data = self.content._read_file_based_on_type(
        #         self.content.filePath
        #     )
        #     logger.info(f"Loaded full data for processing: {self.content.data.shape}")

        self.param = [
            {"data": self.content.data, "variable_name": self.content.variable_name}
        ]

        self.evalChildren()

        return self.param

    def cleanup_memory(self):
        """Explicit memory cleanup to reduce memory usage"""
        if hasattr(self.content, "data") and self.content.data is not None:
            del self.content.data
            self.content.data = None
        # Force garbage collection
        import gc

        gc.collect()

    def get_code(self):
        return self.content.get_code()
