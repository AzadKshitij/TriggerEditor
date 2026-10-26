import copy
import os
from collections import Counter, OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any

import fastexcel
import polars as pl
from loguru import logger
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from qtpy.QtCore import QTimer, Signal
from qtpy.QtGui import QPixmap, QStandardItem, QStandardItemModel
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.input_source import (
    SOURCE_KEYS,
    build_source,
    list_db_tables,
)
from trigger_designer.core.inputs import (
    DEFAULT_EXCLUDE,
    InputReadError,
    detect_file_type,
    effective_mode,
    io_path,
    list_source_files,
    resolve_input_files,
    resolve_stored_path,
    to_stored_paths,
)
from trigger_designer.core.node_configuration import IONodes, NodeTypes, register_node
from trigger_designer.qt.helpers import global_logger
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerGraphicsNode,
    TriggerNode,
    frame_schema,
)
from trigger_designer.qt.undo.protocol import is_syncing
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    ConfigSection,
    FormRow,
    IconButton,
    NoWheelComboBox,
)

_FILENAME_COLUMN = "FileName"
_BULK_QSS_FALLBACK = ":/qss_icons/dark/rc/up_arrow.png"


def _workflow_dir(scene) -> str | None:
    """Plan 09 F-F will own ``workflow_dir``; fall back to the loaded file."""
    value = getattr(scene, "workflow_dir", None)
    if value:
        return value
    filename = getattr(scene, "filename", None)
    if filename:
        return os.path.dirname(os.path.abspath(filename))
    return None


def migrate_file_input_state(content: "FileInputContent") -> None:
    """Hook for future content migrations; version 1 maps to defaults."""
    if getattr(content, "input_schema_version", 1) < 2:
        content.input_schema_version = 1


if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene


class FileInputContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    max_missing_file_attempts = 5
    evaluate = Signal()
    serialized_state_schema = {  # noqa: RUF012 - the mixin reads this class map
        "filePath": {"default": ""},
        "filePathRel": {"default": ""},
        "input_schema_version": {"default": 1},
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
        "file_name_column_name": {"default": _FILENAME_COLUMN},
        "file_name_value": {"default": "name"},
        "include_patterns": {"default": []},
        "exclude_patterns": {"default": list(DEFAULT_EXCLUDE)},
        "recursive": {"default": False},
        "file_order": {"default": "name"},
        "schema_mismatch": {"default": "union"},
        "on_file_error": {"default": "stop"},
        "max_files": {"default": 10000},
        "encoding": {"default": "utf8"},
        "read_as_text": {"default": False},
        "json_nested": {"default": "text"},
        "sheet_mode": {"default": "one"},
        "selected_sheets": {"default": []},
        "add_sheet_name_column": {"default": False},
        "sheet_name_column_name": {"default": "SheetName"},
        "db_mode": {"default": "table"},
        "db_table": {"default": ""},
        "db_query": {"default": ""},
    }

    #: Class-level defaults keep ``FileInputContent.__new__`` usable in unit
    #: tests (several build the content without Qt). Never mutate the lists in
    #: place: assign a fresh list instead.
    input_schema_version = 1
    filePathRel = ""
    file_name_column_name = _FILENAME_COLUMN
    file_name_value = "name"
    include_patterns: list = []  # noqa: RUF012 - class default for __new__
    exclude_patterns: list = list(DEFAULT_EXCLUDE)  # noqa: RUF012
    recursive = False
    file_order = "name"
    schema_mismatch = "union"
    on_file_error = "stop"
    max_files = 10000
    encoding = "utf8"
    read_as_text = False
    json_nested = "text"
    sheet_mode = "one"
    selected_sheets: list = []  # noqa: RUF012 - class default for __new__
    add_sheet_name_column = False
    sheet_name_column_name = "SheetName"
    db_mode = "table"
    db_table = ""
    db_query = ""
    last_report = None
    last_error = None
    _type_user_set = False

    def __init__(self, node: "TriggerNode", parent: QWidget | None = None) -> None:
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

        # New input-type settings. Lists are fresh per instance; the model is
        # projected onto widgets, never mutated in place.
        self.filePathRel = ""
        self.input_schema_version = 1
        self.file_name_column_name = _FILENAME_COLUMN
        self.file_name_value = "name"
        self.include_patterns: list[str] = []
        self.exclude_patterns: list[str] = list(DEFAULT_EXCLUDE)
        self.recursive = False
        self.file_order = "name"
        self.schema_mismatch = "union"
        self.on_file_error = "stop"
        self.max_files = 10000
        self.encoding = "utf8"
        self.read_as_text = False
        self.json_nested = "text"
        self.sheet_mode = "one"
        self.selected_sheets: list[str] = []
        self.add_sheet_name_column = False
        self.sheet_name_column_name = "SheetName"
        self.db_mode = "table"
        self.db_table = ""
        self.db_query = ""
        self.last_report = None
        self.last_error = None
        self._type_user_set = False

        # pass on variables
        self.data: pl.DataFrame | pl.LazyFrame = pl.DataFrame()
        self.variable_name = f"var_file_input_{self.id}"
        self._missing_file_attempts: dict[str, int] = {}
        self._path_timer = None
        self._include_timer = None
        self._exclude_timer = None
        self._filename_column_timer = None
        self._delimiter_timer = None
        self._sheet_column_timer = None
        self._query_timer = None

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

    def initUI(self, _icon: QPixmap | None = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self.table_viewer = None
        self.tableWidget = None
        self._build_source_section()
        self._build_files_section()
        self._build_settings_section()
        self._build_db_section()

        dock_layout.addWidget(self.source_section)
        dock_layout.addWidget(self.files_section)
        dock_layout.addWidget(self.settings_section)
        dock_layout.addWidget(self.db_section)
        dock_layout.addStretch()

        if self.file_type in ("sqlite", "duckdb") and self.filePath:
            self._refresh_db_tables()
        self._apply_visibility()
        self._sync_widgets_from_model()
        if self.filePath and (self.data is None or not frame_schema(self.data)):
            if self._use_legacy_path():
                self.loadFile(self.filePath)
            else:
                self._load_via_builder()
        self._refresh_files_table()
        self._refresh_file_input_counts()

    # -- dock construction -------------------------------------------------
    def _build_source_section(self) -> None:
        section = ConfigSection()
        section._undo_composite = True
        self.source_section = section

        self.filePathEdit = QLineEdit()
        self.filePathEdit.setPlaceholderText(
            "File, folder or pattern  (D:\\data\\*.csv)"
        )
        self.filePathEdit.setAccessibleName("Source path")
        self.filePathEdit.setMinimumHeight(30)
        self._path_timer = self._make_timer("_path_timer", self._commit_path)
        self.filePathEdit.textChanged.connect(self._path_timer.start)

        buttons = QWidget()
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(2)
        self.loadButton = IconButton.themed(
            "Browse for file",
            rsm_icon=self.node.rsm.get("icon_folder_open"),
            qss_fallback=_BULK_QSS_FALLBACK,
        )
        self.loadButton.clicked.connect(self.openFileDialog)
        self.folderButton = IconButton.themed(
            "Browse for folder",
            rsm_icon=self.node.rsm.get("icon_files"),
            qss_fallback=_BULK_QSS_FALLBACK,
        )
        self.folderButton.clicked.connect(self.openFolderDialog)
        buttons_layout.addWidget(self.loadButton)
        buttons_layout.addWidget(self.folderButton)
        section.addWidget(
            FormRow("Source", self.filePathEdit, label_width=56, action=buttons)
        )

        self.typeCombo = NoWheelComboBox()
        self.typeCombo.setMinimumHeight(30)
        self.typeCombo.setAccessibleName("File type")
        for label, value in (
            ("CSV", "csv"),
            ("Text", "txt"),
            ("Excel", "excel"),
            ("Parquet", "parquet"),
            ("JSON", "json"),
            ("JSON Lines", "ndjson"),
            ("SQLite", "sqlite"),
            ("DuckDB", "duckdb"),
        ):
            self.typeCombo.addItem(label, value)
        self.typeCombo.currentIndexChanged.connect(self._on_type_combo_changed)
        self.type_row = FormRow("Type", self.typeCombo, label_width=56)
        section.addWidget(self.type_row)

    def _build_files_section(self) -> None:
        section = ConfigSection("Files")
        section._undo_composite = True
        self.files_section = section

        self.includeEdit = QLineEdit()
        self.includeEdit.setPlaceholderText("*.csv; *.tsv")
        self.includeEdit.setAccessibleName("Include patterns")
        self.includeEdit.setMinimumHeight(30)
        self.includeEdit.setToolTip(
            "Semicolon-separated name patterns. Empty = all files of this type"
        )
        self._include_timer = self._make_timer(
            "_include_timer", lambda: self._commit_patterns("include_patterns")
        )
        self.includeEdit.textChanged.connect(self._include_timer.start)
        self.include_row = FormRow("Include", self.includeEdit, label_width=64)
        section.addWidget(self.include_row)

        self.excludeEdit = QLineEdit()
        self.excludeEdit.setAccessibleName("Exclude patterns")
        self.excludeEdit.setMinimumHeight(30)
        self.excludeEdit.setToolTip(
            "Semicolon-separated name patterns to skip. Default skips "
            "Excel lock files (~$*) and hidden files"
        )
        self._exclude_timer = self._make_timer(
            "_exclude_timer", lambda: self._commit_patterns("exclude_patterns")
        )
        self.excludeEdit.textChanged.connect(self._exclude_timer.start)
        self.exclude_row = FormRow("Exclude", self.excludeEdit, label_width=64)
        section.addWidget(self.exclude_row)

        self.recursiveCheck = QCheckBox("Include subfolders")
        self.recursiveCheck.setToolTip(
            "Walk subfolders. Symbolic links are not followed"
        )
        self.recursiveCheck.toggled.connect(self._on_recursive_toggled)
        section.addWidget(self.recursiveCheck)

        self.orderCombo = NoWheelComboBox()
        self.orderCombo.setMinimumHeight(30)
        self.orderCombo.addItem("Name (natural)", "name")
        self.orderCombo.addItem("Modified date", "modified")
        self.orderCombo.setToolTip(
            "Files are read in this order; 'part_2' comes before 'part_10'"
        )
        self.orderCombo.currentIndexChanged.connect(self._on_order_changed)
        section.addWidget(FormRow("Order", self.orderCombo, label_width=64))

        self.schemaCombo = NoWheelComboBox()
        self.schemaCombo.setMinimumHeight(30)
        self.schemaCombo.addItem("Union by name", "union")
        self.schemaCombo.addItem("Must match", "error")
        self.schemaCombo.setToolTip("Union fills missing columns with empty values")
        self.schemaCombo.currentIndexChanged.connect(self._on_schema_mode_changed)
        section.addWidget(FormRow("Columns", self.schemaCombo, label_width=64))

        self.badFileCombo = NoWheelComboBox()
        self.badFileCombo.setMinimumHeight(30)
        self.badFileCombo.addItem("Stop with error", "stop")
        self.badFileCombo.addItem("Skip and report", "skip")
        self.badFileCombo.currentIndexChanged.connect(self._on_on_file_error_changed)
        section.addWidget(FormRow("Bad file", self.badFileCombo, label_width=64))

        self.filesTable = QTableView()
        self.filesTable.setObjectName("ColumnTable")
        self.filesTable.setAccessibleName("Files read")
        self.filesTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.filesTable.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.filesTable.verticalHeader().setVisible(False)
        self.filesTable.verticalHeader().setDefaultSectionSize(22)
        self.filesTable.setMinimumHeight(60)
        self.filesTable.setMaximumHeight(160)
        self._files_model = QStandardItemModel(0, 3, self)
        self._files_model.setHorizontalHeaderLabels(["File", "Status", "Columns"])
        self.filesTable.setModel(self._files_model)
        self.filesTable.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.filesTable.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.filesTable.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        section.addWidget(self.filesTable)

    def _build_settings_section(self) -> None:
        section = ConfigSection()
        section._undo_composite = True
        self.settings_section = section

        self.outputFilenameCheckBox = QCheckBox("Output filename as field")
        self.outputFilenameCheckBox.setToolTip("Add the source file name as a column")
        self.outputFilenameCheckBox.toggled.connect(self._on_filename_field_toggled)
        section.addWidget(self.outputFilenameCheckBox)
        self.output_filename_widget = self.outputFilenameCheckBox

        self.fileNameColumnEdit = QLineEdit()
        self.fileNameColumnEdit.setMinimumHeight(30)
        self.fileNameColumnEdit.setAccessibleName("Filename column name")
        self._filename_column_timer = self._make_timer(
            "_filename_column_timer",
            lambda: self._commit_text(
                "file_name_column_name",
                self.fileNameColumnEdit.text(),
                "Filename Column Renamed",
                merge_key="fi-fname",
            ),
        )
        self.fileNameColumnEdit.textChanged.connect(self._filename_column_timer.start)
        self.filename_column_row = FormRow(
            "Column name", self.fileNameColumnEdit, label_width=104
        )
        section.addWidget(self.filename_column_row)

        self.fileNameValueCombo = NoWheelComboBox()
        self.fileNameValueCombo.setMinimumHeight(30)
        self.fileNameValueCombo.addItem("File name", "name")
        self.fileNameValueCombo.addItem("Full path", "path")
        self.fileNameValueCombo.addItem("Relative path", "relative")
        self.fileNameValueCombo.currentIndexChanged.connect(
            self._on_filename_value_changed
        )
        self.filename_value_row = FormRow(
            "Value", self.fileNameValueCombo, label_width=104
        )
        section.addWidget(self.filename_value_row)

        self.delimiterEdit = QLineEdit()
        self.delimiterEdit.setMinimumHeight(30)
        self.delimiterEdit.setMaximumWidth(60)
        self.delimiterEdit.setPlaceholderText("e.g., , ; | \\t")
        self._delimiter_timer = self._make_timer(
            "_delimiter_timer", self._commit_delimiter
        )
        self.delimiterEdit.textChanged.connect(self._delimiter_timer.start)
        self.delimiter_row = FormRow("Delimiter", self.delimiterEdit, label_width=104)
        section.addWidget(self.delimiter_row)
        self.delimiter_widget = self.delimiterEdit

        self.firstRowFieldNamesCheckBox = QCheckBox("First row holds field names")
        self.firstRowFieldNamesCheckBox.toggled.connect(self._on_header_row_toggled)
        section.addWidget(self.firstRowFieldNamesCheckBox)
        self.first_row_widget = self.firstRowFieldNamesCheckBox

        self.encodingCombo = NoWheelComboBox()
        self.encodingCombo.setMinimumHeight(30)
        self.encodingCombo.addItem("UTF-8", "utf8")
        self.encodingCombo.addItem("UTF-8 (replace bad bytes)", "utf8-lossy")
        self.encodingCombo.setToolTip(
            "Polars supports UTF-8 only; choose the lossy mode for Latin-1 files"
        )
        self.encodingCombo.currentIndexChanged.connect(self._on_encoding_changed)
        self.encoding_row = FormRow("Encoding", self.encodingCombo, label_width=104)
        section.addWidget(self.encoding_row)

        self.sheetModeCombo = NoWheelComboBox()
        self.sheetModeCombo.setMinimumHeight(30)
        self.sheetModeCombo.addItem("One sheet", "one")
        self.sheetModeCombo.addItem("All sheets", "all")
        self.sheetModeCombo.addItem("Chosen sheets", "chosen")
        self.sheetModeCombo.currentIndexChanged.connect(self._on_sheet_mode_changed)
        self.sheet_mode_row = FormRow("Sheets", self.sheetModeCombo, label_width=104)
        section.addWidget(self.sheet_mode_row)

        self.selectedSheetCombo = NoWheelComboBox()
        self.selectedSheetCombo.setMinimumHeight(30)
        self.selectedSheetCombo.currentTextChanged.connect(self._on_sheet_changed)
        self.selected_sheet_row = FormRow(
            "Sheet", self.selectedSheetCombo, label_width=104
        )
        section.addWidget(self.selected_sheet_row)
        self.selected_sheet_widget = self.selectedSheetCombo

        self.startRowSpinBox = QSpinBox()
        self.startRowSpinBox.setMinimumHeight(30)
        self.startRowSpinBox.setMinimum(1)
        self.startRowSpinBox.setMaximum(999999)
        self.startRowSpinBox.valueChanged.connect(self._on_start_row_changed)
        self.start_row_row = FormRow("Start row", self.startRowSpinBox, label_width=104)
        section.addWidget(self.start_row_row)
        self.start_row_widget = self.startRowSpinBox

        self.sheetsChecklist = ColumnChecklist()
        self.sheetsChecklist.changed.connect(self._on_sheets_checked)
        self.sheets_row = FormRow("Chosen", self.sheetsChecklist, label_width=104)
        section.addWidget(self.sheets_row)

        self.sheetColumnCheck = QCheckBox("Add sheet name column")
        self.sheetColumnCheck.toggled.connect(self._on_sheet_column_toggled)
        section.addWidget(self.sheetColumnCheck)

        self.sheetColumnEdit = QLineEdit()
        self.sheetColumnEdit.setMinimumHeight(30)
        self.sheetColumnEdit.setAccessibleName("Sheet name column")
        self._sheet_column_timer = self._make_timer(
            "_sheet_column_timer",
            lambda: self._commit_text(
                "sheet_name_column_name",
                self.sheetColumnEdit.text(),
                "Sheet Column Renamed",
                merge_key="fi-sheetcol",
            ),
        )
        self.sheetColumnEdit.textChanged.connect(self._sheet_column_timer.start)
        self.sheet_column_row = FormRow(
            "Column name", self.sheetColumnEdit, label_width=104
        )
        section.addWidget(self.sheet_column_row)

        self.nestedCombo = NoWheelComboBox()
        self.nestedCombo.setMinimumHeight(30)
        self.nestedCombo.addItem("As text", "text")
        self.nestedCombo.addItem("Keep as is", "keep")
        self.nestedCombo.currentIndexChanged.connect(self._on_nested_changed)
        self.nested_row = FormRow("Nested values", self.nestedCombo, label_width=104)
        section.addWidget(self.nested_row)

        self.asTextCheck = QCheckBox("Read all columns as text")
        self.asTextCheck.toggled.connect(self._on_read_as_text_toggled)
        self.as_text_widget = self.asTextCheck
        section.addWidget(self.asTextCheck)

        self.limitSpin = QSpinBox()
        self.limitSpin.setMinimumHeight(30)
        self.limitSpin.setRange(0, 2_000_000_000)
        self.limitSpin.setSpecialValueText("All")
        self.limitSpin.setToolTip("0 = read every row")
        self.limitSpin.valueChanged.connect(self._on_limit_changed)
        self.limit_row = FormRow("Row limit", self.limitSpin, label_width=104)
        section.addWidget(self.limit_row)

    def _build_db_section(self) -> None:
        section = ConfigSection(
            "",
            info="Read-only. One SELECT statement. The database is never modified.",
        )
        section._undo_composite = True
        self.db_section = section

        self.dbModeCombo = NoWheelComboBox()
        self.dbModeCombo.setMinimumHeight(30)
        self.dbModeCombo.addItem("Table", "table")
        self.dbModeCombo.addItem("SQL query", "query")
        self.dbModeCombo.currentIndexChanged.connect(self._on_db_mode_changed)
        section.addWidget(FormRow("Read", self.dbModeCombo, label_width=64))

        self.dbTableCombo = NoWheelComboBox()
        self.dbTableCombo.setMinimumHeight(30)
        self.dbTableCombo.currentTextChanged.connect(self._on_db_table_changed)
        self.dbRefreshButton = IconButton.themed(
            "Reload table list",
            rsm_icon=self.node.rsm.get("icon_refresh"),
            qss_fallback=_BULK_QSS_FALLBACK,
        )
        self.dbRefreshButton.clicked.connect(self._refresh_db_tables)
        self.db_table_row = FormRow(
            "Table",
            self.dbTableCombo,
            label_width=64,
            action=self.dbRefreshButton,
        )
        section.addWidget(self.db_table_row)

        self.dbQueryEdit = QPlainTextEdit()
        self.dbQueryEdit.setMinimumHeight(90)
        self.dbQueryEdit.setPlaceholderText("SELECT ... (read-only)")
        self.dbQueryEdit.setAccessibleName("SQL query")
        self._query_timer = self._make_timer(
            "_query_timer",
            lambda: self._commit_text(
                "db_query",
                self.dbQueryEdit.toPlainText(),
                "SQL Query Changed",
                merge_key="fi-query",
            ),
        )
        self.dbQueryEdit.textChanged.connect(self._query_timer.start)
        self.db_query_row = FormRow("Query", self.dbQueryEdit, label_width=64)
        section.addWidget(self.db_query_row)

    def _make_timer(self, _name: str, slot) -> QTimer:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(300)
        timer.timeout.connect(slot)
        return timer

    # -- model <-> widgets -------------------------------------------------
    def _apply_setting(
        self,
        key: str,
        new,
        text: str,
        *,
        merge_key: str | None = None,
        rebuild: bool = False,
    ) -> None:
        if is_syncing(self) or self.history.is_restoring_history:
            return
        old = getattr(self, key)
        if new == old:
            return
        setattr(self, key, copy.deepcopy(new))
        self._after_setting_changed(key)
        self.refresh_dock_context()
        pushed = self.push_property_change(
            (key,), old, new, text, rebuild=rebuild, merge_key=merge_key
        )
        if not pushed:
            # A folded push does not run redo(), so the projection did not
            # re-evaluate the graph. Do it here instead.
            self.evaluate.emit()
        self._apply_visibility()

    def _after_setting_changed(self, key: str) -> None:
        if (
            key
            in (
                "file_type",
                "sheet_mode",
                "selected_sheet",
                "available_sheets",
                "source_state",
            )
            and self.file_type == "excel"
            and self.filePath
        ):
            self._refresh_sheets()
        if (
            key in ("file_type", "db_mode", "db_table", "source_state")
            and self.file_type in ("sqlite", "duckdb")
            and self.filePath
        ):
            self._refresh_db_tables()

    def _commit_text(self, key: str, value, text: str, *, merge_key: str) -> None:
        self._apply_setting(key, value, text, merge_key=merge_key)

    def _commit_path(self) -> None:
        text = self.filePathEdit.text().strip()
        new_type = self.file_type
        if text and not self._type_user_set:
            detected = detect_file_type(text)
            if detected:
                new_type = detected
        if new_type != self.file_type:
            old_state = self.source_state
            new_state = dict(old_state)
            new_state["filePath"] = text
            new_state["file_type"] = new_type
            self._apply_setting(
                "source_state", new_state, "Source Path Changed", rebuild=True
            )
            return
        self._apply_setting(
            "filePath", text, "Source Path Changed", merge_key="fi-path"
        )

    def _commit_patterns(self, key: str) -> None:
        edit = self.includeEdit if key == "include_patterns" else self.excludeEdit
        parts = [part.strip() for part in edit.text().split(";") if part.strip()]
        text = (
            "Include Patterns Changed"
            if key == "include_patterns"
            else "Exclude Patterns Changed"
        )
        self._apply_setting(
            key,
            parts,
            text,
            merge_key="fi-include" if key == "include_patterns" else "fi-exclude",
        )

    def _commit_delimiter(self) -> None:
        text = self.delimiterEdit.text()
        delimiter = {
            "\\t": "\t",
            "\\n": "\n",
            "\\r": "\r",
        }.get(text, text)
        self._apply_setting(
            "delimiter", delimiter, "Delimiter Changed", merge_key="fi-delim"
        )

    def _on_type_combo_changed(self, _index: int) -> None:
        value = self.typeCombo.currentData()
        if value is None:
            return
        self._type_user_set = True
        self._apply_setting("file_type", value, "File Type Changed", rebuild=True)

    def _on_recursive_toggled(self, checked: bool) -> None:
        self._apply_setting("recursive", checked, "Subfolders Toggled")

    def _on_order_changed(self, _index: int) -> None:
        value = self.orderCombo.currentData()
        if value:
            self._apply_setting("file_order", value, "File Order Changed")

    def _on_schema_mode_changed(self, _index: int) -> None:
        value = self.schemaCombo.currentData()
        if value:
            self._apply_setting("schema_mismatch", value, "Schema Mode Changed")

    def _on_on_file_error_changed(self, _index: int) -> None:
        value = self.badFileCombo.currentData()
        if value:
            self._apply_setting("on_file_error", value, "Bad File Mode Changed")

    def _on_filename_field_toggled(self, checked: bool) -> None:
        self._apply_setting(
            "output_filename_as_field", checked, "Filename Field Toggled"
        )

    def _on_filename_value_changed(self, _index: int) -> None:
        value = self.fileNameValueCombo.currentData()
        if value:
            self._apply_setting("file_name_value", value, "Filename Value Changed")

    def _on_header_row_toggled(self, checked: bool) -> None:
        self._apply_setting(
            "first_row_contains_field_names", checked, "Header Row Toggled"
        )

    def _on_encoding_changed(self, _index: int) -> None:
        value = self.encodingCombo.currentData()
        if value:
            self._apply_setting("encoding", value, "Encoding Changed")

    def _on_sheet_mode_changed(self, _index: int) -> None:
        value = self.sheetModeCombo.currentData()
        if value:
            self._apply_setting("sheet_mode", value, "Sheet Mode Changed", rebuild=True)

    def _on_sheet_changed(self, sheet_name: str) -> None:
        if sheet_name and sheet_name != self.selected_sheet:
            self._apply_setting("selected_sheet", sheet_name, "Sheet Changed")

    def _on_start_row_changed(self, value: int) -> None:
        self._apply_setting(
            "start_row", value, "Start Row Changed", merge_key="fi-start"
        )

    def _on_sheets_checked(self, checked: list) -> None:
        self._apply_setting(
            "selected_sheets", list(checked), "Sheets Chosen", rebuild=True
        )

    def _on_sheet_column_toggled(self, checked: bool) -> None:
        self._apply_setting("add_sheet_name_column", checked, "Sheet Column Toggled")

    def _on_nested_changed(self, _index: int) -> None:
        value = self.nestedCombo.currentData()
        if value:
            self._apply_setting("json_nested", value, "Nested Values Changed")

    def _on_read_as_text_toggled(self, checked: bool) -> None:
        self._apply_setting("read_as_text", checked, "Read As Text Toggled")

    def _on_limit_changed(self, value: int) -> None:
        self._apply_setting(
            "record_limit", value, "Row Limit Changed", merge_key="fi-limit"
        )

    def _on_db_mode_changed(self, _index: int) -> None:
        value = self.dbModeCombo.currentData()
        if value:
            self._apply_setting(
                "db_mode", value, "Database Read Mode Changed", rebuild=True
            )

    def _on_db_table_changed(self, table: str) -> None:
        if table and table != self.db_table:
            self._apply_setting("db_table", table, "Database Table Changed")

    # -- source helpers ----------------------------------------------------
    def _use_legacy_path(self) -> bool:
        """Whether this configuration is exactly the pre-existing behaviour."""
        if effective_mode(self.filePath) != "single":
            return False
        if self.file_type not in ("csv", "txt", "excel"):
            return False
        if self.encoding != "utf8" or self.read_as_text:
            return False
        if (
            self.file_name_column_name != _FILENAME_COLUMN
            or self.file_name_value != "name"
        ):
            return False
        if (
            list(self.include_patterns)
            or list(self.exclude_patterns) != list(DEFAULT_EXCLUDE)
            or self.recursive
            or self.file_order != "name"
            or self.schema_mismatch != "union"
            or self.on_file_error != "stop"
            or self.max_files != 10000
        ):
            return False
        return (
            self.sheet_mode == "one"
            and not list(self.selected_sheets)
            and not self.add_sheet_name_column
        )

    def source_spec(self) -> dict:
        spec = {key: getattr(self, key, None) for key in SOURCE_KEYS}
        spec["filePath"] = self.filePath
        for key in ("include_patterns", "exclude_patterns", "selected_sheets"):
            spec[key] = list(spec.get(key) or [])
        return spec

    @property
    def source_state(self) -> dict:
        return {
            "filePath": self.filePath,
            "file_type": self.file_type,
            "output_filename_as_field": self.output_filename_as_field,
            "selected_sheet": self.selected_sheet,
            "available_sheets": list(self.available_sheets),
        }

    @source_state.setter
    def source_state(self, value: dict) -> None:
        for key in (
            "filePath",
            "file_type",
            "output_filename_as_field",
            "selected_sheet",
            "available_sheets",
        ):
            if key in value:
                setattr(self, key, copy.deepcopy(value[key]))

    def resolved_input_files(self, *, hash: bool = False):
        state = dict(self.get_serialized_state())
        state["filePath"] = self.filePath
        return resolve_input_files(
            state, base_dir=_workflow_dir(self.node.scene), hash=hash
        )

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        """Configuration summary for the pane tooltip."""
        chips: list[tuple[str, str]] = []
        if self.filePath:
            chips.append((self.file_type, "accent"))
        report = self.last_report
        if report is not None:
            if report.file_count > 1:
                chips.append((f"{report.file_count} files", "muted"))
            differing = len(report.differing_files())
            if differing:
                chips.append((f"{differing} differ", "warning"))
            if report.skipped_count:
                chips.append((f"{report.skipped_count} skipped", "danger"))
        if self.file_type == "excel" and self.sheet_mode != "one":
            chips.append(("all sheets", "muted"))
        if self.file_type in ("sqlite", "duckdb"):
            chips.append(
                (
                    f"table {self.db_table}" if self.db_mode == "table" else "query",
                    "muted",
                )
            )
        label = ""
        if self.filePath:
            label = os.path.basename(self.filePath.rstrip("\\/")) or self.filePath
        return chips, label

    def _refresh_file_input_counts(self) -> None:
        self.refresh_dock_context()

    # -- visibility and projections ---------------------------------------
    def _apply_visibility(self) -> None:
        if not hasattr(self, "source_section"):
            return
        has_path = bool(self.filePath)
        mode = effective_mode(self.filePath) if has_path else "empty"
        is_csv = self.file_type in ("csv", "txt")
        is_excel = self.file_type == "excel"
        is_json = self.file_type in ("json", "ndjson")
        is_db = self.file_type in ("sqlite", "duckdb")

        self.type_row.setVisible(has_path)
        self.files_section.setVisible(mode in ("folder", "pattern"))
        self.include_row.setVisible(mode == "folder")
        self.recursiveCheck.setVisible(mode == "folder")
        self.settings_section.setVisible(has_path)
        self.db_section.setVisible(has_path and is_db)

        show_filenames = self.output_filename_as_field
        self.filename_column_row.setVisible(has_path and show_filenames)
        self.filename_value_row.setVisible(has_path and show_filenames)

        self.delimiter_row.setVisible(has_path and is_csv)
        self.firstRowFieldNamesCheckBox.setVisible(has_path and is_csv)
        self.encoding_row.setVisible(has_path and is_csv)

        self.sheet_mode_row.setVisible(has_path and is_excel)
        self.selected_sheet_row.setVisible(
            has_path and is_excel and self.sheet_mode == "one"
        )
        self.start_row_row.setVisible(has_path and is_excel)
        self.sheets_row.setVisible(
            has_path and is_excel and self.sheet_mode == "chosen"
        )
        self.sheetColumnCheck.setVisible(has_path and is_excel)
        self.sheet_column_row.setVisible(
            has_path and is_excel and self.add_sheet_name_column
        )

        self.nested_row.setVisible(has_path and is_json)
        self.as_text_widget.setVisible(has_path and not is_csv)
        self.limit_row.setVisible(has_path)

        self.db_table_row.setVisible(has_path and is_db and self.db_mode == "table")
        self.db_query_row.setVisible(has_path and is_db and self.db_mode == "query")

    def _hide_all_options(self) -> None:
        self._apply_visibility()

    def _update_ui_visibility(self, _file_type: str) -> None:
        self._apply_visibility()

    def _refresh_files_table(self) -> None:
        if not hasattr(self, "filesTable"):
            return
        model = self._files_model
        model.removeRows(0, model.rowCount())
        report = self.last_report
        if report is None:
            return
        for item in report.files:
            name = item.relative_path or os.path.basename(item.path)
            if item.sheet:
                name = f"{name} [{item.sheet}]"
            status = "OK"
            if item.status != "ok":
                kind = (item.error or {}).get("kind", "error")
                status = f"skipped: {kind}"
            elif item.extra_columns:
                status = f"+{len(item.extra_columns)} column" + (
                    "s" if len(item.extra_columns) != 1 else ""
                )
            elif item.missing_columns:
                status = f"missing {len(item.missing_columns)}"
            elif item.dtype_conflicts:
                status = "types differ"
            detail = []
            if item.missing_columns:
                detail.append("missing: " + ", ".join(item.missing_columns))
            if item.extra_columns:
                detail.append("extra: " + ", ".join(item.extra_columns))
            if item.dtype_conflicts:
                detail.append("types: " + ", ".join(item.dtype_conflicts))
            if item.error:
                detail.append(item.error.get("message", ""))
            row = [
                QStandardItem(name),
                QStandardItem(status),
                QStandardItem(", ".join(item.columns)),
            ]
            for cell in row:
                cell.setEditable(False)
                cell.setToolTip("\n".join(part for part in detail if part) or status)
            model.appendRow(row)

    def _refresh_sheets(self) -> None:
        if not self.filePath or self.file_type != "excel":
            return
        try:
            listing = list_source_files(
                self.filePath,
                "excel",
                include=self.include_patterns,
                exclude=self.exclude_patterns,
                recursive=self.recursive,
                order=self.file_order,
                max_files=self.max_files,
            )
            first = listing.files[0]
            reader = fastexcel.read_excel(io_path(first.path))
            sheets = list(reader.sheet_names)
        except Exception as exc:  # noqa: BLE001 - a bad workbook is reported later
            logger.warning(f"Could not read Excel sheets: {exc}")
            self.node._set_node_tooltip(str(exc))
            return
        self.available_sheets = sheets
        if not self.selected_sheet or self.selected_sheet not in sheets:
            self.selected_sheet = sheets[0] if sheets else ""
        self._sync_sheet_widgets()
        self.refresh_dock_context()

    def _sync_sheet_widgets(self) -> None:
        if not hasattr(self, "selectedSheetCombo"):
            return
        self.selectedSheetCombo.blockSignals(True)
        self.selectedSheetCombo.clear()
        self.selectedSheetCombo.addItems(self.available_sheets)
        if self.selected_sheet in self.available_sheets:
            self.selectedSheetCombo.setCurrentText(self.selected_sheet)
        self.selectedSheetCombo.blockSignals(False)
        self.sheetsChecklist.setColumns(self.available_sheets, self.selected_sheets)

    def _refresh_db_tables(self) -> None:
        if not hasattr(self, "dbTableCombo"):
            return
        tables: list[str] = []
        if self.filePath and self.file_type in ("sqlite", "duckdb"):
            try:
                tables = list_db_tables(self.filePath, self.file_type)
            except InputReadError as error:
                self.node._set_node_tooltip(str(error))
            except Exception as exc:  # noqa: BLE001
                self.node._set_node_tooltip(str(exc))
        self.dbTableCombo.blockSignals(True)
        self.dbTableCombo.clear()
        self.dbTableCombo.addItems(tables)
        if tables:
            # A database source must have a table before Run can build SQL.
            # Default to the first one, exactly like the first Excel sheet.
            if not self.db_table or self.db_table not in tables:
                self.db_table = tables[0]
            self.dbTableCombo.setCurrentText(self.db_table)
        self.dbTableCombo.blockSignals(False)

    def _set_text(self, widget, value: str) -> None:
        if widget.text() == value:
            return
        widget.blockSignals(True)
        widget.setText(value)
        widget.blockSignals(False)

    def _set_plain_text(self, widget, value: str) -> None:
        if widget.toPlainText() == value:
            return
        widget.blockSignals(True)
        widget.setPlainText(value)
        widget.blockSignals(False)

    def _set_checked(self, widget, value: bool) -> None:
        if widget.isChecked() == bool(value):
            return
        widget.blockSignals(True)
        widget.setChecked(bool(value))
        widget.blockSignals(False)

    def _set_spin(self, widget, value: int) -> None:
        if widget.value() == int(value):
            return
        widget.blockSignals(True)
        widget.setValue(int(value))
        widget.blockSignals(False)

    def _set_combo(self, widget, data) -> None:
        index = widget.findData(data)
        if index < 0 or widget.currentIndex() == index:
            return
        widget.blockSignals(True)
        widget.setCurrentIndex(index)
        widget.blockSignals(False)

    def _sync_widgets_from_model(self) -> None:
        if not hasattr(self, "filePathEdit"):
            return
        self._set_text(self.filePathEdit, self.filePath)
        self._set_combo(self.typeCombo, self.file_type)
        include = "; ".join(self.include_patterns)
        exclude = "; ".join(self.exclude_patterns)
        self._set_text(self.includeEdit, include)
        self._set_text(self.excludeEdit, exclude)
        self._set_checked(self.recursiveCheck, self.recursive)
        self._set_combo(self.orderCombo, self.file_order)
        self._set_combo(self.schemaCombo, self.schema_mismatch)
        self._set_combo(self.badFileCombo, self.on_file_error)
        self._set_checked(self.outputFilenameCheckBox, self.output_filename_as_field)
        self._set_text(self.fileNameColumnEdit, self.file_name_column_name)
        self._set_combo(self.fileNameValueCombo, self.file_name_value)
        self._set_text(self.delimiterEdit, self.delimiter)
        self._set_checked(
            self.firstRowFieldNamesCheckBox,
            self.first_row_contains_field_names,
        )
        self._set_combo(self.encodingCombo, self.encoding)
        self._set_combo(self.sheetModeCombo, self.sheet_mode)
        self._sync_sheet_widgets()
        self._set_spin(self.startRowSpinBox, self.start_row)
        self._set_checked(self.sheetColumnCheck, self.add_sheet_name_column)
        self._set_text(self.sheetColumnEdit, self.sheet_name_column_name)
        self._set_combo(self.nestedCombo, self.json_nested)
        self._set_checked(self.asTextCheck, self.read_as_text)
        self._set_spin(self.limitSpin, self.record_limit)
        self._set_combo(self.dbModeCombo, self.db_mode)
        if self.dbTableCombo.findText(self.db_table) >= 0:
            self.dbTableCombo.blockSignals(True)
            self.dbTableCombo.setCurrentText(self.db_table)
            self.dbTableCombo.blockSignals(False)
        self._set_plain_text(self.dbQueryEdit, self.db_query)
        self._apply_visibility()
        self._refresh_files_table()

    def _rebuild_widgets(self) -> None:
        if not hasattr(self, "typeCombo"):
            return
        if self.file_type == "excel" and self.filePath:
            self._refresh_sheets()
        if self.file_type in ("sqlite", "duckdb") and self.filePath:
            self._refresh_db_tables()
        self._sync_widgets_from_model()

    def check_file_path(self) -> bool:
        if not self.filePath:
            return False
        if self._use_legacy_path():
            # Legacy single-file CSV/TXT/Excel keeps its exact behaviour.
            if not os.path.exists(self.filePath):
                self._log_missing_file(self.filePath)
                self.data = pl.DataFrame()
                self.node.grNode.setToolTip(f"File {self.filePath!r} does not exist")
                self.node.markInvalid(True)
                return False
            self._reset_missing_file_attempts(self.filePath)
            self.node.grNode.setToolTip("")
            self.node.markInvalid(False)
            self.loadFile(self.filePath)
            return True
        return self._load_via_builder()

    def _ensure_db_table(self) -> None:
        """Pick the first readable table when table mode has no choice yet."""
        if (
            self.file_type in ("sqlite", "duckdb")
            and self.db_mode == "table"
            and self.filePath
            and not self.db_table
        ):
            try:
                tables = list_db_tables(self.filePath, self.file_type)
            except InputReadError:
                return
            if tables:
                self.db_table = tables[0]

    def _load_via_builder(self) -> bool:
        self._ensure_db_table()
        try:
            result = build_source(self.source_spec())
        except InputReadError as error:
            self.last_error = error
            self.last_report = None
            self.data = pl.DataFrame()
            self._set_input_error_tooltip(error)
            self.node.markInvalid(True)
            if error.kind in ("file_not_found", "no_match"):
                self._log_missing_file(error.path or self.filePath)
            else:
                logger.warning(str(error))
            self._refresh_files_table()
            return False
        except Exception as exc:  # noqa: BLE001 - build_source should not leak
            error = InputReadError(
                "parse",
                f"Cannot read '{self.filePath}': {exc}",
                path=self.filePath,
                technical=str(exc),
                cause_type=type(exc).__name__,
            )
            self.last_error = error
            self.last_report = None
            self.data = pl.DataFrame()
            self._set_input_error_tooltip(error)
            self.node.markInvalid(True)
            self._refresh_files_table()
            return False
        self.last_error = None
        self.last_report = result.report
        self.data = result.frame
        self._record_schema_from(result.frame)
        self._reset_missing_file_attempts(self.filePath)
        self._set_input_report_tooltip(result.report)
        self.node.markInvalid(False)
        self._refresh_files_table()
        return True

    def _record_schema_from(self, frame) -> None:
        self.schema_snapshot = self._build_schema_snapshot(frame)

    def _set_input_error_tooltip(self, error: InputReadError) -> None:
        """Plan 03 replaces this builder with plain-language text."""
        self.node._set_node_tooltip(str(error))

    def _set_input_report_tooltip(self, report) -> None:
        """Plan 03 replaces this builder with plain-language text."""
        if report.skipped_count or report.differing_files():
            self.node._set_node_tooltip(report.summary())
        else:
            self.node._set_node_tooltip("")

    def _build_schema_snapshot(
        self, dataframe: pl.DataFrame | pl.LazyFrame | None = None
    ) -> list[dict[str, str]]:
        source_df = dataframe
        if source_df is None and self.data is not None:
            source_df = self.data

        if source_df is None:
            return []

        return [
            {"name": column_name, "dtype": str(dtype)}
            for column_name, dtype in frame_schema(source_df).items()
        ]

    def _build_file_metadata(self) -> dict[str, Any]:
        if not self.filePath:
            return {}
        if self._use_legacy_path():
            if not os.path.exists(self.filePath):
                return {}
            file_stat = os.stat(self.filePath)
            return {
                "size_bytes": file_stat.st_size,
                "modified_time": int(file_stat.st_mtime),
            }
        resolved = [item for item in self.resolved_input_files() if item.exists]
        if not resolved:
            return {}
        epochs: list[int] = []
        for item in resolved:
            if item.modified_time:
                try:
                    epochs.append(
                        int(datetime.fromisoformat(item.modified_time).timestamp())
                    )
                except ValueError:
                    continue
        first = resolved[0]
        return {
            "size_bytes": first.size_bytes or 0,
            "modified_time": epochs[0] if epochs else 0,
            "file_count": len(resolved),
            "total_size_bytes": sum(item.size_bytes or 0 for item in resolved),
            "newest_modified_time": max(epochs) if epochs else 0,
        }

    def _refresh_saved_input_metadata(
        self, preview_df: pl.DataFrame | None = None
    ) -> None:
        if self.filePath and os.path.exists(self.filePath):
            schema_source = preview_df
            if schema_source is None:
                schema_source = self._read_file_based_on_type(self.filePath)

            snapshot = self._build_schema_snapshot(schema_source)
            if snapshot:
                self.schema_snapshot = snapshot
            self.file_metadata = self._build_file_metadata()

    @staticmethod
    def _diff_schema(
        saved_snapshot: list, current_columns: dict[str, str]
    ) -> list[str]:
        issues: list[str] = []
        if not saved_snapshot:
            # Version-1 workflows never stored a snapshot. The old serializer
            # happened to fill it while saving the initial history stamp; a
            # snapshot we do not have is not evidence of drift.
            return issues
        saved_columns = {
            item.get("name", ""): item.get("dtype", "")
            for item in saved_snapshot
            if item.get("name")
        }
        current_columns = {
            name: dtype for name, dtype in current_columns.items() if name
        }
        missing_columns = [
            column for column in saved_columns if column not in current_columns
        ]
        added_columns = [
            column for column in current_columns if column not in saved_columns
        ]
        dtype_changes = [
            f"{column} ({saved_columns[column]} -> {current_columns[column]})"
            for column in sorted(saved_columns.keys() & current_columns.keys())
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
        return issues

    def validate_loaded_state(self) -> list[str]:
        issues: list[str] = []
        if not self.filePath:
            return issues

        if self._use_legacy_path():
            if not os.path.exists(self.filePath):
                issues.append(f"Missing input file: {self.filePath}")
            else:
                preview_df = self._read_file_based_on_type(self.filePath)
                current = {
                    name: str(dtype) for name, dtype in frame_schema(preview_df).items()
                }
                issues.extend(self._diff_schema(self.schema_snapshot, current))
                if self.file_type == "excel" and self.selected_sheet:
                    try:
                        reader = fastexcel.read_excel(self.filePath)
                        current_sheets = list(reader.sheet_names)
                        if self.selected_sheet not in current_sheets:
                            issues.append(
                                f"Saved sheet '{self.selected_sheet}' is no longer available"
                            )
                    except Exception as exc:  # noqa: BLE001
                        issues.append(f"Could not validate Excel sheets: {exc}")
        else:
            self._ensure_db_table()
            try:
                result = build_source(self.source_spec())
            except InputReadError as error:
                issues.append(str(error))
            except Exception as exc:  # noqa: BLE001 - validation never raises
                issues.append(f"Could not read the input: {exc}")
            else:
                report = result.report
                if report.skipped_count or report.differing_files():
                    issues.append(report.summary())
                current = {
                    name: str(dtype)
                    for name, dtype in frame_schema(result.frame).items()
                }
                issues.extend(self._diff_schema(self.schema_snapshot, current))

        if issues:
            tooltip = "Workflow load validation failed:\n" + "\n".join(issues)
            self.node.grNode.setToolTip(tooltip)
            self.node.markInvalid(True)
        return issues

    _FILE_FILTERS = (
        "All Supported (*.csv *.tsv *.txt *.xlsx *.xlsm *.xls *.parquet *.pq "
        "*.json *.ndjson *.jsonl *.db *.sqlite *.sqlite3 *.duckdb *.ddb);;"
        "CSV (*.csv *.tsv);;"
        "Text (*.txt);;"
        "Excel (*.xlsx *.xlsm *.xls);;"
        "Parquet (*.parquet *.pq);;"
        "JSON (*.json);;"
        "JSON Lines (*.ndjson *.jsonl);;"
        "Database (*.db *.sqlite *.sqlite3 *.duckdb *.ddb);;"
        "All Files (*)"
    )

    def openFileDialog(self) -> None:
        fileName, _ = QFileDialog.getOpenFileName(
            self.parent(), "Open Data File", "", self._FILE_FILTERS
        )
        if fileName:
            self._choose_file(fileName)

    def openFolderDialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self.parent(), "Choose a folder")
        if folder:
            self._choose_folder(folder)

    def _choose_file(self, fileName: str) -> None:
        detected = detect_file_type(fileName)
        old_state = self.source_state
        new_state = dict(old_state)
        new_state["filePath"] = fileName
        new_state["file_type"] = detected
        self._type_user_set = False
        self._apply_setting("source_state", new_state, "Source Chosen", rebuild=True)
        if detected == "excel":
            self._show_sheet_selection_dialog(fileName)
        self._apply_visibility()

    def _choose_folder(self, folder: str) -> None:
        counts: Counter = Counter()
        try:
            for entry in os.scandir(io_path(folder)):
                if entry.is_file():
                    counts[detect_file_type(entry.name)] += 1
        except OSError:
            pass
        chosen = counts.most_common(1)[0][0] if counts else "csv"
        old_state = self.source_state
        new_state = dict(old_state)
        new_state["filePath"] = folder
        new_state["file_type"] = chosen
        new_state["output_filename_as_field"] = True
        self._type_user_set = False
        self._apply_setting("source_state", new_state, "Source Chosen", rebuild=True)
        if chosen == "excel":
            self._show_sheet_selection_dialog(folder)
        self._apply_visibility()

    def _auto_detect_file_type(self, fileName: str) -> str:
        return detect_file_type(fileName)

    def _show_sheet_selection_dialog(self, _fileName: str = "") -> None:
        """Populate the sheet controls without discarding the chosen source."""
        self._refresh_sheets()
        self._apply_visibility()

    def _read_excel(self, fileName: str, n_rows: int | None = None) -> pl.DataFrame:
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

            except Exception as fastexcel_error:  # noqa: BLE001
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
                        "Fallback: Successfully read Excel preview with polars"
                    )
                    return df
                except Exception as fallback_error:  # noqa: BLE001
                    logger.error(
                        f"All Excel preview reading methods failed: {fallback_error}"
                    )
                    return pl.DataFrame()

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error reading Excel preview {fileName}: {e}")
            return pl.DataFrame()

    def _scan_csv_full(self, fileName: str) -> pl.LazyFrame:
        """Full-file lazy scan mirroring get_code (no preview cap).

        Live data stays lazy; only names/types resolve until a downstream
        node collects. record_limit applies as a lazy head, like codegen.
        """
        scan_options: dict[str, Any] = {"infer_schema": False}
        if self.delimiter != ",":
            scan_options["separator"] = self.delimiter
        if not self.first_row_contains_field_names:
            scan_options["has_header"] = False
        frame = pl.scan_csv(fileName, **scan_options)
        if self.record_limit > 0:
            frame = frame.head(self.record_limit)
        if self.output_filename_as_field:
            frame = frame.with_columns(
                pl.lit(os.path.basename(fileName)).alias("FileName")
            )
        return frame

    def _read_file_based_on_type(self, fileName: str) -> pl.DataFrame | pl.LazyFrame:
        """Read the full file, mirroring get_code (no preview cap)."""
        try:
            if self.file_type == "excel":
                # Full read like codegen (n_rows = record_limit only).
                df = self._read_excel(
                    fileName,
                    self.record_limit if self.record_limit > 0 else None,
                )
                frame: pl.DataFrame | pl.LazyFrame = df.lazy()
            elif self.file_type in ["csv", "txt"]:
                frame = self._scan_csv_full(fileName)
            else:
                # Default to CSV with memory optimization
                frame = pl.scan_csv(fileName, infer_schema=False)

            if self.output_filename_as_field and self.file_type not in ["csv", "txt"]:
                filename_only = os.path.basename(fileName)
                if isinstance(frame, pl.LazyFrame):
                    frame = frame.with_columns(pl.lit(filename_only).alias("FileName"))
                else:
                    frame = frame.with_columns(pl.lit(filename_only).alias("FileName"))

            return frame

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error reading file {fileName}: {e}")
            # Return empty DataFrame on error
            return pl.DataFrame()

    def _preview_frame(self) -> pl.DataFrame:
        """Small eager sample for the table viewer (live data stays lazy)."""
        data = getattr(self, "data", None)
        if data is None:
            return pl.DataFrame()
        if isinstance(data, pl.LazyFrame):
            return data.head(self.preview_rows).collect()
        return data.head(self.preview_rows)

    def loadFile(self, fileName: str) -> None:
        """Load file: full data for processing, preview sample for the viewer"""
        if self.filePath and fileName == self.filePath and not self._use_legacy_path():
            self._load_via_builder()
            return
        # Clear any existing data to free memory first
        if hasattr(self, "data"):
            del self.data

        try:
            # Full read (lazy for csv) so live matches Run output exactly
            full_df = self._read_file_based_on_type(fileName)
            preview_df = (
                full_df.head(self.preview_rows).collect()
                if isinstance(full_df, pl.LazyFrame)
                else full_df.head(self.preview_rows)
            )

            if preview_df.height == 0:
                # Create empty DataFrame for display
                self.data = pl.DataFrame()
                if getattr(self, "table_viewer", None):
                    self.table_viewer.set_dataframe(self.data)
                return

            # Store the full frame as data for later use
            self.data = full_df
            self._refresh_saved_input_metadata(full_df)

            # Set the preview sample in the Polars table viewer
            if getattr(self, "table_viewer", None):
                self.table_viewer.set_dataframe(preview_df)

            logger.info(
                f"Loaded preview: {preview_df.height} rows, {len(frame_schema(full_df))} columns"
            )

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error loading file {fileName}: {e}")
            # Set data to empty DataFrame on error
            self.data = pl.DataFrame()

            # Create error DataFrame for display
            error_df = pl.DataFrame({"Error": [f"Error loading file: {e!s}"]})

            # Only update table viewer if it exists
            if getattr(self, "table_viewer", None):
                self.table_viewer.set_dataframe(error_df)

    def _builder_code(self) -> str:
        spec = self.source_spec()
        return (
            "import polars as pl\n"
            "from trigger_designer.core.input_source import build_source\n"
            f"# File Input ({spec['file_type']}, builder path)\n"
            f"_spec_{self.id} = {spec!r}\n"
            f"{self.variable_name} = pl.DataFrame()\n"
            f"{self.variable_name} = build_source(_spec_{self.id}).frame\n"
        )

    def get_code(self) -> str:
        if not self.filePath:
            # Fallback: always define the output so downstream code never
            # NameErrors.
            return f"import polars as pl\n{self.variable_name} = pl.DataFrame()\n"

        if not self._use_legacy_path():
            return self._builder_code()

        code_lines = []
        code_lines.append("import polars as pl")
        code_lines.append("import os")
        code_lines.append("")
        code_lines.append("# Always use LazyFrame for memory efficiency")

        if self.file_type == "excel":
            # Excel file code generation using fastexcel with LazyFrame conversion
            code_lines.append("import fastexcel")
            code_lines.append(
                f"reader_{self.id} = fastexcel.read_excel({self.filePath!r})"
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
            code_lines.append("# Convert to polars LazyFrame for memory efficiency")
            code_lines.append("try:")
            code_lines.append(
                f"    eager_df_{self.id} = excel_df_{self.id}.to_polars()"
            )
            code_lines.append("except AttributeError:")
            code_lines.append(
                f"    eager_df_{self.id} = pl.from_arrow(excel_df_{self.id}.to_arrow())"
            )
            code_lines.append("# Convert to LazyFrame immediately")
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
            lazy_call = f"pl.scan_csv({self.filePath!r}"
            if read_params:
                lazy_call += f", {', '.join(read_params)}"
            lazy_call += ")"

            code_lines.append(f"{self.variable_name} = {lazy_call}")

            # Apply record limit using lazy operations if specified
            if self.record_limit > 0:
                code_lines.append("# Apply record limit using lazy operations")
                code_lines.append(
                    f"{self.variable_name} = {self.variable_name}.head({self.record_limit})"
                )
        else:
            # Default to CSV with LazyFrame
            code_lines.append("# Default to CSV with LazyFrame")
            code_lines.append(
                f"{self.variable_name} = pl.scan_csv({self.filePath!r}, infer_schema=False)"
            )

        # Add filename as field if requested - using lazy operations
        if self.output_filename_as_field:
            filename_var = f"filename_{self.id}"
            code_lines.append("# Add filename field using lazy operations")
            code_lines.append(f"{filename_var} = os.path.basename({self.filePath!r})")
            code_lines.append(
                f"{self.variable_name} = {self.variable_name}.with_columns(pl.lit({filename_var}).alias('FileName'))"
            )

        # Add a comment about LazyFrame usage
        code_lines.append("")
        code_lines.append(
            f"# {self.variable_name} is now a LazyFrame for memory-efficient processing"
        )
        code_lines.append("# Use .collect() only when you need to materialize the data")

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> OrderedDict[Any, Any]:
        state = self.serialize_content_state(super().serialize())
        if self.filePath:
            absolute, relative = to_stored_paths(
                self.filePath, _workflow_dir(self.node.scene)
            )
        else:
            absolute, relative = "", ""
        state["filePath"] = absolute or self.filePath
        state["filePathRel"] = relative
        state["input_schema_version"] = 2
        state["file_metadata"] = self._build_file_metadata()
        return state

    def deserialize(
        self,
        data: dict,
        hashmap: dict = {},  # noqa: B006 - legacy signature kept for callers
        restore_id: bool | None = True,
    ) -> bool:
        res = super().deserialize(data, hashmap)

        try:
            self.deserialize_content_state(data)
            self.filePath = resolve_stored_path(
                self.filePath,
                self.filePathRel,
                _workflow_dir(self.node.scene),
            )
            migrate_file_input_state(self)
            self._sync_widgets_from_model()
            return res
        except Exception as e:  # noqa: BLE001
            dumpException(e)
        return res


@register_node(IONodes.FILE_INPUT, NodeTypes.IO)
class TriggerNode_FileInput(TriggerNode):
    icon = "node_file_input"
    node_code = IONodes.FILE_INPUT
    node_type = NodeTypes.IO
    node_title = "File Input"
    content_label_objname = "trigger_node_file_input"
    style = {}  # noqa: RUF012 - node class marker read by the canvas

    def __init__(self, scene: "Scene") -> None:
        super().__init__(scene, inputs=[], outputs=[3])
        self.eval()
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        self.content: FileInputContent = FileInputContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values: list[Any]) -> list[dict[str, Any]] | None:
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
