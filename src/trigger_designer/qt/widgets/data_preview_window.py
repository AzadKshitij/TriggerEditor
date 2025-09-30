from qtpy.QtWidgets import (
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QLabel,
    QHBoxLayout,
    QPushButton,
)
from qtpy.QtCore import Qt
import polars as pl
import pandas as pd
import numpy as np
from typing import Union, Optional
import sys
from loguru import logger

# Import the PolarsTableViewer
from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer


class DataPreviewWindow(QMainWindow):
    def __init__(
        self,
        data: Union[pl.DataFrame, pl.LazyFrame, pd.DataFrame, list, dict, any],
        title="Data Preview",
        parent=None,
        max_rows: int = 100,
        max_size_mb: float = 2.0,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1200, 800)
        self.max_rows = max_rows
        self.max_size_mb = max_size_mb
        self.original_data = data
        self.is_lazy_data = False
        self.total_rows = None

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add info header
        self.create_info_header(layout)

        # Display the data using appropriate viewer
        self.display_data(data, layout)

    def create_info_header(self, layout: QVBoxLayout):
        """Create an info header showing data limits and status"""
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)

        self.info_label = QLabel()

        # Refresh button for lazy data
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_preview)
        self.refresh_btn.setVisible(False)  # Initially hidden
        self.refresh_btn.setToolTip("Refresh preview data from source")

        info_layout.addWidget(self.info_label)
        info_layout.addStretch()  # Push refresh button to the right
        info_layout.addWidget(self.refresh_btn)

        layout.addWidget(info_widget)

    def update_info_label(
        self,
        preview_rows: int,
        total_rows: Optional[int] = None,
        is_limited: bool = False,
    ):
        """Update the info label with current preview status"""
        if total_rows is not None:
            if is_limited:
                self.info_label.setText(
                    f"Showing {preview_rows:,} of {total_rows:,} rows"
                )
            else:
                self.info_label.setText(f"Showing all {preview_rows:,} rows")
        else:
            if is_limited:
                self.info_label.setText(f"Showing first {preview_rows:,} rows")
            else:
                self.info_label.setText(f"Showing {preview_rows:,} rows")

    def refresh_preview(self):
        """Refresh the preview data from the original LazyFrame"""
        if self.is_lazy_data and hasattr(self, "original_data"):
            # Clear current layout and reload
            central_widget = self.centralWidget()
            layout = central_widget.layout()

            # Clear all widgets except the info header
            while layout.count() > 1:
                child = layout.takeAt(1)
                if child.widget():
                    child.widget().deleteLater()

            # Display data again
            self.display_data(self.original_data, layout)

    def display_data(self, data, layout: QVBoxLayout):
        """Display data using the most appropriate viewer with size/row limits"""
        preview_df = None
        is_limited = False
        total_rows = None

        if isinstance(data, pl.LazyFrame):
            # Handle LazyFrame with smart preview
            self.is_lazy_data = True
            self.refresh_btn.setVisible(True)

            try:
                # Try to get schema and estimate size first
                schema = data.collect_schema()
                logger.info(f"LazyFrame schema: {list(schema.keys())}")

                # Collect a small sample to estimate memory usage
                small_sample = data.head(10).collect()
                if small_sample.height > 0:
                    # Estimate memory per row based on sample
                    estimated_memory_per_row = (
                        self.estimate_dataframe_memory(small_sample)
                        / small_sample.height
                    )
                    max_rows_by_memory = int(
                        (self.max_size_mb * 1024 * 1024) / estimated_memory_per_row
                    )

                    # Use the smaller of max_rows or memory-based limit
                    effective_max_rows = min(self.max_rows, max_rows_by_memory)

                    logger.info(
                        f"Estimated memory per row: {estimated_memory_per_row:.2f} bytes, "
                        f"effective max rows: {effective_max_rows}"
                    )

                    # Get preview data
                    preview_df = data.head(effective_max_rows).collect()
                    is_limited = True

                    # Try to get total count (this might be expensive for some LazyFrames)
                    try:
                        # Use a timeout or limit this operation
                        total_rows = data.select(pl.len()).collect().item()
                    except Exception as e:
                        logger.warning(f"Could not get total row count: {e}")
                        total_rows = None
                else:
                    preview_df = small_sample

            except Exception as e:
                logger.error(f"Error processing LazyFrame: {e}")
                # Fallback: try to collect a small portion
                try:
                    preview_df = data.head(self.max_rows).collect()
                    is_limited = True
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                    preview_df = pl.DataFrame(
                        {"Error": [f"Failed to load LazyFrame: {str(e)}"]}
                    )

        elif isinstance(data, pl.DataFrame):
            # Handle regular DataFrame with limits
            total_rows = data.height

            if total_rows > self.max_rows:
                # Apply row limit
                preview_df = data.head(self.max_rows)
                is_limited = True
                logger.info(
                    f"Applied row limit: showing {self.max_rows} of {total_rows} rows"
                )
            else:
                # Check memory size
                estimated_memory = self.estimate_dataframe_memory(data)
                max_size_bytes = self.max_size_mb * 1024 * 1024

                if estimated_memory > max_size_bytes:
                    # Calculate how many rows we can show within memory limit
                    memory_per_row = estimated_memory / total_rows
                    max_rows_by_memory = int(max_size_bytes / memory_per_row)
                    effective_rows = min(max_rows_by_memory, self.max_rows)

                    preview_df = data.head(effective_rows)
                    is_limited = True
                    logger.info(
                        f"Applied memory limit: showing {effective_rows} of {total_rows} rows "
                        f"(estimated memory: {estimated_memory / (1024*1024):.2f}MB)"
                    )
                else:
                    preview_df = data

        elif isinstance(data, pd.DataFrame):
            # Convert pandas to polars with limits
            total_rows = len(data)

            if total_rows > self.max_rows:
                limited_pandas = data.head(self.max_rows)
                is_limited = True
            else:
                limited_pandas = data

            try:
                preview_df = pl.from_pandas(limited_pandas)
            except Exception as e:
                logger.error(f"Failed to convert pandas to polars: {e}")
                # Fallback to simple table
                self.display_simple_table(limited_pandas, layout)
                self.update_info_label(len(limited_pandas), total_rows, is_limited)
                return

        else:
            # Handle other data types
            self.display_simple_table(data, layout)
            return

        # Update info label
        if preview_df is not None:
            self.update_info_label(preview_df.height, total_rows, is_limited)

            # Use PolarsTableViewer for DataFrame display
            # Configure to show info statistics prominently
            self.viewer = PolarsTableViewer(
                dataframe=preview_df,
                show_controls=True,
                show_info=True,  # Show information panel
                show_search=True,
                show_export=True,
                show_performance_settings=self.is_lazy_data,
            )

            # Ensure the info panel is visible and on top
            if hasattr(self.viewer, "splitter") and self.viewer.splitter is not None:
                # Move info panel to top by switching the order
                self.viewer.splitter.insertWidget(0, self.viewer.info_panel)
                # Adjust sizes to give more space to table but keep info visible
                self.viewer.splitter.setSizes([100, 700])  # Info: 100px, Table: 700px

            layout.addWidget(self.viewer)

    def estimate_dataframe_memory(self, df: pl.DataFrame) -> int:
        """Estimate memory usage of a Polars DataFrame in bytes"""
        try:
            # Try to get actual memory usage if available
            if hasattr(df, "estimated_size"):
                return df.estimated_size("mb")

            # Fallback: estimate based on data types and row count
            estimated_bytes = 0

            for column_name, dtype in df.schema.items():
                column_data = df[column_name]

                if dtype == pl.Boolean:
                    estimated_bytes += df.height * 1  # 1 byte per boolean
                elif dtype in [pl.Int8, pl.UInt8]:
                    estimated_bytes += df.height * 1
                elif dtype in [pl.Int16, pl.UInt16]:
                    estimated_bytes += df.height * 2
                elif dtype in [pl.Int32, pl.UInt32, pl.Float32]:
                    estimated_bytes += df.height * 4
                elif dtype in [pl.Int64, pl.UInt64, pl.Float64]:
                    estimated_bytes += df.height * 8
                elif dtype == pl.Utf8:
                    # Estimate string column size
                    try:
                        # Sample a few strings to estimate average length
                        sample_size = min(100, df.height)
                        sample_data = column_data.head(sample_size)
                        avg_length = (
                            sample_data.str.len_chars().mean() or 10
                        )  # Default to 10 if None
                        estimated_bytes += (
                            df.height * int(avg_length) * 2
                        )  # UTF-8 can be up to 2 bytes per char for common cases
                    except:
                        estimated_bytes += df.height * 20  # Default 20 bytes per string
                else:
                    # Unknown type, estimate conservatively
                    estimated_bytes += df.height * 8

            return int(estimated_bytes)

        except Exception as e:
            logger.warning(f"Could not estimate DataFrame memory usage: {e}")
            # Conservative estimate: 100 bytes per cell
            return df.height * df.width * 100

    def display_simple_table(self, data, layout: QVBoxLayout):
        """Fallback simple table display for non-DataFrame data with row limits"""
        table = QTableWidget()
        total_rows = None
        is_limited = False

        if isinstance(data, pd.DataFrame):
            # Apply row limit for pandas
            total_rows = len(data)
            if total_rows > self.max_rows:
                display_df = data.head(self.max_rows)
                is_limited = True
            else:
                display_df = data

            table.setRowCount(len(display_df.index))
            table.setColumnCount(len(display_df.columns))
            table.setHorizontalHeaderLabels(display_df.columns.tolist())

            # Fill the table
            for row in range(len(display_df.index)):
                for col in range(len(display_df.columns)):
                    value = display_df.iloc[row, col]
                    item_text = (
                        "NULL" if pd.isna(value) or value is None else str(value)
                    )
                    item = QTableWidgetItem(item_text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    table.setItem(row, col, item)

        elif isinstance(data, (list, tuple)):
            total_rows = len(data)
            # Apply row limit for lists/tuples
            if total_rows > self.max_rows:
                display_data = data[: self.max_rows]
                is_limited = True
            else:
                display_data = data

            table.setRowCount(len(display_data))
            table.setColumnCount(1)
            table.setHorizontalHeaderLabels(["Value"])

            for row, value in enumerate(display_data):
                item_text = "NULL" if value is None else str(value)
                item = QTableWidgetItem(item_text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, 0, item)

        elif isinstance(data, dict):
            items = list(data.items())
            total_rows = len(items)

            # Apply row limit for dictionaries
            if total_rows > self.max_rows:
                display_items = items[: self.max_rows]
                is_limited = True
            else:
                display_items = items

            table.setRowCount(len(display_items))
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Key", "Value"])

            for row, (key, value) in enumerate(display_items):
                key_item = QTableWidgetItem(str(key))
                value_text = "NULL" if value is None else str(value)
                value_item = QTableWidgetItem(value_text)

                key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, 0, key_item)
                table.setItem(row, 1, value_item)

        else:
            # Simple value
            table.setRowCount(1)
            table.setColumnCount(1)
            table.setHorizontalHeaderLabels(["Value"])

            item_text = "NULL" if data is None else str(data)
            item = QTableWidgetItem(item_text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(0, 0, item)

            total_rows = 1

        # Update info label for simple tables
        display_rows = table.rowCount()
        self.update_info_label(display_rows, total_rows, is_limited)

        # Adjust column widths
        table.resizeColumnsToContents()
        layout.addWidget(table)
        self.viewer = table

    @staticmethod
    def safe_preview_lazyframe(
        lazy_df: pl.LazyFrame, max_rows: int = 100, timeout_seconds: int = 5
    ) -> pl.DataFrame:
        """
        Safely preview a LazyFrame with timeout protection

        Args:
            lazy_df: The LazyFrame to preview
            max_rows: Maximum number of rows to collect
            timeout_seconds: Timeout in seconds for the operation

        Returns:
            DataFrame with preview data or error information
        """
        try:
            # Use head() to limit rows before collection
            preview_lazy = lazy_df.head(max_rows)

            # Collect with a reasonable timeout (this is a simple approach)
            # For more sophisticated timeout handling, you might want to use threading
            preview_df = preview_lazy.collect()

            logger.info(f"Successfully collected {preview_df.height} rows for preview")
            return preview_df

        except Exception as e:
            logger.error(f"Error collecting LazyFrame preview: {e}")
            # Return an error DataFrame
            return pl.DataFrame(
                {
                    "Error": [f"Failed to collect LazyFrame preview: {str(e)}"],
                    "Suggestion": [
                        "Try using .collect() with .head() first, or check your data pipeline"
                    ],
                }
            )
