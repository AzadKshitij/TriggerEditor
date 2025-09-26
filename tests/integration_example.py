"""
Integration example for using the new Polars table viewer in the file input node.

This module shows how to update the existing file input widget to use the memory-efficient
Polars table viewer instead of the basic QTableWidget.
"""

import os
from qtpy.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget
from qtpy.QtCore import Qt
import polars as pl
from typing import Optional
from loguru import logger

# Import the new widgets
from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer
from trigger_designer.qt.models.enhanced_data_preview_window import EnhancedDataPreviewWindow


class EnhancedFileInputContent:
    """
    Enhanced version of FileInputContent that uses the new Polars table viewer.

    This is an example of how to integrate the memory-efficient table viewer
    into existing widgets that currently use basic table widgets.
    """

    def _create_enhanced_table_widget(self) -> QWidget:
        """
        Create the enhanced table widget using PolarsTableViewer.

        This replaces the basic QTableWidget with our memory-efficient viewer.
        """
        # Create container widget
        container = QWidget()
        layout = QVBoxLayout(container)

        # Header with data info
        header_layout = QHBoxLayout()
        self.data_info_label = QLabel("No data loaded")
        header_layout.addWidget(self.data_info_label)

        header_layout.addStretch()

        # Enhanced view button
        self.enhanced_view_btn = QPushButton("Enhanced View")
        self.enhanced_view_btn.clicked.connect(self._open_enhanced_view)
        self.enhanced_view_btn.setEnabled(False)
        header_layout.addWidget(self.enhanced_view_btn)

        layout.addLayout(header_layout)

        # Create the Polars table viewer
        self.polars_table_viewer = PolarsTableViewer()

        # Configure for preview mode (smaller chunks, limited cache)
        self.polars_table_viewer.chunk_size = 500  # Smaller chunks for preview
        self.polars_table_viewer.cache_size = 2000  # Limited cache for preview

        # Connect memory warning signal
        self.polars_table_viewer.memoryWarning.connect(self._on_memory_warning)

        layout.addWidget(self.polars_table_viewer)

        return container

    def initUI(self, parent: Optional[QWidget] = None) -> None:
        """
        Modified initUI to use the enhanced table viewer.

        This replaces the original QTableWidget creation with our enhanced version.
        """
        # ... (previous code for file selection widgets)
        # Assume dock_layout exists from parent class initialization

        # Replace the basic table widget creation with enhanced version
        # OLD: self.tableWidget = QTableWidget(self)
        # NEW:
        self.table_container = self._create_enhanced_table_widget()

        # Add to layout (dock_layout would be created in parent class)
        # dock_layout.addWidget(self.table_container)

        # ... (rest of the initUI code)

    def _update_table_display(self, df: pl.DataFrame) -> None:
        """
        Update the table display with new data.

        This replaces the manual population of QTableWidget with
        our efficient DataFrame display.
        """
        if df is None or df.is_empty():
            self.data_info_label.setText("No data available")
            self.enhanced_view_btn.setEnabled(False)
            self.polars_table_viewer.set_dataframe(pl.DataFrame())
            return

        # Update the table viewer
        self.polars_table_viewer.set_dataframe(df)

        # Update info display
        rows = len(df)
        cols = len(df.columns)
        estimated_mb = (rows * cols * 8) / (1024 * 1024)

        self.data_info_label.setText(
            f"Preview: {rows:,} rows × {cols} columns (~{estimated_mb:.1f} MB)"
        )

        # Enable enhanced view button
        self.enhanced_view_btn.setEnabled(True)

    def loadFile(self, fileName: str) -> None:
        """
        Modified loadFile method to work with the enhanced table viewer.

        This loads data and displays it using the efficient viewer.
        """
        try:
            # Load preview data (limited rows for memory efficiency)
            preview_df = self._read_file_for_preview(
                fileName, self.preview_rows)

            if not preview_df.is_empty():
                # Store the preview data
                self.data = preview_df

                # Update the enhanced table display
                self._update_table_display(preview_df)

                # Update file type UI
                file_type = self._auto_detect_file_type(fileName)
                self._update_ui_visibility(file_type)

                logger.info(
                    f"File loaded for preview: {fileName} ({len(preview_df)} rows)")
            else:
                self._update_table_display(pl.DataFrame())
                logger.warning(f"Failed to load file: {fileName}")

        except Exception as e:
            logger.error(f"Error loading file {fileName}: {e}")
            self._update_table_display(pl.DataFrame())

    def _open_enhanced_view(self) -> None:
        """
        Open the enhanced data preview window for full data exploration.

        This provides a full-featured view of the data in a separate window.
        """
        if self.data is None or self.data.is_empty():
            return

        # Check if we need to load full data
        current_df = self.data

        # If current data is just preview, offer to load full data
        if len(current_df) <= self.preview_rows and self.filePath:
            # Show option to load full data
            from qtpy.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self,
                "Load Full Dataset",
                f"Current preview shows {len(current_df)} rows.\n"
                f"Would you like to load the complete dataset for analysis?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                try:
                    # Load full data
                    current_df = self._read_file_based_on_type(self.filePath)
                    if current_df.is_empty():
                        QMessageBox.warning(
                            self, "Error", "Failed to load full dataset")
                        return
                except Exception as e:
                    QMessageBox.critical(
                        self, "Error", f"Error loading full data: {str(e)}")
                    return

        # Create and show enhanced preview window
        try:
            self.enhanced_window = EnhancedDataPreviewWindow(
                current_df,
                f"File Data: {os.path.basename(self.filePath) if self.filePath else 'Unknown'}",
                parent=self
            )
            self.enhanced_window.show()

        except Exception as e:
            logger.error(f"Error opening enhanced view: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to open enhanced view: {str(e)}")

    def _on_memory_warning(self, memory_mb: float) -> None:
        """
        Handle memory warnings from the table viewer.

        This can trigger automatic optimization or user warnings.
        """
        logger.warning(f"Memory warning: {memory_mb:.1f} MB")

        # Update status to show memory warning
        current_text = self.data_info_label.text()
        if "⚠️" not in current_text:
            self.data_info_label.setText(f"{current_text} ⚠️ High Memory")

        # Optionally show user warning for very high memory usage
        if memory_mb > 1000:  # Over 1GB
            from qtpy.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "High Memory Usage",
                f"Memory usage is high ({memory_mb:.0f} MB). "
                f"Consider filtering the data or working with smaller files."
            )


def update_existing_file_input_node():
    """
    Example of how to update the existing FileInputContent class.

    This shows the key changes needed to integrate the enhanced table viewer.
    """

    # 1. Replace table widget creation
    # OLD:
    # self.tableWidget = QTableWidget(self)

    # NEW:
    # self.table_container = self._create_enhanced_table_widget()

    # 2. Replace manual table population
    # OLD:
    # def populateTable(self, data):
    #     self.tableWidget.setRowCount(len(data))
    #     self.tableWidget.setColumnCount(len(data.columns))
    #     # ... manual item setting

    # NEW:
    # def _update_table_display(self, df: pl.DataFrame):
    #     self.polars_table_viewer.set_dataframe(df)

    # 3. Update data loading
    # OLD:
    # self.data = loaded_data
    # self.populateTable(self.data)

    # NEW:
    # self.data = loaded_data
    # self._update_table_display(self.data)

    # 4. Add enhanced view capability
    # NEW:
    # self.enhanced_view_btn = QPushButton("Enhanced View")
    # self.enhanced_view_btn.clicked.connect(self._open_enhanced_view)

    pass


# Example of a complete minimal integration
class MinimalEnhancedFileWidget(QWidget):
    """
    Minimal example of a file widget using the enhanced table viewer.

    This shows the simplest way to create a file viewer with the new components.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: Optional[pl.DataFrame] = None
        self.file_path: str = ""

        self._init_ui()

    def _init_ui(self):
        """Initialize the minimal UI."""
        layout = QVBoxLayout(self)

        # File selection
        file_layout = QHBoxLayout()

        from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog

        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a file...")
        file_layout.addWidget(self.file_edit)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.browse_btn)

        layout.addLayout(file_layout)

        # Enhanced table viewer
        self.table_viewer = PolarsTableViewer()
        layout.addWidget(self.table_viewer)

    def _browse_file(self):
        """Browse for a file and load it."""
        from qtpy.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Data File",
            "",
            "Data Files (*.csv *.xlsx *.txt);;All Files (*)"
        )

        if file_path:
            self.file_path = file_path
            self.file_edit.setText(file_path)
            self._load_file()

    def _load_file(self):
        """Load and display the selected file."""
        if not self.file_path:
            return

        try:
            # Load data using Polars
            if self.file_path.endswith('.csv'):
                self.data = pl.read_csv(self.file_path)
            elif self.file_path.endswith('.xlsx'):
                self.data = pl.read_excel(self.file_path)
            elif self.file_path.endswith('.txt'):
                self.data = pl.read_csv(self.file_path, separator='\t')
            else:
                self.data = pl.read_csv(self.file_path)

            # Display in table viewer
            self.table_viewer.set_dataframe(self.data)

        except Exception as e:
            from qtpy.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Error", f"Failed to load file: {str(e)}")


if __name__ == "__main__":
    """Demo the minimal enhanced file widget."""
    import sys
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = MinimalEnhancedFileWidget()
    widget.setWindowTitle("Enhanced File Viewer Demo")
    widget.resize(1000, 600)
    widget.show()

    sys.exit(app.exec_())
