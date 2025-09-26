"""
Polars DataFrame Table Viewer - Memory Efficient Implementation

This module provides a custom table viewer for Polars DataFrames with optimized memory usage
and high performance for large datasets. Features include:

- Lazy loading with pagination
- Virtual scrolling for large datasets
- Memory-efficient data caching
- Data type-specific formatting
- Search and filtering capabilities
- Performance monitoring
- Export functionality
"""

import polars as pl
import psutil
from typing import Any, Dict, List, Optional, Union, Tuple
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QLineEdit,
    QPushButton,
    QLabel,
    QProgressBar,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QGroupBox,
    QFrame,
    QSplitter,
    QTextEdit,
)
from qtpy.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    QTimer,
    Signal,
    QThread,
    QObject,
)
from qtpy.QtGui import QFont, QColor, QPalette
from loguru import logger
import traceback
import time
from datetime import datetime, date


class PolarsTableModel(QAbstractTableModel):
    """
    Memory-efficient model for displaying Polars DataFrames using lazy loading
    and intelligent caching strategies.
    """

    # Signals for async operations
    dataLoadProgress = Signal(int)  # Progress percentage
    dataLoadComplete = Signal()
    errorOccurred = Signal(str)

    def __init__(
        self,
        dataframe: Optional[pl.DataFrame] = None,
        chunk_size: int = 1000,
        cache_size: int = 5000,
    ):
        """
        Initialize the model with a Polars DataFrame.

        Args:
            dataframe: The Polars DataFrame to display
            chunk_size: Number of rows to load at once for lazy loading
            cache_size: Maximum number of rows to keep in memory cache
        """
        super().__init__()

        self._dataframe = dataframe or pl.DataFrame()
        self.chunk_size = chunk_size
        self.cache_size = cache_size

        # Data cache - stores chunks of data as (start_row, data_chunk) pairs
        self._data_cache: Dict[int, Tuple[pl.DataFrame, int]] = {}
        self._cache_access_times: Dict[int, float] = {}

        # Column information for faster access
        self._column_names: List[str] = []
        self._column_types: Dict[str, pl.DataType] = {}
        self._update_column_info()

        # Statistics
        self._total_rows = len(self._dataframe) if not self._dataframe.is_empty() else 0
        self._total_columns = (
            len(self._dataframe.columns) if not self._dataframe.is_empty() else 0
        )

        # Performance monitoring
        self._memory_usage = 0
        self._last_access_time = time.time()

    def _update_column_info(self):
        """Update cached column information."""
        if not self._dataframe.is_empty():
            self._column_names = self._dataframe.columns
            self._column_types = dict(
                zip(self._dataframe.columns, self._dataframe.dtypes)
            )
            self._total_rows = len(self._dataframe)
            self._total_columns = len(self._dataframe.columns)
        else:
            self._column_names = []
            self._column_types = {}
            self._total_rows = 0
            self._total_columns = 0

    def set_dataframe(self, dataframe: pl.DataFrame):
        """
        Set a new dataframe and refresh the model.

        Args:
            dataframe: New Polars DataFrame to display
        """
        self.beginResetModel()
        self._dataframe = dataframe
        self._data_cache.clear()
        self._cache_access_times.clear()
        self._update_column_info()
        self.endResetModel()
        logger.info(
            f"DataFrame updated: {self._total_rows} rows, {self._total_columns} columns"
        )

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the total number of rows."""
        return self._total_rows

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the total number of columns."""
        return self._total_columns

    def _get_chunk_key(self, row: int) -> int:
        """Get the cache key for a given row."""
        return (row // self.chunk_size) * self.chunk_size

    def _load_chunk(self, start_row: int) -> pl.DataFrame:
        """
        Load a chunk of data from the DataFrame.

        Args:
            start_row: Starting row index for the chunk

        Returns:
            Polars DataFrame containing the chunk data
        """
        try:
            end_row = min(start_row + self.chunk_size, self._total_rows)

            # Use lazy evaluation for better performance
            chunk = self._dataframe.slice(start_row, end_row - start_row)

            return chunk
        except Exception as e:
            logger.error(f"Error loading chunk starting at row {start_row}: {e}")
            return pl.DataFrame()

    def _cache_cleanup(self):
        """Remove old entries from cache if it gets too large."""
        if len(self._data_cache) <= self.cache_size // self.chunk_size:
            return

        # Remove oldest accessed entries
        current_time = time.time()
        entries_to_remove = []

        # Sort by access time
        sorted_entries = sorted(self._cache_access_times.items(), key=lambda x: x[1])

        # Remove oldest half of entries
        max_entries = self.cache_size // self.chunk_size
        entries_to_keep = max_entries // 2

        for key, _ in sorted_entries[:-entries_to_keep]:
            entries_to_remove.append(key)

        for key in entries_to_remove:
            if key in self._data_cache:
                del self._data_cache[key]
            if key in self._cache_access_times:
                del self._cache_access_times[key]

    def _get_cached_data(self, row: int) -> Optional[Any]:
        """
        Get data for a specific row, using cache when possible.

        Args:
            row: Row index

        Returns:
            Data value or None if not available
        """
        if row >= self._total_rows:
            return None

        chunk_key = self._get_chunk_key(row)
        current_time = time.time()

        # Check if chunk is cached
        if chunk_key not in self._data_cache:
            # Load new chunk
            chunk_data = self._load_chunk(chunk_key)
            if not chunk_data.is_empty():
                self._data_cache[chunk_key] = (chunk_data, len(chunk_data))

                # Cleanup cache if necessary
                self._cache_cleanup()

        # Update access time
        self._cache_access_times[chunk_key] = current_time

        # Get data from cache
        if chunk_key in self._data_cache:
            chunk_data, chunk_length = self._data_cache[chunk_key]
            row_in_chunk = row - chunk_key

            if 0 <= row_in_chunk < chunk_length:
                return chunk_data.row(row_in_chunk)

        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """
        Return data for the given index and role.

        Args:
            index: Model index
            role: Data role

        Returns:
            Data value appropriate for the role
        """
        if not index.isValid():
            return None

        row, col = index.row(), index.column()

        if role == Qt.DisplayRole:
            row_data = self._get_cached_data(row)
            if row_data is None:
                return "..."  # Loading indicator

            try:
                value = row_data[col]
                return self._format_value(value, self._column_names[col])
            except (IndexError, KeyError):
                return None

        elif role == Qt.TextAlignmentRole:
            if col < len(self._column_names):
                col_name = self._column_names[col]
                col_type = self._column_types.get(col_name)

                # Right align numeric columns
                if col_type in [
                    pl.Int8,
                    pl.Int16,
                    pl.Int32,
                    pl.Int64,
                    pl.UInt8,
                    pl.UInt16,
                    pl.UInt32,
                    pl.UInt64,
                    pl.Float32,
                    pl.Float64,
                ]:
                    return Qt.AlignRight | Qt.AlignVCenter

            return Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.BackgroundRole:
            # Use theme colors for alternating row backgrounds
            if row % 2 == 0:
                return QColor("#14171b")  # Primary background
            return QColor("#191e21")  # Alternate background (slightly lighter)

        elif role == Qt.ToolTipRole:
            # Show data type and value info in tooltip
            if col < len(self._column_names):
                col_name = self._column_names[col]
                col_type = self._column_types.get(col_name, "Unknown")
                row_data = self._get_cached_data(row)
                if row_data is not None:
                    value = row_data[col]
                    return f"Column: {col_name}\nType: {col_type}\nValue: {value}"

        return None

    def _format_value(self, value: Any, column_name: str) -> str:
        """
        Format a value for display based on its type.

        Args:
            value: The value to format
            column_name: Name of the column

        Returns:
            Formatted string representation
        """
        try:
            if value is None:
                return "NULL"

            col_type = self._column_types.get(column_name)

            # Handle different data types
            if col_type in [pl.Float32, pl.Float64]:
                if isinstance(value, float):
                    if value.is_integer():
                        return f"{value:.0f}"
                    else:
                        return f"{value:.6f}".rstrip("0").rstrip(".")

            elif col_type in [pl.Date]:
                if isinstance(value, date):
                    return value.strftime("%Y-%m-%d")

            elif col_type in [pl.Datetime]:
                if isinstance(value, datetime):
                    return value.strftime("%Y-%m-%d %H:%M:%S")

            elif col_type == pl.Boolean:
                return "True" if value else "False"

            # Default string conversion
            str_value = str(value)

            # Truncate very long strings
            if len(str_value) > 100:
                return str_value[:97] + "..."

            return str_value

        except Exception as e:
            logger.warning(
                f"Error formatting value {value} for column {column_name}: {e}"
            )
            return str(value) if value is not None else "NULL"

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        """
        Return header data for the given section and role.

        Args:
            section: Section index
            orientation: Header orientation
            role: Data role

        Returns:
            Header data
        """
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if 0 <= section < len(self._column_names):
                    col_name = self._column_names[section]
                    col_type = self._column_types.get(col_name, "Unknown")
                    return f"{col_name}\n({col_type})"
                return f"Column {section}"
            else:
                return str(section + 1)  # Row numbers start from 1

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            font.setPointSize(12)  # Slightly larger font for headers
            return font

        elif role == Qt.ForegroundRole:
            return QColor("#ffffff")  # White text to match theme

    def get_memory_usage(self) -> Dict[str, Union[int, float]]:
        """
        Get current memory usage statistics.

        Returns:
            Dictionary with memory usage information
        """
        # Calculate cache memory usage (approximate)
        cache_memory = 0
        for chunk_data, chunk_length in self._data_cache.values():
            # Rough estimate: 8 bytes per cell on average
            cache_memory += chunk_length * len(self._column_names) * 8

        # System memory info
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "cache_size_mb": cache_memory / (1024 * 1024),
            "cached_chunks": len(self._data_cache),
            "total_process_memory_mb": memory_info.rss / (1024 * 1024),
            "chunk_size": self.chunk_size,
            "total_rows": self._total_rows,
            "total_columns": self._total_columns,
        }


class PolarsTableViewer(QWidget):
    """
    High-performance table viewer widget for Polars DataFrames with memory management.

    This widget provides a customizable interface for viewing Polars DataFrames with
    various optional components:

    Customization Options:
    - show_controls: Show/hide the entire control panel
    - show_info: Show/hide the information and statistics panel
    - show_search: Show/hide search and filter functionality
    - show_export: Show/hide export buttons (CSV/Excel)
    - show_performance_settings: Show/hide performance tuning controls

    Usage Examples:

    # Full-featured viewer (default)
    viewer = PolarsTableViewer(dataframe=df)

    # Data-only viewer (minimal interface)
    viewer = PolarsTableViewer(
        dataframe=df,
        show_controls=False,
        show_info=False
    )

    # Search-enabled viewer
    viewer = PolarsTableViewer(
        dataframe=df,
        show_controls=True,
        show_info=False,
        show_search=True,
        show_export=False,
        show_performance_settings=False
    )

    # Runtime visibility control
    viewer.set_controls_visibility(False)
    viewer.set_info_visibility(True)
    """

    # Signals
    memoryWarning = Signal(float)  # Emitted when memory usage is high (MB)
    filterChanged = Signal(str)  # Emitted when filter text changes

    def __init__(
        self,
        dataframe: Optional[pl.DataFrame] = None,
        parent: Optional[QWidget] = None,
        show_controls: bool = True,
        show_info: bool = True,
        show_search: bool = True,
        show_export: bool = True,
        show_performance_settings: bool = True,
    ):
        """
        Initialize the table viewer.

        Args:
            dataframe: Initial dataframe to display
            parent: Parent widget
            show_controls: Whether to show the control panel (default: True)
            show_info: Whether to show the info panel with statistics (default: True)
            show_search: Whether to show search/filter controls (default: True)
            show_export: Whether to show export buttons (default: True)
            show_performance_settings: Whether to show performance settings (default: True)
        """
        super().__init__(parent)

        self.dataframe = dataframe
        self.filtered_dataframe: Optional[pl.DataFrame] = None

        # UI visibility options
        self.show_controls = show_controls
        self.show_info = show_info
        self.show_search = show_search
        self.show_export = show_export
        self.show_performance_settings = show_performance_settings

        # Initialize all widget attributes to None first
        self.control_panel = None
        self.info_panel = None
        self.splitter = None
        self.search_input = None
        self.column_filter = None
        self.apply_filter_btn = None
        self.clear_filter_btn = None
        self.chunk_size_spin = None
        self.cache_size_spin = None
        self.auto_optimize_cb = None
        self.export_csv_btn = None
        self.export_excel_btn = None
        self.info_label = None
        self.memory_label = None
        self.memory_progress = None
        self.performance_log = None

        # Performance settings
        self.chunk_size = 1000
        self.cache_size = 10000
        self.memory_warning_threshold = 500  # MB

        # Initialize UI
        self._init_ui()
        self._init_model()
        self._setup_connections()
        self._start_monitoring()

        # Load initial data
        if dataframe is not None:
            self.set_dataframe(dataframe)

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Control panel (optional)
        if self.show_controls:
            control_panel = self._create_control_panel()
            layout.addWidget(control_panel)
            self.control_panel = control_panel
        else:
            # Control panel is not created, but widget attributes
            # are already initialized to None in __init__
            self.control_panel = None

        # Main content area
        if self.show_info:
            # Use splitter when info panel is shown
            splitter = QSplitter(Qt.Vertical)
            layout.addWidget(splitter)

            # Table view
            self.table_view = QTableView()
            self._apply_table_theme()
            self.table_view.setAlternatingRowColors(False)  # We'll handle this in model
            self.table_view.setSelectionBehavior(QTableView.SelectRows)
            self.table_view.setSortingEnabled(False)  # Disable for performance
            self.table_view.verticalHeader().setDefaultSectionSize(
                28
            )  # Slightly taller rows
            self.table_view.setShowGrid(True)

            # Enable virtual scrolling for performance
            self.table_view.setVerticalScrollMode(QTableView.ScrollPerPixel)
            self.table_view.setHorizontalScrollMode(QTableView.ScrollPerPixel)

            splitter.addWidget(self.table_view)

            # Statistics and info panel
            info_panel = self._create_info_panel()
            splitter.addWidget(info_panel)
            self.info_panel = info_panel

            # Set splitter proportions
            splitter.setStretchFactor(0, 3)  # Table gets most space
            splitter.setStretchFactor(1, 1)  # Info panel gets less space

            self.splitter = splitter
        else:
            # Just show table directly when no info panel
            self.table_view = QTableView()
            self._apply_table_theme()
            self.table_view.setAlternatingRowColors(False)  # We'll handle this in model
            self.table_view.setSelectionBehavior(QTableView.SelectRows)
            self.table_view.setSortingEnabled(False)  # Disable for performance
            self.table_view.verticalHeader().setDefaultSectionSize(
                28
            )  # Slightly taller rows
            self.table_view.setShowGrid(True)

            # Enable virtual scrolling for performance
            self.table_view.setVerticalScrollMode(QTableView.ScrollPerPixel)
            self.table_view.setHorizontalScrollMode(QTableView.ScrollPerPixel)

            layout.addWidget(self.table_view)

            self.info_panel = None
            self.splitter = None

    def _apply_table_theme(self):
        """Apply consistent theme styling to the table view."""
        # Apply stylesheet to match the application theme
        table_style = """
            QTableView {
                background-color: #14171b;
                alternate-background-color: #191e21;
                color: #ffffff;
                gridline-color: #191e21;
                border: 1px solid #191e21;
                border-radius: 4px;
                selection-background-color: #5680c2;
                selection-color: #ffffff;
                font-size: 13px;
            }
            
            QTableView::item {
                padding: 6px;
                border-bottom: 1px solid #191e21;
                border-right: 1px solid #191e21;
            }
            
            QTableView::item:selected {
                background-color: #5680c2;
                color: #ffffff;
            }
            
            QTableView::item:hover {
                background-color: #232323;
                color: #ffffff;
            }
            
            QTableCornerButton::section {
                background-color: #191e21;
                border: 1px solid #191e21;
                border-radius: 0px;
            }
        """

        self.table_view.setStyleSheet(table_style)

        # Style the headers to match theme
        header_style = """
            QHeaderView {
                background-color: #191e21;
                color: #ffffff;
                border: none;
                font-size: 13px;
                font-weight: bold;
            }
            
            QHeaderView::section {
                background-color: #191e21;
                color: #ffffff;
                padding: 8px 6px;
                border: none;
                border-right: 1px solid #14171b;
                border-bottom: 1px solid #14171b;
                text-align: left;
            }
            
            QHeaderView::section:hover {
                background-color: #232323;
            }
        """

        self.table_view.horizontalHeader().setStyleSheet(header_style)
        self.table_view.verticalHeader().setStyleSheet(header_style)

    def _create_control_panel(self) -> QWidget:
        """Create the control panel with search, filters, and settings."""
        panel = QGroupBox("Controls")
        layout = QHBoxLayout(panel)

        # Search functionality (optional)
        if self.show_search:
            search_group = QGroupBox("Search & Filter")
            search_layout = QHBoxLayout(search_group)

            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("Search in data...")
            search_layout.addWidget(QLabel("Search:"))
            search_layout.addWidget(self.search_input)

            # Column filter
            self.column_filter = QComboBox()
            self.column_filter.addItem("All Columns")
            search_layout.addWidget(QLabel("In:"))
            search_layout.addWidget(self.column_filter)

            # Apply filter button
            self.apply_filter_btn = QPushButton("Apply Filter")
            self.clear_filter_btn = QPushButton("Clear")
            search_layout.addWidget(self.apply_filter_btn)
            search_layout.addWidget(self.clear_filter_btn)

            layout.addWidget(search_group)
        else:
            # Initialize as None when not shown
            self.search_input = None
            self.column_filter = None
            self.apply_filter_btn = None
            self.clear_filter_btn = None

        # Performance settings (optional)
        if self.show_performance_settings:
            perf_group = QGroupBox("Performance")
            perf_layout = QHBoxLayout(perf_group)

            perf_layout.addWidget(QLabel("Chunk Size:"))
            self.chunk_size_spin = QSpinBox()
            self.chunk_size_spin.setRange(100, 10000)
            self.chunk_size_spin.setValue(self.chunk_size)
            self.chunk_size_spin.setSuffix(" rows")
            perf_layout.addWidget(self.chunk_size_spin)

            perf_layout.addWidget(QLabel("Cache:"))
            self.cache_size_spin = QSpinBox()
            self.cache_size_spin.setRange(1000, 100000)
            self.cache_size_spin.setValue(self.cache_size)
            self.cache_size_spin.setSuffix(" rows")
            perf_layout.addWidget(self.cache_size_spin)

            # Memory optimization
            self.auto_optimize_cb = QCheckBox("Auto Optimize")
            self.auto_optimize_cb.setChecked(True)
            perf_layout.addWidget(self.auto_optimize_cb)

            layout.addWidget(perf_group)
        else:
            # Initialize as None when not shown
            self.chunk_size_spin = None
            self.cache_size_spin = None
            self.auto_optimize_cb = None

        # Export functionality (optional)
        if self.show_export:
            export_group = QGroupBox("Export")
            export_layout = QHBoxLayout(export_group)

            self.export_csv_btn = QPushButton("Export CSV")
            self.export_excel_btn = QPushButton("Export Excel")
            export_layout.addWidget(self.export_csv_btn)
            export_layout.addWidget(self.export_excel_btn)

            layout.addWidget(export_group)
        else:
            # Initialize as None when not shown
            self.export_csv_btn = None
            self.export_excel_btn = None

        return panel

    def _create_info_panel(self) -> QWidget:
        """Create the information and statistics panel."""
        panel = QGroupBox("Information & Statistics")
        layout = QVBoxLayout(panel)

        # Data info
        data_info = QGroupBox("Dataset Info")
        data_layout = QVBoxLayout(data_info)

        self.info_label = QLabel("No data loaded")
        self.info_label.setWordWrap(True)
        data_layout.addWidget(self.info_label)

        layout.addWidget(data_info)

        # Memory usage
        memory_group = QGroupBox("Memory Usage")
        memory_layout = QVBoxLayout(memory_group)

        self.memory_label = QLabel("Memory: 0 MB")
        memory_layout.addWidget(self.memory_label)

        self.memory_progress = QProgressBar()
        self.memory_progress.setMaximum(self.memory_warning_threshold)
        memory_layout.addWidget(self.memory_progress)

        layout.addWidget(memory_group)

        # Performance log
        log_group = QGroupBox("Performance Log")
        log_layout = QVBoxLayout(log_group)

        self.performance_log = QTextEdit()
        self.performance_log.setMaximumHeight(150)
        self.performance_log.setReadOnly(True)
        log_layout.addWidget(self.performance_log)

        layout.addWidget(log_group)

        return panel

    def _init_model(self):
        """Initialize the table model."""
        self.model = PolarsTableModel(
            self.dataframe, chunk_size=self.chunk_size, cache_size=self.cache_size
        )
        self.table_view.setModel(self.model)

    def _setup_connections(self):
        """Setup signal connections."""
        # Search and filter (only if widgets exist)
        if self.apply_filter_btn is not None:
            self.apply_filter_btn.clicked.connect(self._apply_filter)
        if self.clear_filter_btn is not None:
            self.clear_filter_btn.clicked.connect(self._clear_filter)
        if self.search_input is not None:
            self.search_input.returnPressed.connect(self._apply_filter)

        # Performance settings (only if widgets exist)
        if self.chunk_size_spin is not None:
            self.chunk_size_spin.valueChanged.connect(self._update_chunk_size)
        if self.cache_size_spin is not None:
            self.cache_size_spin.valueChanged.connect(self._update_cache_size)

        # Export (only if widgets exist)
        if self.export_csv_btn is not None:
            self.export_csv_btn.clicked.connect(self._export_csv)
        if self.export_excel_btn is not None:
            self.export_excel_btn.clicked.connect(self._export_excel)

        # Model signals
        self.model.dataLoadProgress.connect(self._on_load_progress)
        self.model.errorOccurred.connect(self._on_error)

    def _start_monitoring(self):
        """Start performance monitoring timer."""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_performance_stats)
        self.monitor_timer.start(2000)  # Update every 2 seconds

    def set_dataframe(self, dataframe: pl.DataFrame):
        """
        Set a new dataframe to display.

        Args:
            dataframe: New Polars DataFrame
        """
        self.dataframe = dataframe
        self.filtered_dataframe = None

        # Update model
        self.model.set_dataframe(dataframe)

        # Update column filter (only if it exists)
        if self.column_filter is not None:
            self.column_filter.clear()
            self.column_filter.addItem("All Columns")
            if not dataframe.is_empty():
                for col in dataframe.columns:
                    self.column_filter.addItem(col)

        # Update info
        self._update_info_display()
        self._log_performance(
            f"DataFrame loaded: {len(dataframe)} rows, {len(dataframe.columns)} columns"
        )

    def _apply_filter(self):
        """Apply search filter to the dataframe."""
        # Check if search widgets are available
        if self.search_input is None or self.column_filter is None:
            return

        search_text = self.search_input.text().strip()
        column_name = self.column_filter.currentText()

        if not search_text:
            self._clear_filter()
            return

        if self.dataframe is None or self.dataframe.is_empty():
            return

        try:
            if column_name == "All Columns":
                # Search in all string columns
                conditions = []
                for col in self.dataframe.columns:
                    if self.dataframe[col].dtype in [pl.Utf8, pl.String]:
                        conditions.append(
                            pl.col(col)
                            .cast(pl.Utf8)
                            .str.contains(search_text, case_sensitive=False)
                            .fill_null(False)
                        )

                if conditions:
                    # Combine conditions with OR
                    combined_condition = conditions[0]
                    for condition in conditions[1:]:
                        combined_condition = combined_condition | condition

                    self.filtered_dataframe = self.dataframe.filter(combined_condition)
                else:
                    self.filtered_dataframe = pl.DataFrame()
            else:
                # Search in specific column
                if column_name in self.dataframe.columns:
                    condition = (
                        pl.col(column_name)
                        .cast(pl.Utf8)
                        .str.contains(search_text, case_sensitive=False)
                        .fill_null(False)
                    )
                    self.filtered_dataframe = self.dataframe.filter(condition)
                else:
                    self.filtered_dataframe = pl.DataFrame()

            # Update model with filtered data
            self.model.set_dataframe(self.filtered_dataframe)
            self._update_info_display()
            self._log_performance(
                f"Filter applied: '{search_text}' -> {len(self.filtered_dataframe)} rows"
            )

        except Exception as e:
            logger.error(f"Error applying filter: {e}")
            self._log_performance(f"Filter error: {str(e)}")

    def _clear_filter(self):
        """Clear the current filter."""
        # Clear search input only if it exists
        if self.search_input is not None:
            self.search_input.clear()

        self.filtered_dataframe = None

        if self.dataframe is not None:
            self.model.set_dataframe(self.dataframe)
            self._update_info_display()
            self._log_performance("Filter cleared")

    def _update_chunk_size(self, value: int):
        """Update the chunk size for lazy loading."""
        self.chunk_size = value
        self.model.chunk_size = value
        self._log_performance(f"Chunk size updated: {value}")

    def _update_cache_size(self, value: int):
        """Update the cache size."""
        self.cache_size = value
        self.model.cache_size = value
        self._log_performance(f"Cache size updated: {value}")

    def _update_performance_stats(self):
        """Update performance statistics display."""
        try:
            memory_stats = self.model.get_memory_usage()

            # Update memory display (only if widgets exist)
            cache_mb = memory_stats.get("cache_size_mb", 0)
            total_mb = memory_stats.get("total_process_memory_mb", 0)

            if hasattr(self, "memory_label") and self.memory_label is not None:
                self.memory_label.setText(
                    f"Cache: {cache_mb:.1f} MB | Process: {total_mb:.1f} MB"
                )

            # Update progress bar (only if it exists)
            if hasattr(self, "memory_progress") and self.memory_progress is not None:
                self.memory_progress.setValue(
                    min(int(total_mb), self.memory_warning_threshold)
                )

            # Check for memory warnings
            if total_mb > self.memory_warning_threshold:
                self.memoryWarning.emit(total_mb)
                if (
                    hasattr(self, "auto_optimize_cb")
                    and self.auto_optimize_cb is not None
                    and self.auto_optimize_cb.isChecked()
                ):
                    self._optimize_memory()

        except Exception as e:
            logger.error(f"Error updating performance stats: {e}")

    def _optimize_memory(self):
        """Optimize memory usage by clearing caches."""
        self.model._data_cache.clear()
        self.model._cache_access_times.clear()
        self._log_performance("Memory optimized - caches cleared")

    def _update_info_display(self):
        """Update the information display."""
        # Only update if info label exists
        if not hasattr(self, "info_label") or self.info_label is None:
            return

        current_df = (
            self.filtered_dataframe
            if self.filtered_dataframe is not None
            else self.dataframe
        )

        if current_df is None or current_df.is_empty():
            self.info_label.setText("No data loaded")
            return

        # Basic stats
        rows = len(current_df)
        cols = len(current_df.columns)

        # Memory estimation
        estimated_mb = (rows * cols * 8) / (1024 * 1024)  # Rough estimate

        info_text = f"""
        <b>Dataset Overview:</b><br>
        Rows: {rows:,}<br>
        Columns: {cols}<br>
        Estimated Size: {estimated_mb:.1f} MB<br>
        
        <b>Columns:</b><br>
        """

        # Add column information
        # Show first 10 columns
        for i, col in enumerate(current_df.columns[:10]):
            col_type = current_df[col].dtype
            info_text += f"• {col} ({col_type})<br>"

        if len(current_df.columns) > 10:
            info_text += f"... and {len(current_df.columns) - 10} more columns<br>"

        self.info_label.setText(info_text)

    def _log_performance(self, message: str):
        """Log a performance message."""
        # Only log to UI if performance log widget exists
        if hasattr(self, "performance_log") and self.performance_log is not None:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            self.performance_log.append(log_entry)

            # Keep log size manageable
            if self.performance_log.document().lineCount() > 100:
                # Remove old lines
                cursor = self.performance_log.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.movePosition(cursor.Down, cursor.KeepAnchor, 50)
                cursor.removeSelectedText()

        # Always log to logger for debugging purposes
        logger.debug(f"PolarsTableViewer: {message}")

    def _export_csv(self):
        """Export current dataframe to CSV."""
        try:
            current_df = (
                self.filtered_dataframe
                if self.filtered_dataframe is not None
                else self.dataframe
            )
            if current_df is None or current_df.is_empty():
                self._log_performance("Export failed: No data to export")
                return

            from qtpy.QtWidgets import QFileDialog

            filename, _ = QFileDialog.getSaveFileName(
                self, "Export CSV", "dataframe_export.csv", "CSV Files (*.csv)"
            )

            if filename:
                current_df.write_csv(filename)
                self._log_performance(f"Data exported to CSV: {filename}")

        except Exception as e:
            logger.error(f"CSV export error: {e}")
            self._log_performance(f"CSV export error: {str(e)}")

    def _export_excel(self):
        """Export current dataframe to Excel."""
        try:
            current_df = (
                self.filtered_dataframe
                if self.filtered_dataframe is not None
                else self.dataframe
            )
            if current_df is None or current_df.is_empty():
                self._log_performance("Export failed: No data to export")
                return

            from qtpy.QtWidgets import QFileDialog

            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Excel", "dataframe_export.xlsx", "Excel Files (*.xlsx)"
            )

            if filename:
                current_df.write_excel(filename)
                self._log_performance(f"Data exported to Excel: {filename}")

        except Exception as e:
            logger.error(f"Excel export error: {e}")
            self._log_performance(f"Excel export error: {str(e)}")

    def _on_load_progress(self, progress: int):
        """Handle data loading progress."""
        self._log_performance(f"Loading progress: {progress}%")

    def _on_error(self, error_message: str):
        """Handle model errors."""
        self._log_performance(f"Error: {error_message}")
        logger.error(f"Model error: {error_message}")

    def get_selected_data(self) -> Optional[pl.DataFrame]:
        """
        Get the currently selected rows as a new DataFrame.

        Returns:
            Selected data as Polars DataFrame or None if no selection
        """
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return None

        current_df = (
            self.filtered_dataframe
            if self.filtered_dataframe is not None
            else self.dataframe
        )
        if current_df is None:
            return None

        selected_indices = [index.row() for index in selection]
        return current_df[selected_indices]

    def refresh(self):
        """Refresh the view and clear caches."""
        self.model._data_cache.clear()
        self.model._cache_access_times.clear()
        self.model.beginResetModel()
        self.model.endResetModel()
        self._update_info_display()
        self._log_performance("View refreshed")

    def set_controls_visibility(self, visible: bool):
        """
        Toggle visibility of the control panel.

        Args:
            visible: Whether to show the control panel
        """
        if hasattr(self, "control_panel") and self.control_panel is not None:
            self.control_panel.setVisible(visible)

    def set_info_visibility(self, visible: bool):
        """
        Toggle visibility of the info panel.

        Args:
            visible: Whether to show the info panel
        """
        if hasattr(self, "info_panel") and self.info_panel is not None:
            self.info_panel.setVisible(visible)

    def set_search_visibility(self, visible: bool):
        """
        Toggle visibility of search controls within the control panel.

        Args:
            visible: Whether to show search controls
        """
        if (
            self.search_input is not None
            and self.column_filter is not None
            and self.apply_filter_btn is not None
            and self.clear_filter_btn is not None
        ):

            # Find the search group widget and toggle its visibility
            search_group = self.search_input.parent()
            if search_group is not None:
                search_group.setVisible(visible)

    def set_export_visibility(self, visible: bool):
        """
        Toggle visibility of export controls within the control panel.

        Args:
            visible: Whether to show export controls
        """
        if self.export_csv_btn is not None and self.export_excel_btn is not None:
            # Find the export group widget and toggle its visibility
            export_group = self.export_csv_btn.parent()
            if export_group is not None:
                export_group.setVisible(visible)

    def set_performance_settings_visibility(self, visible: bool):
        """
        Toggle visibility of performance settings within the control panel.

        Args:
            visible: Whether to show performance settings
        """
        if (
            self.chunk_size_spin is not None
            and self.cache_size_spin is not None
            and self.auto_optimize_cb is not None
        ):

            # Find the performance group widget and toggle its visibility
            perf_group = self.chunk_size_spin.parent()
            if perf_group is not None:
                perf_group.setVisible(visible)

    def get_table_view(self):
        """
        Get direct access to the underlying QTableView for custom styling or operations.

        Returns:
            QTableView: The table view widget
        """
        return self.table_view
