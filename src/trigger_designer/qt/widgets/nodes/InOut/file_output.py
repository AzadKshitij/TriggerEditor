"""File Output node: Qt wrapper only; the writer lives in core/shaping."""

from __future__ import annotations

import json
import os

from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QLineEdit,
    QVBoxLayout,
)

from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    register_node,
)
from trigger_designer.core.shaping import file_output as core
from trigger_designer.qt.helpers.shaping_support import ShapingContent
from trigger_designer.qt.node_base import (
    TriggerGraphicsNode,
    TriggerNode,
)
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    FormRow,
    IconButton,
    NoWheelComboBox,
)

_FORMAT_LABELS = (
    ("csv", "CSV"),
    ("excel", "Excel"),
    ("parquet", "Parquet"),
    ("json", "JSON"),
    ("ndjson", "NDJSON"),
    ("ipc", "Arrow IPC"),
    ("custom_delimited", "Custom delimited"),
)

_EXTENSION_FORMATS = {
    "csv": "csv",
    "txt": "csv",
    "xlsx": "excel",
    "xls": "excel",
    "parquet": "parquet",
    "json": "json",
    "ndjson": "ndjson",
    "ipc": "ipc",
    "arrow": "ipc",
}


class FileOutputContent(ShapingContent):
    """Destination and format settings for the sink."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.file_output"
    OUTPUT_KINDS = ()
    INPUTS = 1
    HISTORY = "File Output"
    SUMMARY = "write to file"

    # -- dock ------------------------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        destination = ConfigSection("Destination")
        destination._undo_composite = True
        self.destination_section = destination

        self.filePathEdit = QLineEdit()
        self.filePathEdit.setMinimumHeight(30)
        self.filePathEdit.setPlaceholderText("Enter file path")
        self.filePathEdit.setText(str(self.settings.get("filePath") or ""))
        self._debounced(
            self.filePathEdit.textChanged,
            lambda: self._commit_path(self.filePathEdit.text()),
        )
        self.saveButton = IconButton.themed(
            "Browse for save location",
            rsm_icon=self.node.rsm.get("icon_save"),
            theme_fallback="document-save",
        )
        self.saveButton.clicked.connect(self.openFileDialog)
        destination.addWidget(
            FormRow(
                "File",
                self.filePathEdit,
                label_width=32,
                action=self.saveButton,
            )
        )
        dock_layout.addWidget(destination)

        options = ConfigSection("Format")
        options._undo_composite = True
        self.format_section = options

        self.formatCombo = NoWheelComboBox()
        self.formatCombo.setMinimumHeight(30)
        self.formatCombo.setMaxVisibleItems(len(_FORMAT_LABELS))
        for value, label in _FORMAT_LABELS:
            self.formatCombo.addItem(label, value)
        index = self.formatCombo.findData(
            str(self.settings.get("file_format") or "csv")
        )
        self.formatCombo.setCurrentIndex(max(0, index))
        self.formatCombo.currentIndexChanged.connect(
            lambda _index: self.set_setting(
                "file_format",
                self.formatCombo.currentData() or "csv",
                "File Output Format Changed",
            )
        )
        options.addWidget(FormRow("Format", self.formatCombo, label_width=88))

        self.delimiterEdit = QLineEdit()
        self.delimiterEdit.setMinimumHeight(30)
        self.delimiterEdit.setMaximumWidth(60)
        self.delimiterEdit.setText(str(self.settings.get("delimiter") or ","))
        self._debounced(
            self.delimiterEdit.textChanged,
            lambda: self.set_setting(
                "delimiter",
                self.delimiterEdit.text() or ",",
                "File Output Delimiter Changed",
            ),
        )
        self.delimiter_row = FormRow("Delimiter", self.delimiterEdit, label_width=88)
        options.addWidget(self.delimiter_row)

        self.bom_check = QCheckBox("Include BOM")
        self.bom_check.setChecked(bool(self.settings.get("include_bom", False)))
        self.bom_check.toggled.connect(
            lambda checked: self.set_setting(
                "include_bom", bool(checked), "File Output BOM Changed"
            )
        )
        self.bom_row = FormRow("Encoding", self.bom_check, label_width=88)
        options.addWidget(self.bom_row)

        dock_layout.addWidget(options)
        dock_layout.addStretch()
        self._apply_visibility()
        self._refresh_counts()

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        file_format = str(self.settings.get("file_format") or "csv")
        path = str(self.settings.get("filePath") or "")
        chips: list[tuple[str, str]] = [(file_format, "accent")]
        if path:
            chips.append(("path set", ""))
        return chips, os.path.basename(path)

    def _refresh_counts(self) -> None:
        self.refresh_dock_context()

    def after_change(self) -> None:
        self._sync_widgets_from_model()
        self._refresh_counts()

    def _sync_widgets_from_model(self) -> None:
        """Project settings onto the custom controls (undo/redo/load)."""
        if getattr(self, "formatCombo", None) is None:
            return
        path = str(self.settings.get("filePath") or "")
        if self.filePathEdit.text() != path:
            blocked = self.filePathEdit.blockSignals(True)
            try:
                self.filePathEdit.setText(path)
            finally:
                self.filePathEdit.blockSignals(blocked)

        index = self.formatCombo.findData(
            str(self.settings.get("file_format") or "csv")
        )
        if index >= 0 and self.formatCombo.currentIndex() != index:
            blocked = self.formatCombo.blockSignals(True)
            try:
                self.formatCombo.setCurrentIndex(index)
            finally:
                self.formatCombo.blockSignals(blocked)

        delimiter = str(self.settings.get("delimiter") or ",")
        if self.delimiterEdit.text() != delimiter:
            blocked = self.delimiterEdit.blockSignals(True)
            try:
                self.delimiterEdit.setText(delimiter)
            finally:
                self.delimiterEdit.blockSignals(blocked)

        include_bom = bool(self.settings.get("include_bom", False))
        if self.bom_check.isChecked() != include_bom:
            blocked = self.bom_check.blockSignals(True)
            try:
                self.bom_check.setChecked(include_bom)
            finally:
                self.bom_check.blockSignals(blocked)

        self._apply_visibility()

    def _apply_visibility(self) -> None:
        if getattr(self, "delimiter_row", None) is None:
            return
        delimited = self.settings.get("file_format") in (
            "csv",
            "custom_delimited",
        )
        self.delimiter_row.setVisible(delimited)
        self.bom_row.setVisible(delimited)

    # -- commits ----------------------------------------------------------
    def _commit_path(self, path: str) -> None:
        self.set_setting(
            "filePath", path, "File Output Path Changed", "File Output-path"
        )
        extension = path.lower().rsplit(".", 1)[-1] if "." in path else ""
        detected = _EXTENSION_FORMATS.get(extension)
        if detected and detected != self.settings.get("file_format"):
            self.set_setting("file_format", detected, "File Output Format Changed")

    def openFileDialog(self) -> None:
        file_format = str(self.settings.get("file_format") or "csv")
        filters = {
            "csv": "CSV Files (*.csv);;Text Files (*.txt)",
            "excel": "Excel Files (*.xlsx *.xls)",
            "parquet": "Parquet Files (*.parquet)",
            "json": "JSON Files (*.json)",
            "ndjson": "NDJSON Files (*.ndjson)",
            "ipc": "Arrow IPC Files (*.ipc *.arrow)",
            "custom_delimited": "Text Files (*.txt);;CSV Files (*.csv)",
        }
        filter_str = filters.get(file_format, "All Files (*)")
        path, _selected = QFileDialog.getSaveFileName(
            self.parent(), f"Save {file_format.upper()} File", "", filter_str
        )
        if path:
            self.filePathEdit.setText(path)
            self._commit_path(path)

    # -- code generation --------------------------------------------------
    def get_code(self) -> str:
        if not self.input_vars or not self.input_vars[0]:
            return (
                "raise ValueError('File Output: no incoming data - connect an input')\n"
            )
        payload = json.dumps(self.settings, sort_keys=True)
        return (
            "import json\n"
            "from trigger_designer.core.shaping.file_output import "
            "write_node as _write_node\n"
            f"_write_node([{self.input_vars[0]}], json.loads({payload!r}))\n"
        )

    # -- persistence ------------------------------------------------------
    def deserialize(self, data, hashmap={}):  # noqa: B006
        if "settings" not in data and ("filePath" in data or "file_format" in data):
            data = dict(data)
            data["settings"] = {
                "filePath": str(data.get("filePath") or ""),
                "file_format": str(data.get("file_format") or "csv"),
                "delimiter": str(data.get("delimiter") or ","),
                "use_streaming": bool(data.get("use_streaming", True)),
                "include_bom": bool(data.get("include_bom", False)),
                "compression": data.get("compression"),
            }
        return super().deserialize(data, hashmap)


@register_node(IONodes.FILE_OUTPUT, NodeTypes.IO)
class TriggerNode_FileOutput(TriggerNode):
    icon = "node_file_output"
    node_code = IONodes.FILE_OUTPUT
    node_title = "File Output"
    node_type = NodeTypes.IO
    content_label_objname = "trigger_node_file_output"
    style = {}  # noqa: RUF012 - shared empty node style

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[])

    def initInnerClasses(self) -> None:
        self.content: FileOutputContent = FileOutputContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):
        upstream = socket = None
        try:
            upstream, socket = self.getInputWithSocket(0)
        except Exception:  # noqa: BLE001 - unconnected input
            upstream = socket = None
        entry = None
        if upstream is not None and socket is not None and input_values:
            row = input_values[0]
            if row and socket.index < len(row):
                entry = row[socket.index]
        if entry is None or entry.get("data") is None:
            self.content.frames[0] = None
            self.content.input_vars[0] = ""
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid(True)
            return None

        self.content.frames[0] = entry["data"]
        self.content.input_vars[0] = entry.get("variable_name") or ""
        self.markDirty(False)
        self.markInvalid(False)
        self.grNode.setToolTip("")
        return entry

    def get_code(self) -> str:
        return self.content.get_code()
