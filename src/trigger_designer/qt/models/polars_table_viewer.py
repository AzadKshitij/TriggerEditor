"""
Polars DataFrame table viewer for the Data Preview surfaces.

A memory-conscious table widget for Polars DataFrames:

- paging: the model exposes one page at a time over a bounded frame
- lazy row-chunk loading with a bounded cache (keys stay absolute)
- data type-specific formatting
- search/filter over the loaded frame
- CSV/Excel export of the loaded frame

Theming comes from ``base.qss`` (the view, headers and selection states are
styled there). The one thing QSS cannot express is a data-driven per-row
tint, so the model supplies the even/odd row background from the active
theme's tokens via ``Qt.BackgroundRole``.
"""

import polars as pl
from typing import Any, Dict, List, Optional, Union, Tuple
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QLineEdit,
    QPushButton,
    QLabel,
    QComboBox,
    QGroupBox,
    QScrollArea,
    QApplication,
    QShortcut,
    QMenu,
    QAction,
)
from qtpy.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSettings,
    Qt,
    Signal,
)
from qtpy.QtGui import QFont, QColor, QKeySequence
from loguru import logger
import time
from datetime import datetime, date

from trigger_designer.qt.resource_manager import ResourceManager


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
        parent: QObject | None = None,
    ):
        """
        Initialize the model with a Polars DataFrame.

        Args:
            dataframe: The Polars DataFrame to display
            chunk_size: Number of rows to load at once for lazy loading
            cache_size: Maximum number of rows to keep in memory cache
        """
        super().__init__(parent)

        self._dataframe = dataframe if dataframe is not None else pl.DataFrame()
        self.chunk_size = chunk_size
        self.cache_size = cache_size

        # Data cache - stores chunks of data as (start_row, data_chunk) pairs
        self._data_cache: Dict[int, Tuple[pl.DataFrame, int]] = {}
        self._cache_access_times: Dict[int, float] = {}

        # Paging: the view shows one page at a time; the chunk cache below
        # stays keyed by absolute rows.
        self.page_size = 250
        self.page_index = 0

        # Sort state; sorting re-orders the frame in place and resets paging.
        self._sort_column: int | None = None
        self._sort_descending = False
        self._row_colors: tuple[QColor, QColor] | None = None

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
        self.page_index = 0
        self._sort_column = None
        self._sort_descending = False
        self._row_colors = None
        self._update_column_info()
        self.endResetModel()
        logger.info(
            f"DataFrame updated: {self._total_rows} rows, {self._total_columns} columns"
        )

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of rows on the current page."""
        if parent.isValid():
            return 0
        return max(0, min(self.page_size, self._total_rows - self.page_offset))

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the total number of columns."""
        return self._total_columns

    @property
    def page_offset(self) -> int:
        """Absolute index of the first row on the current page."""
        return self.page_index * self.page_size

    @property
    def page_count(self) -> int:
        """Number of pages; at least 1 so an empty frame stays pageable."""
        if self._total_rows <= 0:
            return 1
        return (self._total_rows + self.page_size - 1) // self.page_size

    @property
    def total_rows(self) -> int:
        """Total rows in the frame, across all pages."""
        return self._total_rows

    @property
    def sort_column(self) -> int | None:
        """Index of the sorted column, or None when unsorted."""
        return self._sort_column

    @property
    def sort_descending(self) -> bool:
        """Whether the current sort is descending."""
        return self._sort_descending

    def set_page(self, index: int) -> None:
        """Show the given page, clamped to the valid range."""
        index = max(0, min(index, self.page_count - 1))
        if index == self.page_index:
            return
        self.beginResetModel()
        self.page_index = index
        self.endResetModel()

    def set_page_size(self, size: int) -> None:
        """Change the page size, keeping the first visible row in view."""
        if size <= 0 or size == self.page_size:
            return
        first_row = self.page_offset
        self.beginResetModel()
        self.page_size = size
        self.page_index = first_row // size
        self.endResetModel()

    def sort_by(self, column: int, descending: bool = False) -> None:
        """Sort the frame by one column (nulls last) and reset paging.

        The sort is applied to the model's own frame, so the chunk cache and
        the current page are invalidated. Callers that keep their own copy of
        the frame (e.g. the viewer's ``filtered_dataframe``) should treat that
        copy as unsorted source data.
        """
        if column < 0 or column >= len(self._column_names):
            return
        if self._dataframe.is_empty():
            return

        name = self._column_names[column]
        try:
            sorted_frame = self._dataframe.sort(
                name, descending=descending, nulls_last=True
            )
        except Exception as e:
            logger.warning(f"Unable to sort by column '{name}': {e}")
            return

        self.beginResetModel()
        self._dataframe = sorted_frame
        self._data_cache.clear()
        self._cache_access_times.clear()
        self.page_index = 0
        self._sort_column = column
        self._sort_descending = descending
        self._update_column_info()
        self.endResetModel()

    def _get_row_background_colors(self) -> tuple[QColor, QColor]:
        """Even/odd row tints from the active theme, resolved once per model.

        ``base.qss`` cannot target row parity, so the model hands these to the
        view through ``Qt.BackgroundRole`` - using the same theme tokens the
        stylesheet uses for the table's own background.
        """
        if self._row_colors is None:
            rsm = ResourceManager()
            self._row_colors = (
                rsm.get_theme_color("background_primary"),
                rsm.get_theme_color("background_secondary", "#191e21"),
            )
        return self._row_colors

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
        Get data for a view row, using cache when possible.

        ``row`` is page-relative (what the view asks for); chunk keys and the
        cache itself stay absolute.

        Args:
            row: View row index on the current page

        Returns:
            Data value or None if not available
        """
        absolute_row = self.page_offset + row
        if absolute_row >= self._total_rows:
            return None

        chunk_key = self._get_chunk_key(absolute_row)
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
            row_in_chunk = absolute_row - chunk_key

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

        # `createIndex` does not validate against the model dimensions, so a
        # synthetically built index can be out of range. Such a cell has no
        # data at all - only a genuine load miss (see below) is "loading".
        absolute_row = self.page_offset + row
        if absolute_row >= self._total_rows or col >= self._total_columns:
            return None

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
            # Row parity uses the absolute row so striping stays stable across
            # page boundaries.
            even, odd = self._get_row_background_colors()
            return even if (self.page_offset + row) % 2 == 0 else odd

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
                # Absolute row numbers: row 1 of page 2 is still row 251.
                # Header text colour comes from base.qss (QHeaderView::section).
                return str(self.page_offset + section + 1)

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            font.setPointSize(12)  # Slightly larger font for headers
            return font

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

        return {
            "cache_size_mb": cache_memory / (1024 * 1024),
            "cached_chunks": len(self._data_cache),
            "chunk_size": self.chunk_size,
            "total_rows": self._total_rows,
            "total_columns": self._total_columns,
        }


class PolarsTableViewer(QWidget):
    """
    Table viewer widget for Polars DataFrames.

    The model shows one page at a time and loads row chunks lazily, so the
    widget stays responsive for frames far larger than the viewport. Sorting
    is model-level (click a header): the frame is re-ordered in place and
    paging resets to the first page.

    Customization Options:
    - show_controls: Show/hide the entire control panel
    - show_info: Show/hide the information and statistics panel
    - show_search: Show/hide search and filter functionality
    - show_export: Show/hide export buttons (CSV/Excel)

    Usage Examples:

    # Full-featured viewer (default)
    viewer = PolarsTableViewer(dataframe=df)

    # Data-only viewer (minimal interface)
    viewer = PolarsTableViewer(
        dataframe=df,
        show_controls=False,
        show_info=False
    )
    """

    # Signals
    filterChanged = Signal(str)  # Emitted when filter text changes

    def __init__(
        self,
        dataframe: Optional[pl.DataFrame] = None,
        parent: Optional[QWidget] = None,
        show_controls: bool = True,
        show_info: bool = True,
        show_search: bool = True,
        show_export: bool = True,
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
        """
        super().__init__(parent)

        self.dataframe = dataframe
        self.filtered_dataframe: Optional[pl.DataFrame] = None

        # UI visibility options
        self.show_controls = show_controls
        self.show_info = show_info
        self.show_search = show_search
        self.show_export = show_export

        # Initialize all widget attributes to None first
        self.stats_panel = None
        self.combined_panel = None
        self.search_input = None
        self.column_filter = None
        self.apply_filter_btn = None
        self.clear_filter_btn = None
        self.export_csv_btn = None
        self.export_excel_btn = None
        self.info_label = None

        # Chunk/cache sizing for the model
        self.chunk_size = 1000
        self.cache_size = 10000

        # Initialize UI
        self._init_ui()
        self._init_model()
        self._setup_connections()

        # Load initial data
        if dataframe is not None:
            self.set_dataframe(dataframe)

    def _init_ui(self):
        """Initialize the user interface."""
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to maximize space

        # Create scroll area to contain all content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create content widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # 1. Statistics section at the very top (if enabled)
        if self.show_info:
            stats_panel = self._create_stats_panel()
            layout.addWidget(stats_panel)
            self.stats_panel = stats_panel
        else:
            self.stats_panel = None

        # 2. Combined search and export controls in same row (if enabled)
        if self.show_controls and (self.show_search or self.show_export):
            combined_panel = self._create_combined_controls_panel()
            layout.addWidget(combined_panel)
            self.combined_panel = combined_panel
        else:
            self.combined_panel = None
            # Initialize widgets as None when not shown
            self.search_input = None
            self.column_filter = None
            self.apply_filter_btn = None
            self.clear_filter_btn = None
            self.export_csv_btn = None
            self.export_excel_btn = None

        # 3. Table view (main content) - takes all available space
        self.table_view = QTableView()
        # Row striping is painted by the model (Qt.BackgroundRole); view,
        # headers and selection states are themed by base.qss.
        self.table_view.setAlternatingRowColors(False)
        self.table_view.setSelectionBehavior(
            QTableView.SelectItems
        )  # Allow cell selection for copying
        # Qt's own sorting would fight paging; model sorting is the one path.
        self.table_view.setSortingEnabled(False)
        header = self.table_view.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(-1, Qt.AscendingOrder)  # hidden until sorted
        self.table_view.verticalHeader().setDefaultSectionSize(
            28
        )  # Slightly taller rows
        self.table_view.setShowGrid(True)

        # Enable virtual scrolling for performance
        self.table_view.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.table_view.setHorizontalScrollMode(QTableView.ScrollPerPixel)

        # Enable copy functionality
        self._setup_copy_functionality()

        # Add table with stretch factor to take most of the space
        layout.addWidget(self.table_view, 9)  # 90% of space for table

        # Set content widget in scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

    def _setup_copy_functionality(self):
        """Setup keyboard shortcuts and context menu for copying table data."""
        # Create keyboard shortcut for Ctrl+C
        copy_shortcut = QShortcut(QKeySequence.Copy, self.table_view)
        copy_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        copy_shortcut.activated.connect(self.copy_selected_to_clipboard)

        # Create context menu for right-click copy
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, position):
        """Show context menu with copy options."""

        menu = QMenu(self.table_view)

        # Copy selected cells
        copy_action = QAction("Copy Selected", self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_selected_to_clipboard)
        menu.addAction(copy_action)

        # Copy selected rows (if row selection)
        copy_rows_action = QAction("Copy Selected Rows", self)
        copy_rows_action.triggered.connect(self.copy_selected_rows_to_clipboard)
        menu.addAction(copy_rows_action)

        # Copy all visible data
        copy_all_action = QAction("Copy All Visible Data", self)
        copy_all_action.triggered.connect(self.copy_all_visible_to_clipboard)
        menu.addAction(copy_all_action)

        # Show menu at cursor position
        menu.exec_(self.table_view.mapToGlobal(position))

    def copy_selected_to_clipboard(self):
        """Copy currently selected cells to clipboard in tab-separated format."""
        try:
            selection_model = self.table_view.selectionModel()
            if not selection_model or not selection_model.hasSelection():
                return

            selected_indexes = selection_model.selectedIndexes()
            if not selected_indexes:
                return

            # Sort indexes by row and column
            selected_indexes.sort(key=lambda idx: (idx.row(), idx.column()))

            # Group by rows
            rows_data = {}
            for index in selected_indexes:
                row = index.row()
                col = index.column()
                data = self.model.data(index, Qt.DisplayRole) or ""

                if row not in rows_data:
                    rows_data[row] = {}
                rows_data[row][col] = str(data)

            # Build text with tab separation
            clipboard_text = []
            for row in sorted(rows_data.keys()):
                row_data = rows_data[row]
                # Get all column indices for this row
                cols = sorted(row_data.keys())
                row_text = "\t".join(row_data.get(col, "") for col in cols)
                clipboard_text.append(row_text)

            # Copy to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(clipboard_text))

            logger.info(f"Copied {len(clipboard_text)} rows to clipboard")

        except Exception as e:
            logger.error(f"Error copying to clipboard: {str(e)}")

    def copy_selected_rows_to_clipboard(self):
        """Copy complete selected rows to clipboard with headers."""
        try:
            selection_model = self.table_view.selectionModel()
            if not selection_model or not selection_model.hasSelection():
                return

            selected_rows = set()
            for index in selection_model.selectedIndexes():
                selected_rows.add(index.row())

            if not selected_rows:
                return

            # Get headers
            headers = []
            for col in range(self.model.columnCount()):
                header = (
                    self.model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
                    or f"Column_{col}"
                )
                headers.append(str(header))

            clipboard_text = ["\t".join(headers)]

            # Get data for selected rows
            for row in sorted(selected_rows):
                row_data = []
                for col in range(self.model.columnCount()):
                    index = self.model.index(row, col)
                    data = self.model.data(index, Qt.DisplayRole) or ""
                    row_data.append(str(data))
                clipboard_text.append("\t".join(row_data))

            # Copy to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(clipboard_text))

            logger.info(
                f"Copied {len(selected_rows)} complete rows with headers to clipboard"
            )

        except Exception as e:
            logger.error(f"Error copying rows to clipboard: {str(e)}")

    def copy_all_visible_to_clipboard(self):
        """Copy all visible data to clipboard with headers."""
        try:
            if not self.model:
                return

            # Get headers
            headers = []
            for col in range(self.model.columnCount()):
                header = (
                    self.model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
                    or f"Column_{col}"
                )
                headers.append(str(header))

            clipboard_text = ["\t".join(headers)]

            # Get all visible data
            for row in range(self.model.rowCount()):
                row_data = []
                for col in range(self.model.columnCount()):
                    index = self.model.index(row, col)
                    data = self.model.data(index, Qt.DisplayRole) or ""
                    row_data.append(str(data))
                clipboard_text.append("\t".join(row_data))

            # Copy to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(clipboard_text))

            logger.info(
                f"Copied all {self.model.rowCount()} visible rows with headers to clipboard"
            )

        except Exception as e:
            logger.error(f"Error copying all data to clipboard: {str(e)}")

    def _create_stats_panel(self) -> QWidget:
        """Create a compact statistics panel."""
        panel = QGroupBox("Dataset Statistics")
        layout = QVBoxLayout(panel)

        # Data info - compact display; styling comes from base.qss
        self.info_label = QLabel("No data loaded")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        return panel

    def _create_combined_controls_panel(self) -> QWidget:
        """Create a combined panel with search and export controls in the same row."""
        panel = QGroupBox("Search & Export Controls")
        main_layout = QHBoxLayout(panel)

        # Search section (if enabled)
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

            # Apply filter buttons
            self.apply_filter_btn = QPushButton("Apply")
            self.clear_filter_btn = QPushButton("Clear")
            search_layout.addWidget(self.apply_filter_btn)
            search_layout.addWidget(self.clear_filter_btn)

            main_layout.addWidget(search_group)
        else:
            # Initialize as None when not shown
            self.search_input = None
            self.column_filter = None
            self.apply_filter_btn = None
            self.clear_filter_btn = None

        # Export section (if enabled)
        if self.show_export:
            export_group = QGroupBox("Export")
            export_layout = QHBoxLayout(export_group)

            self.export_csv_btn = QPushButton("CSV")
            self.export_excel_btn = QPushButton("Excel")
            export_layout.addWidget(self.export_csv_btn)
            export_layout.addWidget(self.export_excel_btn)

            main_layout.addWidget(export_group)
        else:
            # Initialize as None when not shown
            self.export_csv_btn = None
            self.export_excel_btn = None

        return panel

    def _init_model(self):
        """Initialize the table model (owned by the view that shows it)."""
        self.model = PolarsTableModel(
            self.dataframe,
            chunk_size=self.chunk_size,
            cache_size=self.cache_size,
            parent=self,
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

        # Export (only if widgets exist)
        if self.export_csv_btn is not None:
            self.export_csv_btn.clicked.connect(self.export_csv)
        if self.export_excel_btn is not None:
            self.export_excel_btn.clicked.connect(self.export_excel)

        # Header clicks drive model-side sorting (Qt's own sorting stays off).
        self.table_view.horizontalHeader().sectionClicked.connect(
            self._on_header_clicked
        )

        # Model signals
        self.model.dataLoadProgress.connect(self._on_load_progress)
        self.model.errorOccurred.connect(self._on_error)

    def _on_header_clicked(self, column: int) -> None:
        """Sort by the clicked column, toggling direction on repeat clicks."""
        if self.model.columnCount() == 0:
            return
        if self.model.sort_column == column:
            descending = not self.model.sort_descending
        else:
            descending = False
        self.model.sort_by(column, descending)
        # sort_by is a no-op for unsupported dtypes, so mirror the model state.
        if self.model.sort_column == column:
            self.table_view.horizontalHeader().setSortIndicator(
                column, Qt.DescendingOrder if descending else Qt.AscendingOrder
            )

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
        logger.debug(
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
                            .str.contains(search_text, literal=False, strict=False)
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
                        .str.contains(search_text, literal=False, strict=False)
                        .fill_null(False)
                    )
                    self.filtered_dataframe = self.dataframe.filter(condition)
                else:
                    self.filtered_dataframe = pl.DataFrame()

            # Update model with filtered data
            self.model.set_dataframe(self.filtered_dataframe)
            self._update_info_display()
            logger.debug(
                f"Filter applied: '{search_text}' -> {len(self.filtered_dataframe)} rows"
            )

        except Exception as e:
            logger.error(f"Error applying filter: {e}")

    def _clear_filter(self):
        """Clear the current filter."""
        # Clear search input only if it exists
        if self.search_input is not None:
            self.search_input.clear()

        self.filtered_dataframe = None

        if self.dataframe is not None:
            self.model.set_dataframe(self.dataframe)
            self._update_info_display()
            logger.debug("Filter cleared")

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

        # Compact single-line format
        info_text = f"Rows: {rows:,} | Columns: {cols} | Size: {estimated_mb:.1f} MB"

        self.info_label.setText(info_text)

    def export_csv(self) -> None:
        """Export the loaded frame to CSV (asks for a path first)."""
        try:
            current_df = (
                self.filtered_dataframe
                if self.filtered_dataframe is not None
                else self.dataframe
            )
            if current_df is None or current_df.is_empty():
                logger.debug("Export skipped: no data to export")
                return

            from qtpy.QtWidgets import QFileDialog

            filename, _ = QFileDialog.getSaveFileName(
                self, "Export CSV", "dataframe_export.csv", "CSV Files (*.csv)"
            )

            if filename:
                current_df.write_csv(filename)
                logger.debug(f"Data exported to CSV: {filename}")

        except Exception as e:
            logger.error(f"CSV export error: {e}")

    def export_excel(self) -> None:
        """Export the loaded frame to Excel (asks for a path first)."""
        try:
            current_df = (
                self.filtered_dataframe
                if self.filtered_dataframe is not None
                else self.dataframe
            )
            if current_df is None or current_df.is_empty():
                logger.debug("Export skipped: no data to export")
                return

            from qtpy.QtWidgets import QFileDialog

            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Excel", "dataframe_export.xlsx", "Excel Files (*.xlsx)"
            )

            if filename:
                current_df.write_excel(filename)
                logger.debug(f"Data exported to Excel: {filename}")

        except Exception as e:
            logger.error(f"Excel export error: {e}")

    def _on_load_progress(self, progress: int):
        """Handle data loading progress."""
        logger.debug(f"Loading progress: {progress}%")

    def _on_error(self, error_message: str):
        """Handle model errors."""
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
        logger.debug("View refreshed")

    def get_table_view(self):
        """
        Get direct access to the underlying QTableView for custom styling or operations.

        Returns:
            QTableView: The table view widget
        """
        return self.table_view
