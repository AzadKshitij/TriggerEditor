import polars as pl
import os
import fastexcel
from qtpy.QtWidgets import QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout, QComboBox, QHBoxLayout, QLabel, QSpinBox, QCheckBox, QDialog, QListWidget, QDialogButtonBox
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.core.node_configuration import register_node, IONodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
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

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
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
        self.preview_rows = 3  # Reduce to just 3 rows for absolute minimal memory usage
        self.node = node
        self.file_type = "csv"  # Default file type

        # New properties for the enhanced functionality
        self.record_limit = 0  # 0 means no limit
        self.output_filename_as_field = False
        self.delimiter = ","    # Default delimiter for CSV/TXT files
        self.first_row_contains_field_names = True
        self.selected_sheet = ""  # For Excel files
        self.available_sheets = []  # List of all available sheets
        self.start_row = 1  # Row to start reading from (1-based)

        # pass on variables
        self.data: pl.DataFrame = pl.DataFrame()
        self.variable_name = f'var_file_input_{self.id}'

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
        self._node = value

    def initUI(self, _icon: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        # File path input
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setPlaceholderText("Enter file path")
        self.filePathEdit.textChanged.connect(
            self._on_filePathEdit_textChanged)
        self.registerInputWidget(self.filePathEdit)

        # Load button
        self.loadButton = QPushButton("Load File", self)
        self.loadButton.clicked.connect(self.openFileDialog)

        # Record Limit
        record_limit_layout = QHBoxLayout()
        record_limit_layout.addWidget(QLabel("Record Limit:"))
        self.recordLimitSpinBox = QSpinBox(self)
        self.recordLimitSpinBox.setMinimum(0)
        self.recordLimitSpinBox.setMaximum(999999999)
        self.recordLimitSpinBox.setValue(self.record_limit)
        self.recordLimitSpinBox.setSpecialValueText("No Limit")
        self.recordLimitSpinBox.valueChanged.connect(
            self._on_record_limit_changed)
        self.registerInputWidget(self.recordLimitSpinBox)
        record_limit_layout.addWidget(self.recordLimitSpinBox)

        # Output Filename as Field
        self.outputFilenameCheckBox = QCheckBox("Output Filename as Field")
        self.outputFilenameCheckBox.setChecked(self.output_filename_as_field)
        self.outputFilenameCheckBox.toggled.connect(
            self._on_output_filename_changed)
        self.registerInputWidget(self.outputFilenameCheckBox)

        # Delimiter (for CSV/TXT files)
        delimiter_layout = QHBoxLayout()
        delimiter_layout.addWidget(QLabel("Delimiter:"))
        self.delimiterEdit = QLineEdit(self)
        self.delimiterEdit.setText(self.delimiter)
        self.delimiterEdit.setPlaceholderText("e.g., , ; | \\t")
        self.delimiterEdit.textChanged.connect(self._on_delimiter_changed)
        self.registerInputWidget(self.delimiterEdit)
        delimiter_layout.addWidget(self.delimiterEdit)

        # First Row Contains Field Names
        self.firstRowFieldNamesCheckBox = QCheckBox(
            "First Row Contains Field Names")
        self.firstRowFieldNamesCheckBox.setChecked(
            self.first_row_contains_field_names)
        self.firstRowFieldNamesCheckBox.toggled.connect(
            self._on_first_row_field_names_changed)
        self.registerInputWidget(self.firstRowFieldNamesCheckBox)

        # Selected Sheet (for Excel files)
        selected_sheet_layout = QHBoxLayout()
        selected_sheet_layout.addWidget(QLabel("Selected Sheet:"))
        self.selectedSheetCombo = QComboBox(self)
        self.selectedSheetCombo.currentTextChanged.connect(
            self._on_selected_sheet_changed)
        self.registerInputWidget(self.selectedSheetCombo)
        selected_sheet_layout.addWidget(self.selectedSheetCombo)

        # Start Row (for Excel files)
        start_row_layout = QHBoxLayout()
        start_row_layout.addWidget(QLabel("Start Row:"))
        self.startRowSpinBox = QSpinBox(self)
        self.startRowSpinBox.setMinimum(1)
        self.startRowSpinBox.setMaximum(999999)
        self.startRowSpinBox.setValue(self.start_row)
        self.startRowSpinBox.valueChanged.connect(self._on_start_row_changed)
        self.registerInputWidget(self.startRowSpinBox)
        start_row_layout.addWidget(self.startRowSpinBox)

        # Always create a new table widget when creating layout
        self.tableWidget = QTableWidget(self)

        # Add widgets to layout
        dock_layout.addWidget(self.filePathEdit)
        dock_layout.addWidget(self.loadButton)

        record_limit_widget = QWidget()
        record_limit_widget.setLayout(record_limit_layout)
        dock_layout.addWidget(record_limit_widget)
        self.record_limit_widget = record_limit_widget  # Store reference for show/hide

        dock_layout.addWidget(self.outputFilenameCheckBox)
        # Store reference for show/hide
        self.output_filename_widget = self.outputFilenameCheckBox

        delimiter_widget = QWidget()
        delimiter_widget.setLayout(delimiter_layout)
        dock_layout.addWidget(delimiter_widget)
        self.delimiter_widget = delimiter_widget  # Store reference for show/hide

        dock_layout.addWidget(self.firstRowFieldNamesCheckBox)
        # Store reference for show/hide
        self.first_row_widget = self.firstRowFieldNamesCheckBox

        selected_sheet_widget = QWidget()
        selected_sheet_widget.setLayout(selected_sheet_layout)
        dock_layout.addWidget(selected_sheet_widget)
        self.selected_sheet_widget = selected_sheet_widget  # Store reference for show/hide

        start_row_widget = QWidget()
        start_row_widget.setLayout(start_row_layout)
        dock_layout.addWidget(start_row_widget)
        self.start_row_widget = start_row_widget  # Store reference for show/hide

        dock_layout.addWidget(self.tableWidget)

        # Initially hide all options until a file is selected
        # Load file if path exists and show appropriate options
        self._hide_all_options()
        if self.filePath:
            self.filePathEdit.setText(self.filePath)
            file_type = self._auto_detect_file_type(self.filePath)
            self._update_ui_visibility(file_type)
            if self.data.is_empty():
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
        if delimiter_text == '\\t':
            self.delimiter = '\t'
        elif delimiter_text == '\\n':
            self.delimiter = '\n'
        elif delimiter_text == '\\r':
            self.delimiter = '\r'
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

    def get_columns(self) -> list[str]:
        """Get column names - use minimal reading without storing data"""
        if self.filePath:
            try:
                # For CSV/TXT, use pure Python to get just column names
                if self.file_type in ['csv', 'txt']:
                    import csv

                    try:
                        with open(self.filePath, 'r', encoding='utf-8', newline='') as csvfile:
                            reader = csv.reader(
                                csvfile, delimiter=self.delimiter)

                            if self.first_row_contains_field_names:
                                columns = next(reader)
                                return list(columns)
                            else:
                                # Read first row to count columns
                                first_row = next(reader)
                                return [f"Column_{i+1}" for i in range(len(first_row))]

                    except Exception as e:
                        logger.warning(
                            f"Pure Python CSV reading failed: {e}, trying polars")
                        # Fallback to polars lazy scan
                        lazy_df = pl.scan_csv(
                            self.filePath,
                            separator=self.delimiter,
                            has_header=self.first_row_contains_field_names,
                            infer_schema=False,
                            low_memory=True
                        )
                        columns = list(lazy_df.columns)
                        del lazy_df
                        return columns
                        # Ultra-minimal fallback
                        df = pl.read_csv(
                            self.filePath,
                            separator=self.delimiter,
                            has_header=self.first_row_contains_field_names,
                            n_rows=0 if self.first_row_contains_field_names else 1,
                            infer_schema=False,
                            low_memory=True
                        )
                        columns = list(df.columns)
                        del df
                        return columns

                elif self.file_type == 'excel':
                    import fastexcel
                    reader = fastexcel.read_excel(self.filePath)
                    sample_df = reader.load_sheet(
                        idx_or_name=self.selected_sheet,
                        header_row=0 if self.first_row_contains_field_names else None,
                        n_rows=1
                    )
                    if hasattr(sample_df, 'to_polars'):
                        df = sample_df.to_polars()
                    else:
                        df = pl.from_arrow(sample_df.to_arrow())

                    columns = list(df.columns)
                    del df, sample_df
                    return columns
                else:
                    df = pl.read_csv(self.filePath, n_rows=0,
                                     infer_schema=False, low_memory=True)
                    columns = list(df.columns)
                    del df
                    return columns

            except Exception as e:
                logger.error(f"Error reading file for columns: {e}")
                return []

        return []

    def openFileDialog(self) -> None:
        '''Open file dialog with support for multiple file types'''
        options = QFileDialog.Options()
        file_filters = (
            "All Supported Files (*.csv *.txt *.xlsx *.xls);;"
            "CSV Files (*.csv);;"
            "Text Files (*.txt);;"
            "Excel Files (*.xlsx *.xls);;"
            "All Files (*)"
        )
        fileName, _ = QFileDialog.getOpenFileName(
            self.parent(),
            "Open Data File",
            "",
            file_filters,
            options=options
        )
        if fileName:
            # Clear existing data first to free memory
            if hasattr(self, 'data') and self.data is not None:
                del self.data
                self.data = None

            self.filePath = fileName
            self.filePathEdit.setText(fileName)

            # Auto-detect file type and handle Excel sheet selection
            file_type = self._auto_detect_file_type(fileName)

            if file_type == 'excel':
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
        if extension in ['.xlsx', '.xls']:
            file_type = 'excel'
        elif extension == '.txt':
            file_type = 'txt'
        else:  # .csv or others default to CSV
            file_type = 'csv'

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
                    f"Found sheet names using fastexcel: {self.available_sheets}")

                # Set the first sheet as default if no sheet is selected
                if not self.selected_sheet and self.available_sheets:
                    self.selected_sheet = self.available_sheets[0]

                # Update UI to show Excel options
                self._update_ui_visibility('excel')

            except Exception as e:
                logger.error(
                    f"fastexcel failed to read Excel file {fileName}: {e}")
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
        """Hide all option widgets when no file is selected"""
        if hasattr(self, 'record_limit_widget'):
            self.record_limit_widget.setVisible(False)
        if hasattr(self, 'output_filename_widget'):
            self.output_filename_widget.setVisible(False)
        if hasattr(self, 'delimiter_widget'):
            self.delimiter_widget.setVisible(False)
        if hasattr(self, 'first_row_widget'):
            self.first_row_widget.setVisible(False)
        if hasattr(self, 'selected_sheet_widget'):
            self.selected_sheet_widget.setVisible(False)
        if hasattr(self, 'start_row_widget'):
            self.start_row_widget.setVisible(False)

    def _update_ui_visibility(self, file_type: str) -> None:
        """Update UI element visibility based on file type"""
        # Show common options for all file types
        if hasattr(self, 'record_limit_widget'):
            self.record_limit_widget.setVisible(True)
        if hasattr(self, 'output_filename_widget'):
            self.output_filename_widget.setVisible(True)
        if hasattr(self, 'first_row_widget'):
            self.first_row_widget.setVisible(True)

        # Show/hide file-type specific options
        if hasattr(self, 'delimiter_widget'):
            # Show delimiter options for CSV/TXT files only
            self.delimiter_widget.setVisible(file_type in ['csv', 'txt'])

        if hasattr(self, 'selected_sheet_widget'):
            # Show selected sheet for Excel files only
            self.selected_sheet_widget.setVisible(file_type == 'excel')
            if file_type == 'excel' and hasattr(self, 'selectedSheetCombo'):
                # Populate the dropdown with available sheets
                self.selectedSheetCombo.clear()
                if self.available_sheets:
                    self.selectedSheetCombo.addItems(self.available_sheets)
                    # Set current selection
                    if self.selected_sheet in self.available_sheets:
                        self.selectedSheetCombo.setCurrentText(
                            self.selected_sheet)

        if hasattr(self, 'start_row_widget'):
            # Show start row for Excel files only
            self.start_row_widget.setVisible(file_type == 'excel')

    def _read_file_based_on_type(self, fileName: str) -> pl.DataFrame:
        """Read file based on the selected file type"""
        try:
            if self.file_type == 'excel':
                # Read Excel file using fastexcel

                logger.info(
                    f"Reading Excel file: {fileName}, Selected sheet: {self.selected_sheet}")

                try:
                    reader = fastexcel.read_excel(f"{fileName}")

                    # Handle start row and header row logic
                    skip_rows = self.start_row - 1  # Convert to 0-based index
                    header_row = None

                    if self.first_row_contains_field_names:
                        # If first row contains field names, use the start row as header
                        header_row = skip_rows
                        skip_rows = 0  # Don't skip additional rows when header is specified

                    # For memory optimization, only read what we need
                    # If this is for preview, limit the rows read
                    read_limit = None
                    if self.record_limit > 0:
                        read_limit = self.record_limit

                    # Read sheet directly to polars if possible, otherwise convert
                    try:
                        # Try using fastexcel's direct polars conversion if available
                        excel_df = reader.load_sheet(
                            idx_or_name=self.selected_sheet,
                            header_row=header_row,
                            skip_rows=skip_rows,
                            n_rows=read_limit  # Limit rows for memory optimization
                        )

                        # Check if fastexcel returns a polars DataFrame directly
                        if hasattr(excel_df, 'to_polars'):
                            df = excel_df.to_polars()
                        else:
                            # Convert to polars without intermediate pandas storage
                            df = pl.from_arrow(excel_df.to_arrow())

                    except AttributeError:
                        # Fallback: use polars' native excel reading
                        logger.info(
                            "Falling back to polars native Excel reading")
                        df = pl.read_excel(
                            fileName,
                            sheet_name=self.selected_sheet,
                            read_csv_options={
                                "skip_rows": skip_rows,
                                "n_rows": read_limit,
                                "has_header": self.first_row_contains_field_names,
                                "infer_schema": False
                            }
                        )

                    logger.info(
                        f"Successfully read Excel sheet '{self.selected_sheet}' starting from row {self.start_row} with {len(df)} rows")

                except Exception as e:
                    logger.error(
                        f"Failed to read Excel file with fastexcel: {e}")
                    # Fallback: try reading the first sheet with polars
                    try:
                        logger.info(
                            "Trying fallback with polars native Excel reading")
                        # Read first sheet by index
                        df = pl.read_excel(fileName, sheet_id=0)
                        logger.info(
                            f"Fallback: Successfully read first sheet with polars")
                    except Exception as fallback_error:
                        logger.error(
                            f"All Excel reading methods failed: {fallback_error}")
                        return pl.DataFrame()
            elif self.file_type in ['csv', 'txt']:
                # Read CSV/TXT file with memory optimization
                read_options = {
                    'separator': self.delimiter,
                    'has_header': self.first_row_contains_field_names,
                    'infer_schema': False,  # Read all as strings initially
                    'low_memory': True,     # Enable low memory mode
                    'rechunk': False        # Don't rechunk to save memory
                }

                # Apply record limit if specified for memory optimization
                if self.record_limit > 0:
                    read_options['n_rows'] = self.record_limit

                # Use lazy evaluation for large files to save memory
                try:
                    # Try lazy reading first for memory efficiency
                    lazy_df = pl.scan_csv(fileName, **read_options)
                    if self.record_limit > 0:
                        df = lazy_df.head(self.record_limit).collect()
                    else:
                        df = lazy_df.collect()
                except Exception as lazy_error:
                    logger.warning(
                        f"Lazy reading failed: {lazy_error}, falling back to direct read")
                    df = pl.read_csv(fileName, **read_options)
            else:
                # Default to CSV with memory optimization
                df = pl.read_csv(fileName, infer_schema=False,
                                 low_memory=True, rechunk=False)

            # Add filename as field if requested
            if self.output_filename_as_field:
                filename_only = os.path.basename(fileName)
                df = df.with_columns(pl.lit(filename_only).alias("FileName"))

            return df

        except Exception as e:
            logger.error(f"Error reading file {fileName}: {e}")
            # Return empty DataFrame on error
            return pl.DataFrame()

    def _read_minimal_csv_preview(self, fileName: str, preview_rows: int):
        """Ultra-minimal CSV preview using pure Python - no polars overhead"""
        import csv

        try:
            rows = []
            columns = []

            with open(fileName, 'r', encoding='utf-8', newline='') as csvfile:
                # Create CSV reader with specified delimiter
                reader = csv.reader(csvfile, delimiter=self.delimiter)

                # Read header if present
                if self.first_row_contains_field_names:
                    columns = next(reader)
                    rows_to_read = preview_rows
                else:
                    # Generate generic column names
                    first_row = next(reader)
                    columns = [f"Column_{i+1}" for i in range(len(first_row))]
                    rows.append(first_row)
                    rows_to_read = preview_rows - 1

                # Read only the required number of rows
                for i, row in enumerate(reader):
                    if i >= rows_to_read:
                        break
                    rows.append(row)

            # Return raw data without polars DataFrame
            return {'columns': columns, 'rows': rows}

        except Exception as e:
            logger.error(f"Error reading minimal CSV preview: {e}")
            return {'columns': [], 'rows': []}

    def _read_file_for_preview(self, fileName: str, preview_rows: int) -> pl.DataFrame:
        """Ultra-lightweight file reading for preview purposes - minimal memory footprint"""
        try:
            if self.file_type == 'excel':
                logger.debug(
                    f"Reading Excel preview: {fileName}, Sheet: {self.selected_sheet}, Rows: {preview_rows}")

                try:
                    reader = fastexcel.read_excel(f"{fileName}")
                    skip_rows = self.start_row - 1
                    header_row = None

                    if self.first_row_contains_field_names:
                        header_row = skip_rows
                        skip_rows = 0

                    # Read minimal rows for preview
                    excel_df = reader.load_sheet(
                        idx_or_name=self.selected_sheet,
                        header_row=header_row,
                        skip_rows=skip_rows,
                        n_rows=preview_rows
                    )

                    # Convert to polars efficiently
                    if hasattr(excel_df, 'to_polars'):
                        df = excel_df.to_polars()
                    else:
                        df = pl.from_arrow(excel_df.to_arrow())

                except Exception as e:
                    logger.warning(
                        f"fastexcel preview failed: {e}, trying polars")
                    df = pl.read_excel(fileName, sheet_id=0, read_options={
                                       'n_rows': preview_rows})

            elif self.file_type in ['csv', 'txt']:
                # For CSV/TXT: Use pure Python reading to avoid polars memory overhead
                raw_data = self._read_minimal_csv_preview(
                    fileName, preview_rows)

                if not raw_data['columns']:
                    return pl.DataFrame()

                # Create minimal polars DataFrame only if we have data
                if raw_data['rows']:
                    # Create dictionary for polars
                    data_dict = {}
                    for i, col in enumerate(raw_data['columns']):
                        column_data = []
                        for row in raw_data['rows']:
                            if i < len(row):
                                # Convert to string
                                column_data.append(str(row[i]))
                            else:
                                column_data.append("")  # Fill missing values
                        data_dict[col] = column_data

                    # Create minimal DataFrame
                    df = pl.DataFrame(data_dict)
                else:
                    # Create empty DataFrame with column structure
                    data_dict = {col: [] for col in raw_data['columns']}
                    df = pl.DataFrame(data_dict)
            else:
                # Default minimal CSV read with memory optimization
                df = pl.read_csv(
                    fileName,
                    n_rows=preview_rows,
                    infer_schema=False,
                    low_memory=True,
                    rechunk=False
                )

            # Add filename field if requested (only for preview)
            if self.output_filename_as_field:
                filename_only = os.path.basename(fileName)
                df = df.with_columns(pl.lit(filename_only).alias("FileName"))

            logger.debug(
                f"Preview loaded: {df.shape[0]} rows, {df.shape[1]} columns, memory optimized")
            return df

        except Exception as e:
            logger.error(f"Error reading file preview {fileName}: {e}")
            return pl.DataFrame()

    def loadFile(self, fileName: str) -> None:
        """Ultra-lightweight file loading for preview - minimal memory footprint"""
        # Clear any existing data to free memory first
        if hasattr(self, 'data'):
            del self.data

        # Create table widget only if it doesn't exist
        if not hasattr(self, 'tableWidget') or self.tableWidget is None:
            self.tableWidget = QTableWidget(self)

        try:
            # Use even smaller preview for minimal memory - just 2 rows
            preview_limit = 2

            # For CSV files, use pure Python reading to avoid polars entirely
            if self.file_type in ['csv', 'txt']:
                raw_data = self._read_minimal_csv_preview(
                    fileName, preview_limit)

                if not raw_data['columns']:
                    self.tableWidget.setRowCount(0)
                    self.tableWidget.setColumnCount(0)
                    return

                columns = raw_data['columns']
                rows = raw_data['rows']

                # Set table dimensions
                self.tableWidget.setRowCount(len(rows))
                self.tableWidget.setColumnCount(len(columns))
                self.tableWidget.setHorizontalHeaderLabels(columns)

                # Fill table directly from raw data - no DataFrame needed
                for row_idx, row_data in enumerate(rows):
                    for col_idx, value in enumerate(row_data):
                        if col_idx < len(columns):
                            item = QTableWidgetItem(
                                str(value) if value is not None else "")
                            self.tableWidget.setItem(row_idx, col_idx, item)

                # Don't store any data - table has what we need
                row_count = len(rows)  # Define for later use
                col_count = len(columns)  # Define for later use
                logger.info(f"Loaded CSV preview: {row_count} rows, {col_count} columns (no DataFrame stored)")

            else:
                # For Excel and other formats, use minimal polars DataFrame
                preview_df = self._read_file_for_preview(
                    fileName, preview_limit)

                if preview_df.height == 0:
                    self.tableWidget.setRowCount(0)
                    self.tableWidget.setColumnCount(0)
                    return

                columns = list(preview_df.columns)
                row_count = preview_df.height
                col_count = len(columns)

                # Set table dimensions
                self.tableWidget.setRowCount(row_count)
                self.tableWidget.setColumnCount(col_count)
                self.tableWidget.setHorizontalHeaderLabels(columns)

                # Fill table row by row and immediately discard DataFrame
                for row_idx in range(row_count):
                    row_data = preview_df.row(row_idx)
                    for col_idx, value in enumerate(row_data):
                        item = QTableWidgetItem(
                            str(value) if value is not None else "")
                        self.tableWidget.setItem(row_idx, col_idx, item)

                # Immediately delete DataFrame to free memory
                del preview_df
                logger.info(
                    f"Loaded preview: {row_count} rows, {col_count} columns (DataFrame deleted)")

            # Configure table with minimal memory settings
            header = self.tableWidget.horizontalHeader()
            header.setStretchLastSection(False)
            col_count = self.tableWidget.columnCount()
            for i in range(min(10, col_count)):  # Limit to first 10 columns
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
                if header.sectionSize(i) > 150:  # Even smaller column limit
                    header.resizeSection(i, 150)

            logger.info(
                f"Loaded preview: {row_count} rows, {col_count} columns")

        except Exception as e:
            logger.error(f"Error loading file {fileName}: {e}")
            # Clear data on error
            if hasattr(self, 'data'):
                del self.data
            # Create empty table
            if hasattr(self, 'tableWidget'):
                self.tableWidget.setRowCount(0)
                self.tableWidget.setColumnCount(0)

            # Configure table properties
            self.tableWidget.setSortingEnabled(True)
            self.tableWidget.horizontalHeader().setSectionsMovable(True)

            # Update tooltip with file info
            file_info = f"File: {os.path.basename(fileName)}\nType: {self.file_type.upper()}\nRows (preview): {row_count}"
            if self.file_type in ['csv', 'txt']:
                file_info += f"\nDelimiter: '{self.delimiter}'"
            self.tableWidget.setToolTip(file_info)

        except Exception as e:
            logger.error(
                f"Exception in loading {self.file_type} file: {fileName}")
            logger.trace(e)
            # Show error in table widget
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

        if self.file_type == 'excel':
            # Excel file code generation using fastexcel with direct polars conversion
            code_lines.append("import fastexcel")
            code_lines.append(
                f"reader_{self.id} = fastexcel.read_excel('{self.filePath}')")

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
                f"    {self.variable_name} = excel_df_{self.id}.to_polars()")
            code_lines.append(f"except AttributeError:")
            code_lines.append(
                f"    {self.variable_name} = pl.from_arrow(excel_df_{self.id}.to_arrow())")

        elif self.file_type in ['csv', 'txt']:
            # CSV/TXT file code generation with memory optimization
            read_params = ["infer_schema=False"]
            if self.delimiter != ',':
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
                code_lines.append(
                    "# Using lazy evaluation for memory efficiency")
                lazy_call = f"pl.scan_csv('{self.filePath}'"
                if read_params:
                    lazy_call += f", {', '.join(read_params)}"
                lazy_call += ")"
                code_lines.append(f"lazy_{self.variable_name} = {lazy_call}")
                code_lines.append(f"try:")
                code_lines.append(
                    f"    {self.variable_name} = lazy_{self.variable_name}.collect()")
                code_lines.append(f"except Exception as e:")
                code_lines.append(
                    f"    # Fallback to direct reading if lazy fails")
                fallback_call = f"pl.read_csv('{self.filePath}'"
                if read_params:
                    fallback_call += f", {', '.join(read_params)}"
                fallback_call += ")"
                code_lines.append(
                    f"    {self.variable_name} = {fallback_call}")
        else:
            # Default to CSV
            code_lines.append(
                f"{self.variable_name} = pl.read_csv('{self.filePath}', infer_schema=False)")

        # Add filename as field if requested
        if self.output_filename_as_field:
            filename_var = f"filename_{self.id}"
            code_lines.append(
                f"{filename_var} = os.path.basename('{self.filePath}')")
            code_lines.append(
                f"{self.variable_name} = {self.variable_name}.with_columns(pl.lit({filename_var}).alias('FileName'))")

        return '\n'.join(code_lines) + '\n'

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

    def deserialize(self, data: dict, hashmap: dict = {}, restore_id: Optional[bool] = True) -> bool:
        res = super().deserialize(data, hashmap)

        try:
            self.filePath = data.get('filePath', "")
            self.file_type = data.get('file_type', "csv")
            self.record_limit = data.get('record_limit', 0)
            self.output_filename_as_field = data.get(
                'output_filename_as_field', False)
            self.delimiter = data.get('delimiter', ",")
            self.first_row_contains_field_names = data.get(
                'first_row_contains_field_names', True)
            self.selected_sheet = data.get('selected_sheet', "")
            self.available_sheets = data.get('available_sheets', [])
            self.start_row = data.get('start_row', 1)

            # Update UI elements if they exist
            if hasattr(self, 'recordLimitSpinBox'):
                self.recordLimitSpinBox.setValue(self.record_limit)
            if hasattr(self, 'outputFilenameCheckBox'):
                self.outputFilenameCheckBox.setChecked(
                    self.output_filename_as_field)
            if hasattr(self, 'delimiterEdit'):
                self.delimiterEdit.setText(self.delimiter)
            if hasattr(self, 'firstRowFieldNamesCheckBox'):
                self.firstRowFieldNamesCheckBox.setChecked(
                    self.first_row_contains_field_names)
            if hasattr(self, 'selectedSheetCombo'):
                if self.available_sheets:
                    self.selectedSheetCombo.clear()
                    self.selectedSheetCombo.addItems(self.available_sheets)
                    if self.selected_sheet in self.available_sheets:
                        self.selectedSheetCombo.setCurrentText(
                            self.selected_sheet)
            if hasattr(self, 'startRowSpinBox'):
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

    def __init__(self, scene: 'Scene') -> None:
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

        self.param = [{
            "data": self.content.data,
            "variable_name": self.content.variable_name
        }]

        self.evalChildren()

        return self.param

    def cleanup_memory(self):
        """Explicit memory cleanup to reduce memory usage"""
        if hasattr(self.content, 'data') and self.content.data is not None:
            del self.content.data
            self.content.data = None
        # Force garbage collection
        import gc
        gc.collect()

    def get_code(self):
        return self.content.get_code()
