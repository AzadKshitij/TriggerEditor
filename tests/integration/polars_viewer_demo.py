#!/usr/bin/env python
"""
Polars Table Viewer Demo

This script demonstrates the usage of the memory-efficient Polars table viewer
with various types of datasets to showcase its performance and features.
"""

import sys
import polars as pl
import numpy as np
from datetime import datetime, timedelta
from qtpy.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
)
from qtpy.QtCore import QTimer
import random
import string

# Add the src directory to the path to import our custom widgets
sys.path.append(r"c:\Users\KASHVINCHANDRASAN\Desktop\Personal\Github\TriggerEditor\src")

try:
    from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer
    from trigger_designer.qt.models.enhanced_data_preview_window import (
        EnhancedDataPreviewWindow,
        preview_data,
    )
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the correct directory")
    sys.exit(1)


def generate_sample_data(rows: int = 10000, include_nulls: bool = True) -> pl.DataFrame:
    """
    Generate sample data for testing the table viewer.

    Args:
        rows: Number of rows to generate
        include_nulls: Whether to include null values

    Returns:
        Generated Polars DataFrame
    """
    print(f"Generating sample data with {rows:,} rows...")

    # Generate random data
    np.random.seed(42)  # For reproducible results

    # Different data types
    data = {
        # Integer columns
        "id": range(1, rows + 1),
        "category_id": np.random.randint(1, 100, rows),
        "age": np.random.randint(18, 80, rows),
        # Float columns
        "price": np.round(np.random.uniform(10.0, 1000.0, rows), 2),
        "rating": np.round(np.random.uniform(1.0, 5.0, rows), 1),
        "discount": np.round(np.random.uniform(0.0, 0.5, rows), 3),
        # String columns
        "name": [
            "".join(random.choices(string.ascii_letters, k=random.randint(5, 15)))
            for _ in range(rows)
        ],
        "description": [
            "Description for item "
            + str(i)
            + " with random text: "
            + "".join(
                random.choices(string.ascii_letters + " ", k=random.randint(20, 100))
            )
            for i in range(rows)
        ],
        "category": np.random.choice(
            ["Electronics", "Clothing", "Books", "Sports", "Home"], rows
        ),
        # Boolean column
        "is_active": np.random.choice([True, False], rows, p=[0.8, 0.2]),
        # Date columns
        "created_date": [
            datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1400))
            for _ in range(rows)
        ],
        "updated_date": [
            datetime(2023, 1, 1) + timedelta(days=random.randint(0, 365))
            for _ in range(rows)
        ],
    }

    # Create DataFrame
    df = pl.DataFrame(data)

    # Add some null values if requested
    if include_nulls:
        # Randomly set some values to null in certain columns
        null_mask_price = np.random.random(rows) < 0.05  # 5% nulls
        null_mask_rating = np.random.random(rows) < 0.1  # 10% nulls
        null_mask_description = np.random.random(rows) < 0.02  # 2% nulls

        df = df.with_columns(
            [
                pl.when(null_mask_price)
                .then(None)
                .otherwise(pl.col("price"))
                .alias("price"),
                pl.when(null_mask_rating)
                .then(None)
                .otherwise(pl.col("rating"))
                .alias("rating"),
                pl.when(null_mask_description)
                .then(None)
                .otherwise(pl.col("description"))
                .alias("description"),
            ]
        )

    print(f"Generated DataFrame with shape: {df.shape}")
    return df


class PolarsViewerDemo(QMainWindow):
    """Demo application for the Polars table viewer."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Polars Table Viewer Demo")
        self.setGeometry(100, 100, 1400, 900)

        # Current dataset
        self.current_df = None

        self._init_ui()

        # Load initial small dataset
        self._load_small_dataset()

    def _init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Control panel
        control_layout = QHBoxLayout()

        # Dataset generation buttons
        control_layout.addWidget(QLabel("Generate Dataset:"))

        self.small_btn = QPushButton("Small (1K rows)")
        self.small_btn.clicked.connect(self._load_small_dataset)
        control_layout.addWidget(self.small_btn)

        self.medium_btn = QPushButton("Medium (10K rows)")
        self.medium_btn.clicked.connect(self._load_medium_dataset)
        control_layout.addWidget(self.medium_btn)

        self.large_btn = QPushButton("Large (100K rows)")
        self.large_btn.clicked.connect(self._load_large_dataset)
        control_layout.addWidget(self.large_btn)

        self.huge_btn = QPushButton("Huge (1M rows)")
        self.huge_btn.clicked.connect(self._load_huge_dataset)
        control_layout.addWidget(self.huge_btn)

        control_layout.addStretch()

        # Demo buttons
        self.preview_window_btn = QPushButton("Open Preview Window")
        self.preview_window_btn.clicked.connect(self._open_preview_window)
        control_layout.addWidget(self.preview_window_btn)

        self.memory_test_btn = QPushButton("Memory Stress Test")
        self.memory_test_btn.clicked.connect(self._run_memory_test)
        control_layout.addWidget(self.memory_test_btn)

        layout.addLayout(control_layout)

        # Status bar
        self.status_label = QLabel("Ready - Load a dataset to begin")
        layout.addWidget(self.status_label)

        # Main table viewer
        self.table_viewer = PolarsTableViewer()
        layout.addWidget(self.table_viewer)

        # Connect signals
        self.table_viewer.memoryWarning.connect(self._on_memory_warning)

    def _load_small_dataset(self):
        """Load a small dataset (1K rows)."""
        self.status_label.setText("Generating small dataset (1K rows)...")
        QApplication.processEvents()  # Update UI

        self.current_df = generate_sample_data(1000)
        self.table_viewer.set_dataframe(self.current_df)
        self.status_label.setText("Small dataset loaded - 1,000 rows")

    def _load_medium_dataset(self):
        """Load a medium dataset (10K rows)."""
        self.status_label.setText("Generating medium dataset (10K rows)...")
        QApplication.processEvents()

        self.current_df = generate_sample_data(10000)
        self.table_viewer.set_dataframe(self.current_df)
        self.status_label.setText("Medium dataset loaded - 10,000 rows")

    def _load_large_dataset(self):
        """Load a large dataset (100K rows)."""
        self.status_label.setText("Generating large dataset (100K rows)...")
        QApplication.processEvents()

        self.current_df = generate_sample_data(100000)
        self.table_viewer.set_dataframe(self.current_df)
        self.status_label.setText("Large dataset loaded - 100,000 rows")

    def _load_huge_dataset(self):
        """Load a huge dataset (1M rows)."""
        self.status_label.setText(
            "Generating huge dataset (1M rows) - This may take a moment..."
        )
        QApplication.processEvents()

        self.current_df = generate_sample_data(1000000)
        self.table_viewer.set_dataframe(self.current_df)
        self.status_label.setText("Huge dataset loaded - 1,000,000 rows")

    def _open_preview_window(self):
        """Open the enhanced preview window."""
        if self.current_df is None:
            self.status_label.setText("Please load a dataset first")
            return

        # Demonstrate different ways to use the preview window

        # Method 1: Using the convenience function
        preview_window = preview_data(self.current_df, "Polars DataFrame Preview")

        # Method 2: Direct instantiation (commented out to avoid multiple windows)
        # preview_window = EnhancedDataPreviewWindow(
        #     self.current_df,
        #     "Enhanced Data Preview",
        #     parent=self
        # )
        # preview_window.show()

        self.status_label.setText("Preview window opened")

    def _run_memory_test(self):
        """Run a memory stress test."""
        if self.current_df is None:
            self.status_label.setText("Please load a dataset first")
            return

        self.status_label.setText("Running memory stress test...")
        QApplication.processEvents()

        # Simulate rapid scrolling and filtering
        test_timer = QTimer(self)
        test_count = 0

        def run_test():
            nonlocal test_count
            test_count += 1

            if test_count <= 10:
                # Apply random filters
                search_terms = ["Electronics", "test", "100", "item", "description"]
                search_term = random.choice(search_terms)

                self.table_viewer.search_input.setText(search_term)
                self.table_viewer._apply_filter()

                # Update status
                self.status_label.setText(
                    f"Memory test - Step {test_count}/10 - Filter: '{search_term}'"
                )

            else:
                # Test complete
                test_timer.stop()
                self.table_viewer._clear_filter()
                self.status_label.setText("Memory stress test completed")

        test_timer.timeout.connect(run_test)
        test_timer.start(1000)  # Run test every second

    def _on_memory_warning(self, memory_mb: float):
        """Handle memory warnings."""
        self.status_label.setText(
            f"⚠️ Memory Warning: {memory_mb:.0f} MB - Consider optimization"
        )


def main():
    """Main application entry point."""
    print("Starting Polars Table Viewer Demo...")

    app = QApplication(sys.argv)

    # Create and show demo window
    demo_window = PolarsViewerDemo()
    demo_window.show()

    print("Demo application started. Try the following features:")
    print("1. Generate datasets of different sizes")
    print("2. Use search and filtering")
    print("3. Adjust performance settings")
    print("4. Monitor memory usage")
    print("5. Export data")
    print("6. Open the enhanced preview window")

    # Start the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
