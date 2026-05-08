import os
import polars as pl
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
    QSpacerItem,
    QSizePolicy,
    QComboBox,
    QLabel,
    QHBoxLayout,
    QCheckBox,
    QSpinBox,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import register_node, IONodes, NodeTypes
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget

from nodeeditor.utils import dumpException
from typing import Optional, Union
from loguru import logger


class FileOutputContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        # local Variables
        self.filePath = ""
        self.node = node
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # File format options
        self.file_format = "csv"  # Default format
        self.delimiter = ","  # Custom delimiter for CSV/text files
        self.use_streaming = True  # Use streaming for memory optimization
        self.include_bom = False  # BOM for text files
        self.compression = None  # Compression type

        # incoming variables
        self.incoming_variable = ""
        self.data: Optional[Union[pl.DataFrame, pl.LazyFrame]] = None

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon_: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon_)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        # File path input
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setPlaceholderText("Enter file path")
        self.filePathEdit.textChanged.connect(self._on_filePathEdit_textChanged)
        self.registerInputWidget(self.filePathEdit)

        # File format selection
        format_layout = QHBoxLayout()
        format_label = QLabel("Format:")
        self.formatCombo = QComboBox(self)
        self.formatCombo.addItems(
            ["csv", "excel", "parquet", "json", "ndjson", "ipc", "custom_delimited"]
        )
        self.formatCombo.currentTextChanged.connect(self._on_format_changed)
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.formatCombo)

        # Custom delimiter (for CSV/custom delimited)
        delimiter_layout = QHBoxLayout()
        delimiter_label = QLabel("Delimiter:")
        self.delimiterEdit = QLineEdit(self)
        self.delimiterEdit.setText(",")
        self.delimiterEdit.setMaximumWidth(50)
        self.delimiterEdit.textChanged.connect(self._on_delimiter_changed)
        delimiter_layout.addWidget(delimiter_label)
        delimiter_layout.addWidget(self.delimiterEdit)

        # Streaming option
        self.streamingCheckbox = QCheckBox("Use streaming (memory optimized)")
        self.streamingCheckbox.setChecked(True)
        self.streamingCheckbox.toggled.connect(self._on_streaming_changed)

        # BOM option
        self.bomCheckbox = QCheckBox("Include BOM (for UTF-8)")
        self.bomCheckbox.toggled.connect(self._on_bom_changed)

        # Save button
        self.saveButton = QPushButton("Save File", self)
        self.saveButton.clicked.connect(self.openFileDialog)

        if self.filePath:
            self.filePathEdit.setText(self.filePath)

        # Add widgets to layout
        dock_layout.addWidget(self.filePathEdit)
        dock_layout.addLayout(format_layout)
        dock_layout.addLayout(delimiter_layout)
        dock_layout.addWidget(self.streamingCheckbox)
        dock_layout.addWidget(self.bomCheckbox)
        dock_layout.addWidget(self.saveButton)

        dock_layout.setContentsMargins(0, 0, 0, 0)
        dock_layout.addSpacerItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        # Set initial visibility
        self._update_ui_visibility()

    def _on_filePathEdit_textChanged(self) -> None:
        self.filePath = self.filePathEdit.text()
        # Auto-detect format from file extension
        if self.filePath:
            ext = self.filePath.lower().split(".")[-1] if "." in self.filePath else ""
            if ext in ["csv", "txt"]:
                self.formatCombo.setCurrentText("csv")
            elif ext in ["xlsx", "xls"]:
                self.formatCombo.setCurrentText("excel")
            elif ext == "parquet":
                self.formatCombo.setCurrentText("parquet")
            elif ext == "json":
                self.formatCombo.setCurrentText("json")
            elif ext == "ndjson":
                self.formatCombo.setCurrentText("ndjson")
            elif ext == "ipc":
                self.formatCombo.setCurrentText("ipc")

    def _on_format_changed(self, format_type: str) -> None:
        self.file_format = format_type
        self._update_ui_visibility()

    def _on_delimiter_changed(self) -> None:
        self.delimiter = self.delimiterEdit.text() or ","

    def _on_streaming_changed(self, checked: bool) -> None:
        self.use_streaming = checked

    def _on_bom_changed(self, checked: bool) -> None:
        self.include_bom = checked

    def _update_ui_visibility(self) -> None:
        """Update UI element visibility based on selected format"""
        # Only update UI if elements have been created
        if not hasattr(self, "delimiterEdit") or not self.delimiterEdit:
            return

        show_delimiter = self.file_format in ["csv", "custom_delimited"]
        self.delimiterEdit.setVisible(show_delimiter)
        self.delimiterEdit.parent().layout().itemAt(0).widget().setVisible(
            show_delimiter
        )  # Label

        show_bom = self.file_format in ["csv", "custom_delimited", "json", "ndjson"]
        if hasattr(self, "bomCheckbox") and self.bomCheckbox:
            self.bomCheckbox.setVisible(show_bom)

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

        return True

    def openFileDialog(self) -> None:
        format_filters = {
            "csv": "CSV Files (*.csv);;Text Files (*.txt)",
            "excel": "Excel Files (*.xlsx *.xls)",
            "parquet": "Parquet Files (*.parquet)",
            "json": "JSON Files (*.json)",
            "ndjson": "NDJSON Files (*.ndjson)",
            "ipc": "Arrow IPC Files (*.ipc *.arrow)",
            "custom_delimited": "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)",
        }

        filter_str = format_filters.get(self.file_format, "All Files (*)")
        filter_str += ";;All Files (*)"

        filePath, _ = QFileDialog.getSaveFileName(
            self.parent(), f"Save {self.file_format.upper()} File", "", filter_str
        )

        if filePath:
            self.filePath = filePath
            self.filePathEdit.setText(filePath)
            # Auto-update format based on extension
            ext = filePath.lower().split(".")[-1] if "." in filePath else ""
            if ext in ["csv", "txt"] and self.file_format not in [
                "csv",
                "custom_delimited",
            ]:
                self.formatCombo.setCurrentText("csv")
            elif ext in ["xlsx", "xls"]:
                self.formatCombo.setCurrentText("excel")

    def get_code(self):
        if self.incoming_variable is None or self.incoming_variable == "":
            return "print('''No Incoming Variable''')\n"

        print(
            "🐍 File: InOut/file_output.py | Line: 238 | get_code ~ self.incoming_variable",
            self.incoming_variable,
            "may be no incomming variable",
        )

        code_lines = []
        var_name = self.incoming_variable

        # Add safety check for LazyFrame existence and convert to lazy if needed
        code_lines.append(
            f"# Ensure we're working with a LazyFrame for memory efficiency"
        )
        code_lines.append(f"if {var_name} is not None:")
        code_lines.append(f"    # Check if we have a LazyFrame or DataFrame")
        code_lines.append(f"    import polars as pl")
        code_lines.append(f"    if isinstance({var_name}, pl.DataFrame):")
        code_lines.append(f"        {var_name}_lazy = {var_name}.lazy()")
        code_lines.append(f"    elif isinstance({var_name}, pl.LazyFrame):")
        code_lines.append(f"        {var_name}_lazy = {var_name}")
        code_lines.append(f"    else:")
        code_lines.append(
            f"        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {{type({var_name})}}')"
        )
        code_lines.append("")
        code_lines.append("    try:")

        if self.file_format == "csv":
            # CSV with lazy streaming support
            options = []
            if self.delimiter != ",":
                options.append(f'separator="{self.delimiter}"')
            if self.include_bom:
                options.append("include_bom=True")

            code_lines.append(
                f"        # Using LazyFrame sink for optimal memory usage"
            )
            options_str = ", " + ", ".join(options) if options else ""
            code_lines.append(
                f"        {var_name}_lazy.sink_csv('{self.filePath}'{options_str})"
            )

        elif self.file_format == "custom_delimited":
            # Custom delimiter with lazy streaming
            delimiter = self.delimiter if self.delimiter else ","
            options = [f'separator="{delimiter}"']
            if self.include_bom:
                options.append("include_bom=True")

            options_str = ", " + ", ".join(options)
            code_lines.append(
                f"        # Custom delimiter: '{delimiter}' with LazyFrame"
            )
            code_lines.append(
                f"        {var_name}_lazy.sink_csv('{self.filePath}'{options_str})"
            )

        elif self.file_format == "excel":
            # Excel format - LazyFrame needs to be collected first
            code_lines.append(
                f"        # Excel requires eager evaluation - collecting LazyFrame"
            )
            code_lines.append(
                f"        {var_name}_lazy.collect().write_excel('{self.filePath}')"
            )

        elif self.file_format == "parquet":
            # Parquet with lazy execution for optimal memory usage
            code_lines.append(
                f"        # Using LazyFrame sink_parquet for zero-copy streaming"
            )
            code_lines.append(
                f"        {var_name}_lazy.sink_parquet('{self.filePath}', compression='snappy')"
            )

        elif self.file_format == "json":
            # JSON format - requires eager evaluation
            code_lines.append(
                f"        # JSON requires eager evaluation - collecting LazyFrame"
            )
            code_lines.append(
                f"        {var_name}_lazy.collect().write_json('{self.filePath}')"
            )

        elif self.file_format == "ndjson":
            # Newline-delimited JSON with lazy execution
            code_lines.append(
                f"        # Using LazyFrame sink_ndjson for memory-efficient streaming"
            )
            code_lines.append(f"        {var_name}_lazy.sink_ndjson('{self.filePath}')")

        elif self.file_format == "ipc":
            # Arrow IPC format with lazy execution
            code_lines.append(
                f"        # Using LazyFrame sink_ipc for ultra-fast columnar streaming"
            )
            code_lines.append(f"        {var_name}_lazy.sink_ipc('{self.filePath}')")

        else:
            # Default to CSV with lazy execution
            code_lines.append(f"        # Defaulting to CSV format with LazyFrame")
            code_lines.append(f"        {var_name}_lazy.sink_csv('{self.filePath}')")

        # Add success message (note: we can't easily get row count from LazyFrame without collecting)
        code_lines.append(
            f"        print(f'[SUCCESS] Successfully saved data to {self.filePath} using LazyFrame')"
        )
        code_lines.append("    except Exception as e:")
        code_lines.append(f"        print(f'[ERROR] Failed to save file: {{e}}')")
        code_lines.append(f"        raise e")
        code_lines.append("else:")
        code_lines.append(f"    print('[WARNING] No data to save')")

        return "\n".join(code_lines) + "\n"

    def serialize(self):
        res = super().serialize()
        res["filePath"] = self.filePath
        res["file_format"] = self.file_format
        res["delimiter"] = self.delimiter
        res["use_streaming"] = self.use_streaming
        res["include_bom"] = self.include_bom
        return res

    def deserialize(self, data, hashmap={}):
        logger.debug(f"FileOutput deserialize data: {data}")
        res = super().deserialize(data, hashmap)

        try:
            self.filePath = data.get("filePath", "")
            self.file_format = data.get("file_format", "csv")
            self.delimiter = data.get("delimiter", ",")
            self.use_streaming = data.get("use_streaming", True)
            self.include_bom = data.get("include_bom", False)

            # Update UI elements if they exist
            if hasattr(self, "filePathEdit") and self.filePathEdit:
                self.filePathEdit.setText(self.filePath)
            if hasattr(self, "formatCombo") and self.formatCombo:
                self.formatCombo.setCurrentText(self.file_format)
            if hasattr(self, "delimiterEdit") and self.delimiterEdit:
                self.delimiterEdit.setText(self.delimiter)
            if hasattr(self, "streamingCheckbox") and self.streamingCheckbox:
                self.streamingCheckbox.setChecked(self.use_streaming)
            if hasattr(self, "bomCheckbox") and self.bomCheckbox:
                self.bomCheckbox.setChecked(self.include_bom)

            # Update UI visibility
            if hasattr(self, "_update_ui_visibility"):
                self._update_ui_visibility()

            return True & res
        except Exception as e:
            dumpException(e)
            return res


@register_node(IONodes.FILE_OUTPUT, NodeTypes.IO)
class TriggerNode_FileOutput(TriggerNode):
    icon = "node_file_output"
    node_code = IONodes.FILE_OUTPUT
    node_title = "File Output"
    node_type = NodeTypes.IO
    content_label_objname = "trigger_node_file_output"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[])
        # self.eval()

    def initInnerClasses(self) -> None:
        self.content: FileOutputContent = FileOutputContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

    def processInputs(self, input_values):
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)  # type: ignore
        input_value = input_values[this_socket_index][socket_index]

        if not input_value:
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid(True)
            return None

        self.markDirty(False)
        self.markInvalid(False)

        self.content.incoming_variable = input_value.get("variable_name")
        self.grNode.setToolTip("")

        print(f"Value Received in {self.__class__.__name__}:", input_value)

        return input_value

    def get_code(self):
        # print("getting code for file output: ", self.content.get_code())
        return self.content.get_code()

    # def params(self):
    # param = {
    #     "columns": self.content.get_columns(),
    #     "data": self.content.data
    # }
    # return param
