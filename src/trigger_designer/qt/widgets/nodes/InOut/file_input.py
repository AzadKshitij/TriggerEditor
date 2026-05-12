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
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils_no_qt import dumpException
from loguru import logger
from typing import Any, Optional, OrderedDict, TYPE_CHECKING, Type, TypeVar, Union, cast
from trigger_designer.qt.helpers import global_logger


if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    from trigger_designer.qt.node_base import TriggerNode
    from nodeeditor.node_node import Node


class FileInputContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    max_missing_file_attempts = 5
    evaluate = Signal()
    serialized_state_schema = {
        "filePath": {"default": ""},
        "file_type": {"default": "csv"},
        "record_limit": {"default": 0},
        "output_filename_as_field": {"default": False},
        "delimiter": {"default": ","},
        "first_row_contains_field_names": {"default": True},
        "selected_sheet": {"default": ""},
        "available_sheets": {"default": []},
        "start_row": {"default": 1},
        "schema_snapshot": {"default": []},
        "file_metadata": {"default": {}},
    }

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
        self.schema_snapshot: list[dict[str, str]] = []
        self.file_metadata: dict[str, Any] = {}

        # pass on variables
        self.data: Union[pl.DataFrame, pl.LazyFrame] = pl.DataFrame()
        self.variable_name = f"var_file_input_{self.id}"
        self._missing_file_attempts: dict[str, int] = {}

    def _reset_missing_file_attempts(self, file_path: str) -> None:
        self._missing_file_attempts.pop(file_path, None)

    def _log_missing_file(self, file_path: str) -> None:
        attempts = self._missing_file_attempts.get(file_path, 0) + 1
        self._missing_file_attempts[file_path] = attempts

        if attempts > self.max_missing_file_attempts:
            return

        warning_message = (
            f"File not found: '{file_path}' "
            f"(attempt {attempts}/{self.max_missing_file_attempts})"
        )
        logger.warning(warning_message)
        global_logger.warning(warning_message)

        if attempts == self.max_missing_file_attempts:
            give_up_message = (
                f"Giving up after {self.max_missing_file_attempts} attempts: "
                f"file '{file_path}' was not found."
            )
            logger.error(give_up_message)
            global_logger.error(give_up_message)

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

        # Polars table viewer for preview (data-only mode for clean interface)
        self.table_viewer = PolarsTableViewer(
            parent=self,
            show_controls=False,  # No controls needed in file input node
            show_info=False,  # No info panel to keep it compact
            show_search=False,  # Search not needed for preview
            show_export=False,  # Export not needed in node context
            show_performance_settings=False,  # Performance settings not needed
        )
        dock_layout.addWidget(self.table_viewer)

        # Keep reference to tableWidget for backward compatibility
        # Some methods might still reference self.tableWidget
        self.tableWidget = self.table_viewer.table_view

        # Initially hide all options until a file is selected
        self._hide_all_options()
        if self.filePath:
            self.filePathEdit.setText(self.filePath)
            file_type = self._auto_detect_file_type(self.filePath)
            self._update_ui_visibility(file_type)
            if self.data is None or self.data.height == 0:
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
            self._log_missing_file(self.filePath)
            self.data = pl.DataFrame()
            self.node.grNode.setToolTip(f"File '{self.filePath}' does not exist")
            self.node.markInvalid(True)
            return False
        else:
            self._reset_missing_file_attempts(self.filePath)
            self.node.grNode.setToolTip("")
            self.node.markInvalid(False)

        self.loadFile(self.filePath)
        return True

    def _build_schema_snapshot(
        self, dataframe: Optional[pl.DataFrame] = None
    ) -> list[dict[str, str]]:
        source_df = dataframe
        if source_df is None and isinstance(self.data, pl.DataFrame):
            source_df = self.data

        if source_df is None or source_df.width == 0:
            return []

        return [
            {"name": column_name, "dtype": str(dtype)}
            for column_name, dtype in source_df.schema.items()
        ]

    def _build_file_metadata(self) -> dict[str, Any]:
        if not self.filePath or not os.path.exists(self.filePath):
            return {}

        file_stat = os.stat(self.filePath)
        return {
            "size_bytes": file_stat.st_size,
            "modified_time": int(file_stat.st_mtime),
        }

    def _refresh_saved_input_metadata(
        self, preview_df: Optional[pl.DataFrame] = None
    ) -> None:
        if self.filePath and os.path.exists(self.filePath):
            schema_source = preview_df
            if schema_source is None:
                schema_source = self._read_file_based_on_type(self.filePath)

            snapshot = self._build_schema_snapshot(schema_source)
            if snapshot:
                self.schema_snapshot = snapshot
            self.file_metadata = self._build_file_metadata()

    def validate_loaded_state(self) -> list[str]:
        issues: list[str] = []

        if not self.filePath:
            return issues

        if not os.path.exists(self.filePath):
            issues.append(f"Missing input file: {self.filePath}")
        else:
            preview_df = self._read_file_based_on_type(self.filePath)
            current_snapshot = self._build_schema_snapshot(preview_df)
            saved_columns = {
                item.get("name", ""): item.get("dtype", "")
                for item in self.schema_snapshot
                if item.get("name")
            }
            current_columns = {
                item.get("name", ""): item.get("dtype", "")
                for item in current_snapshot
                if item.get("name")
            }

            missing_columns = [
                column for column in saved_columns if column not in current_columns
            ]
            added_columns = [
                column for column in current_columns if column not in saved_columns
            ]
            dtype_changes = [
                f"{column} ({saved_columns[column]} -> {current_columns[column]})"
                for column in saved_columns.keys() & current_columns.keys()
                if saved_columns[column] != current_columns[column]
            ]

            if missing_columns:
                issues.append(
                    "Missing saved columns: " + ", ".join(sorted(missing_columns))
                )
            if added_columns:
                issues.append(
                    "New columns compared to saved workflow: "
                    + ", ".join(sorted(added_columns))
                )
            if dtype_changes:
                issues.append("Column type changes: " + ", ".join(dtype_changes))

            if self.file_type == "excel" and self.selected_sheet:
                try:
                    reader = fastexcel.read_excel(self.filePath)
                    current_sheets = list(reader.sheet_names)
                    if self.selected_sheet not in current_sheets:
                        issues.append(
                            f"Saved sheet '{self.selected_sheet}' is no longer available"
                        )
                except Exception as exc:
                    issues.append(f"Could not validate Excel sheets: {exc}")

        if issues:
            tooltip = "Workflow load validation failed:\n" + "\n".join(issues)
            self.node.grNode.setToolTip(tooltip)
            self.node.markInvalid(True)

        return issues

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
        """Load file using Polars table viewer for enhanced performance and memory efficiency"""
        # Clear any existing data to free memory first
        if hasattr(self, "data"):
            del self.data

        try:
            # Load preview data using the new simplified functions
            preview_df = self._read_file_based_on_type(fileName)

            if preview_df.height == 0:
                # Create empty DataFrame for display
                self.data = pl.DataFrame()
                if getattr(self, "table_viewer", None):
                    self.table_viewer.set_dataframe(self.data)
                return

            # Store the preview DataFrame as data for later use
            self.data = preview_df
            self._refresh_saved_input_metadata(preview_df)

            # Set the dataframe in the Polars table viewer
            if getattr(self, "table_viewer", None):
                self.table_viewer.set_dataframe(preview_df)

            logger.info(
                f"Loaded preview: {preview_df.height} rows, {len(preview_df.columns)} columns"
            )

        except Exception as e:
            logger.error(f"Error loading file {fileName}: {e}")
            # Set data to empty DataFrame on error
            self.data = pl.DataFrame()

            # Create error DataFrame for display
            error_df = pl.DataFrame({"Error": [f"Error loading file: {str(e)}"]})

            # Only update table viewer if it exists
            if getattr(self, "table_viewer", None):
                self.table_viewer.set_dataframe(error_df)

    def get_code(self) -> str:
        if not self.filePath:
            return ""

        code_lines = []
        code_lines.append("import polars as pl")
        code_lines.append("import os")
        code_lines.append("")
        code_lines.append("# Always use LazyFrame for memory efficiency")

        if self.file_type == "excel":
            # Excel file code generation using fastexcel with LazyFrame conversion
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
            else:
                load_params.append("header_row=None")
                if skip_rows > 0:
                    load_params.append(f"skip_rows={skip_rows}")

            # Add record limit if specified
            if self.record_limit > 0:
                load_params.append(f"n_rows={self.record_limit}")

            load_call = f"reader_{self.id}.load_sheet({', '.join(load_params)})"

            # Generate code for conversion to LazyFrame
            code_lines.append(f"excel_df_{self.id} = {load_call}")
            code_lines.append(f"# Convert to polars LazyFrame for memory efficiency")
            code_lines.append(f"try:")
            code_lines.append(
                f"    eager_df_{self.id} = excel_df_{self.id}.to_polars()"
            )
            code_lines.append(f"except AttributeError:")
            code_lines.append(
                f"    eager_df_{self.id} = pl.from_arrow(excel_df_{self.id}.to_arrow())"
            )
            code_lines.append(f"# Convert to LazyFrame immediately")
            code_lines.append(f"{self.variable_name} = eager_df_{self.id}.lazy()")

        elif self.file_type in ["csv", "txt"]:
            # CSV/TXT file code generation with LazyFrame
            read_params = ["infer_schema=False"]
            if self.delimiter != ",":
                read_params.append(f"separator='{self.delimiter}'")
            if not self.first_row_contains_field_names:
                read_params.append("has_header=False")

            # Always use lazy evaluation for maximum memory efficiency
            code_lines.append("# Using LazyFrame for optimal memory usage")

            # Build the scan_csv call
            lazy_call = f"pl.scan_csv('{self.filePath}'"
            if read_params:
                lazy_call += f", {', '.join(read_params)}"
            lazy_call += ")"

            code_lines.append(f"{self.variable_name} = {lazy_call}")

            # Apply record limit using lazy operations if specified
            if self.record_limit > 0:
                code_lines.append(f"# Apply record limit using lazy operations")
                code_lines.append(
                    f"{self.variable_name} = {self.variable_name}.head({self.record_limit})"
                )
        else:
            # Default to CSV with LazyFrame
            code_lines.append("# Default to CSV with LazyFrame")
            code_lines.append(
                f"{self.variable_name} = pl.scan_csv('{self.filePath}', infer_schema=False)"
            )

        # Add filename as field if requested - using lazy operations
        if self.output_filename_as_field:
            filename_var = f"filename_{self.id}"
            code_lines.append(f"# Add filename field using lazy operations")
            code_lines.append(f"{filename_var} = os.path.basename('{self.filePath}')")
            code_lines.append(
                f"{self.variable_name} = {self.variable_name}.with_columns(pl.lit({filename_var}).alias('FileName'))"
            )

        # Add a comment about LazyFrame usage
        code_lines.append("")
        code_lines.append(
            f"# {self.variable_name} is now a LazyFrame for memory-efficient processing"
        )
        code_lines.append(
            f"# Use .collect() only when you need to materialize the data"
        )

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> OrderedDict[Any, Any]:
        self._refresh_saved_input_metadata()
        return self.serialize_content_state(super().serialize())

    def deserialize(
        self, data: dict, hashmap: dict = {}, restore_id: Optional[bool] = True
    ) -> bool:
        res = super().deserialize(data, hashmap)

        try:
            self.deserialize_content_state(data)

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
        # Custom processing logic for the File Input node
        if not self.content.filePath:
            self.grNode.setToolTip("No file selected")
            self.markInvalid(True)
            self.param = []
            self.value = None
            return None

        if not self.content.check_file_path():
            self.markDirty(False)
            self.markInvalid(True)
            self.param = []
            self.value = None
            return None

        self.markDirty(False)
        self.markInvalid(False)

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
