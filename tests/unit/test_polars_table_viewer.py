"""
Comprehensive test suite for the Polars Table Viewer

This module contains test cases for validating the memory-efficient Polars table viewer
including performance, memory usage, data integrity, and edge cases.
"""

import unittest
import polars as pl
import numpy as np
import psutil
import time
from datetime import datetime, date
from typing import List, Dict, Any
import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

try:
    from trigger_designer.qt.models.polars_table_viewer import (
        PolarsTableModel,
        PolarsTableViewer,
    )
    from trigger_designer.qt.models.enhanced_data_preview_window import (
        EnhancedDataPreviewWindow,
    )
    from qtpy.QtWidgets import QApplication
    from qtpy.QtCore import QModelIndex, Qt
    from qtpy.QtGui import QKeySequence, QShortcut
except ImportError as e:
    print(f"Import error: {e}")
    print("Skipping Qt-dependent tests")


class TestPolarsTableViewerShortcuts(unittest.TestCase):
    """Regression checks for viewer shortcut scoping."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_copy_shortcut_is_scoped_to_table_widget(self):
        viewer = PolarsTableViewer(
            dataframe=pl.DataFrame({"id": [1]}),
            show_controls=False,
            show_info=False,
            show_search=False,
            show_export=False,
            show_performance_settings=False,
        )

        copy_shortcuts = [
            shortcut
            for shortcut in viewer.table_view.findChildren(QShortcut)
            if shortcut.key() == QKeySequence.Copy
        ]

        self.assertTrue(copy_shortcuts)
        self.assertTrue(
            all(shortcut.context() == Qt.ShortcutContext.WidgetShortcut for shortcut in copy_shortcuts)
        )

        viewer.close()


class TestPolarsTableModel(unittest.TestCase):
    """Test cases for the PolarsTableModel."""

    def setUp(self):
        """Set up test fixtures."""
        # Create sample data
        self.small_df = pl.DataFrame(
            {
                "id": [1, 2, 3, 4, 5],
                "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
                "age": [25, 30, 35, 28, 32],
                "salary": [50000.0, 60000.0, 70000.0, 55000.0, 65000.0],
                "is_active": [True, True, False, True, True],
                "join_date": [
                    date(2020, 1, 1),
                    date(2019, 6, 15),
                    date(2021, 3, 10),
                    date(2020, 8, 22),
                    date(2018, 12, 5),
                ],
            }
        )

        # Larger dataset for performance testing
        self.large_df = self._create_large_dataset(10000)

        # Dataset with null values
        self.null_df = pl.DataFrame(
            {
                "col_a": [1, None, 3, None, 5],
                "col_b": ["a", "b", None, "d", None],
                "col_c": [1.1, 2.2, 3.3, None, 5.5],
            }
        )

    def _create_large_dataset(self, rows: int) -> pl.DataFrame:
        """Create a large dataset for testing."""
        np.random.seed(42)
        return pl.DataFrame(
            {
                "id": range(rows),
                "value": np.random.random(rows),
                "category": np.random.choice(["A", "B", "C", "D"], rows),
                "timestamp": [datetime.now() for _ in range(rows)],
            }
        )

    def test_model_initialization(self):
        """Test model initialization with different datasets."""
        # Empty model
        model = PolarsTableModel()
        self.assertEqual(model.rowCount(), 0)
        self.assertEqual(model.columnCount(), 0)

        # Model with data
        model = PolarsTableModel(self.small_df)
        self.assertEqual(model.rowCount(), 5)
        self.assertEqual(model.columnCount(), 6)

    def test_data_access(self):
        """Test data access through the model."""
        model = PolarsTableModel(self.small_df, chunk_size=3)

        # Test valid indices
        index = model.createIndex(0, 0)
        data = model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "1")

        index = model.createIndex(1, 1)
        data = model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "Bob")

        # Test invalid indices
        index = model.createIndex(10, 0)
        data = model.data(index, Qt.DisplayRole)
        self.assertIsNone(data)

    def test_header_data(self):
        """Test header data retrieval."""
        model = PolarsTableModel(self.small_df)

        # Column headers
        header = model.headerData(0, Qt.Horizontal, Qt.DisplayRole)
        self.assertIn("id", header)

        header = model.headerData(1, Qt.Horizontal, Qt.DisplayRole)
        self.assertIn("name", header)

        # Row headers
        header = model.headerData(0, Qt.Vertical, Qt.DisplayRole)
        self.assertEqual(header, "1")

    def test_chunk_loading(self):
        """Test chunk-based data loading."""
        model = PolarsTableModel(self.large_df, chunk_size=1000)

        # Access data from different chunks
        index1 = model.createIndex(500, 0)  # First chunk
        data1 = model.data(index1, Qt.DisplayRole)
        self.assertIsNotNone(data1)

        index2 = model.createIndex(1500, 0)  # Second chunk
        data2 = model.data(index2, Qt.DisplayRole)
        self.assertIsNotNone(data2)

        # Verify cache contains expected chunks
        self.assertGreater(len(model._data_cache), 0)

    def test_null_handling(self):
        """Test handling of null values."""
        model = PolarsTableModel(self.null_df)

        # Test null values are displayed as "NULL"
        index = model.createIndex(1, 0)  # null in col_a
        data = model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "NULL")

        index = model.createIndex(2, 1)  # null in col_b
        data = model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "NULL")

    def test_data_formatting(self):
        """Test data type-specific formatting."""
        model = PolarsTableModel(self.small_df)

        # Test float formatting
        index = model.createIndex(0, 3)  # salary column
        data = model.data(index, Qt.DisplayRole)
        self.assertIn("50000", data)

        # Test boolean formatting
        index = model.createIndex(0, 4)  # is_active column
        data = model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "True")

        # Test date formatting
        index = model.createIndex(0, 5)  # join_date column
        data = model.data(index, Qt.DisplayRole)
        self.assertIn("2020-01-01", data)

    def test_memory_management(self):
        """Test memory management and cache behavior."""
        model = PolarsTableModel(self.large_df, chunk_size=1000, cache_size=2000)

        # Access many different chunks to test cache cleanup
        for i in range(0, 5000, 1000):
            index = model.createIndex(i, 0)
            model.data(index, Qt.DisplayRole)

        # Verify cache doesn't grow indefinitely
        cache_chunks = len(model._data_cache)
        # Should not exceed reasonable size
        self.assertLessEqual(cache_chunks, 5)

        # Test memory usage tracking
        memory_stats = model.get_memory_usage()
        self.assertIsInstance(memory_stats, dict)
        self.assertIn("cache_size_mb", memory_stats)
        self.assertIn("cached_chunks", memory_stats)

    def test_dataframe_update(self):
        """Test updating the dataframe."""
        model = PolarsTableModel(self.small_df)

        # Initial state
        self.assertEqual(model.rowCount(), 5)

        # Update with new dataframe
        new_df = pl.DataFrame({"x": [1, 2], "y": [3, 4]})
        model.set_dataframe(new_df)

        # Verify update
        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.columnCount(), 2)

        # Verify cache is cleared
        self.assertEqual(len(model._data_cache), 0)


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmark tests."""

    def setUp(self):
        """Set up performance test fixtures."""
        self.benchmark_sizes = [1000, 10000, 100000]
        self.results: Dict[str, List[float]] = {}

    def _benchmark_operation(
        self, operation_name: str, operation_func, *args, **kwargs
    ):
        """Benchmark an operation and record results."""
        start_time = time.time()
        result = operation_func(*args, **kwargs)
        end_time = time.time()

        execution_time = end_time - start_time

        if operation_name not in self.results:
            self.results[operation_name] = []
        self.results[operation_name].append(execution_time)

        return result, execution_time

    def test_dataframe_creation_performance(self):
        """Benchmark dataframe creation with different sizes."""
        for size in self.benchmark_sizes:
            df, exec_time = self._benchmark_operation(
                f"create_df_{size}", self._create_benchmark_dataframe, size
            )

            print(f"Created {size:,} row dataframe in {exec_time:.3f}s")
            # Should complete within 10 seconds
            self.assertLess(exec_time, 10.0)

    def test_model_initialization_performance(self):
        """Benchmark model initialization with different sizes."""
        for size in self.benchmark_sizes:
            df = self._create_benchmark_dataframe(size)

            model, exec_time = self._benchmark_operation(
                f"init_model_{size}", PolarsTableModel, df, 1000, 5000
            )

            print(f"Initialized model with {size:,} rows in {exec_time:.3f}s")
            self.assertLess(exec_time, 5.0)  # Should complete within 5 seconds

    def test_data_access_performance(self):
        """Benchmark data access patterns."""
        df = self._create_benchmark_dataframe(50000)
        model = PolarsTableModel(df, chunk_size=1000)

        # Sequential access
        def sequential_access():
            for i in range(0, 1000, 10):
                index = model.createIndex(i, 0)
                model.data(index, Qt.DisplayRole)

        _, exec_time = self._benchmark_operation("sequential_access", sequential_access)

        print(f"Sequential access (100 items) in {exec_time:.3f}s")
        self.assertLess(exec_time, 1.0)

        # Random access
        def random_access():
            indices = np.random.randint(0, 50000, 100)
            for i in indices:
                index = model.createIndex(i, 0)
                model.data(index, Qt.DisplayRole)

        _, exec_time = self._benchmark_operation("random_access", random_access)

        print(f"Random access (100 items) in {exec_time:.3f}s")
        self.assertLess(exec_time, 2.0)

    def _create_benchmark_dataframe(self, rows: int) -> pl.DataFrame:
        """Create a benchmark dataframe."""
        np.random.seed(42)
        return pl.DataFrame(
            {
                "id": range(rows),
                "value1": np.random.random(rows),
                "value2": np.random.random(rows),
                "category": np.random.choice(["A", "B", "C"], rows),
                "text": [f"Item_{i}" for i in range(rows)],
            }
        )


class TestMemoryUsage(unittest.TestCase):
    """Memory usage tests."""

    def setUp(self):
        """Set up memory test fixtures."""
        self.process = psutil.Process()

    def test_memory_efficiency(self):
        """Test memory efficiency with large datasets."""
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        # Create large dataset
        large_df = pl.DataFrame(
            {
                "id": range(100000),
                "value": np.random.random(100000),
                "text": [f"Text_{i}" * 10 for i in range(100000)],  # Large strings
            }
        )

        after_df_memory = self.process.memory_info().rss / 1024 / 1024

        # Create model
        model = PolarsTableModel(large_df, chunk_size=1000, cache_size=5000)

        # Access some data to populate cache
        for i in range(0, 10000, 1000):
            index = model.createIndex(i, 0)
            model.data(index, Qt.DisplayRole)

        after_model_memory = self.process.memory_info().rss / 1024 / 1024

        # Log memory usage
        df_memory_increase = after_df_memory - initial_memory
        model_memory_increase = after_model_memory - after_df_memory

        print(f"Memory usage:")
        print(f"  Initial: {initial_memory:.1f} MB")
        print(
            f"  After DataFrame: {after_df_memory:.1f} MB (+{df_memory_increase:.1f} MB)"
        )
        print(
            f"  After Model: {after_model_memory:.1f} MB (+{model_memory_increase:.1f} MB)"
        )

        # Model should not add significant memory overhead
        # Less than 10% overhead
        self.assertLess(model_memory_increase, df_memory_increase * 0.1)

    def test_cache_memory_limits(self):
        """Test that cache respects memory limits."""
        df = pl.DataFrame(
            {
                "id": range(50000),
                "data": [f"Large text data {i}" * 100 for i in range(50000)],
            }
        )

        model = PolarsTableModel(df, chunk_size=1000, cache_size=3000)

        # Access many chunks
        for i in range(0, 30000, 1000):
            index = model.createIndex(i, 0)
            model.data(index, Qt.DisplayRole)

        # Cache should not exceed reasonable size
        cached_chunks = len(model._data_cache)
        self.assertLessEqual(cached_chunks, 10)  # Should cleanup automatically

        # Get memory statistics
        memory_stats = model.get_memory_usage()
        cache_mb = memory_stats["cache_size_mb"]

        print(f"Cache usage: {cache_mb:.1f} MB with {cached_chunks} chunks")
        self.assertLess(cache_mb, 100)  # Should stay under 100 MB


class TestEdgeCases(unittest.TestCase):
    """Edge case tests."""

    def test_empty_dataframe(self):
        """Test handling of empty dataframes."""
        empty_df = pl.DataFrame()
        model = PolarsTableModel(empty_df)

        self.assertEqual(model.rowCount(), 0)
        self.assertEqual(model.columnCount(), 0)

        # Accessing data should not crash
        index = model.createIndex(0, 0)
        data = model.data(index, Qt.DisplayRole)
        self.assertIsNone(data)

    def test_single_row_dataframe(self):
        """Test handling of single-row dataframes."""
        single_df = pl.DataFrame({"a": [1], "b": ["test"]})
        model = PolarsTableModel(single_df)

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.columnCount(), 2)

        index = model.createIndex(0, 0)
        data = model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "1")

    def test_single_column_dataframe(self):
        """Test handling of single-column dataframes."""
        single_col_df = pl.DataFrame({"only_col": [1, 2, 3, 4, 5]})
        model = PolarsTableModel(single_col_df)

        self.assertEqual(model.rowCount(), 5)
        self.assertEqual(model.columnCount(), 1)

        index = model.createIndex(2, 0)
        data = model.data(index, Qt.DisplayRole)
        self.assertEqual(data, "3")

    def test_all_null_column(self):
        """Test handling of columns with all null values."""
        null_df = pl.DataFrame(
            {"all_nulls": [None, None, None], "some_data": [1, 2, 3]}
        )
        model = PolarsTableModel(null_df)

        # All values in first column should be "NULL"
        for i in range(3):
            index = model.createIndex(i, 0)
            data = model.data(index, Qt.DisplayRole)
            self.assertEqual(data, "NULL")

    def test_extreme_chunk_sizes(self):
        """Test with extreme chunk sizes."""
        df = pl.DataFrame({"x": range(1000)})

        # Very small chunks
        model1 = PolarsTableModel(df, chunk_size=1)
        index = model1.createIndex(500, 0)
        data = model1.data(index, Qt.DisplayRole)
        self.assertEqual(data, "500")

        # Very large chunks
        model2 = PolarsTableModel(df, chunk_size=10000)
        index = model2.createIndex(500, 0)
        data = model2.data(index, Qt.DisplayRole)
        self.assertEqual(data, "500")

    def test_mixed_data_types(self):
        """Test with mixed and unusual data types."""
        mixed_df = pl.DataFrame(
            {
                "integers": [1, 2, 3],
                "floats": [1.1, 2.2, 3.3],
                "strings": ["a", "b", "c"],
                "booleans": [True, False, True],
                "dates": [date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)],
                "mixed_nulls": [1, None, "text"],
            }
        )

        model = PolarsTableModel(mixed_df)

        # Test each column type
        for col in range(model.columnCount()):
            for row in range(model.rowCount()):
                index = model.createIndex(row, col)
                data = model.data(index, Qt.DisplayRole)
                self.assertIsNotNone(data)  # Should always return something


def run_performance_report():
    """Generate a comprehensive performance report."""
    print("\n" + "=" * 80)
    print("POLARS TABLE VIEWER - PERFORMANCE REPORT")
    print("=" * 80)

    # Run performance benchmarks
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPerformanceBenchmarks)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Run memory tests
    print("\n" + "-" * 80)
    print("MEMORY USAGE TESTS")
    print("-" * 80)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestMemoryUsage)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print("PERFORMANCE REPORT COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test the Polars Table Viewer")
    parser.add_argument(
        "--performance", action="store_true", help="Run performance benchmarks"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all tests including performance"
    )

    args = parser.parse_args()

    if args.performance:
        run_performance_report()
    elif args.all:
        # Run all tests
        unittest.main(verbosity=2)
        run_performance_report()
    else:
        # Run basic tests
        suite = unittest.TestSuite()
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestPolarsTableModel))
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestEdgeCases))

        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
