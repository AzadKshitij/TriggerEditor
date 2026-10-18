"""Model-level behaviour of the Polars table viewer.

Paging, the chunk cache, sorting and cell formatting all live on
``PolarsTableModel``; the widget-level counterparts are in
``tests/ui/test_polars_table_viewer.py``.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime

import numpy as np
import polars as pl
from qtpy.QtCore import Qt

from trigger_designer.qt.models.polars_table_viewer import PolarsTableModel


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
                # Naive timestamps mirror what a CSV scan produces.
                "timestamp": [datetime(2026, 1, 1) for _ in range(rows)],  # noqa: DTZ001
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


class TestPagingAndSorting(unittest.TestCase):
    """Paging and model-level sorting behaviour."""

    def _model(self, rows: int = 600, page_size: int = 250) -> PolarsTableModel:
        df = pl.DataFrame(
            {"id": range(rows), "label": [f"row_{i}" for i in range(rows)]}
        )
        model = PolarsTableModel(df)
        model.set_page_size(page_size)
        return model

    def test_page_slice_boundaries(self):
        model = self._model()  # 600 rows, 250 per page
        self.assertEqual(model.page_count, 3)
        self.assertEqual(model.page_offset, 0)
        self.assertEqual(model.rowCount(), 250)

        model.set_page(1)
        self.assertEqual(model.page_offset, 250)
        self.assertEqual(model.rowCount(), 250)

        model.set_page(2)
        self.assertEqual(model.page_offset, 500)
        self.assertEqual(model.rowCount(), 100)  # short last page

    def test_page_index_is_clamped(self):
        model = self._model()
        model.set_page(99)
        self.assertEqual(model.page_index, 2)

        model.set_page(-5)
        self.assertEqual(model.page_index, 0)

    def test_page_count_for_empty_and_short_frames(self):
        self.assertEqual(PolarsTableModel().page_count, 1)
        self.assertEqual(PolarsTableModel().rowCount(), 0)

        short = PolarsTableModel(pl.DataFrame({"a": [1, 2]}))
        self.assertEqual(short.page_count, 1)
        self.assertEqual(short.rowCount(), 2)

    def test_data_maps_view_rows_to_absolute_rows(self):
        model = self._model()
        self.assertEqual(model.data(model.createIndex(0, 0), Qt.DisplayRole), "0")

        model.set_page(2)  # rows 500..599
        self.assertEqual(model.data(model.createIndex(0, 0), Qt.DisplayRole), "500")
        self.assertEqual(model.data(model.createIndex(99, 0), Qt.DisplayRole), "599")
        # Past the last real row of the frame -> nothing to show
        self.assertIsNone(model.data(model.createIndex(100, 0), Qt.DisplayRole))

    def test_chunk_cache_uses_absolute_offsets(self):
        df = pl.DataFrame({"id": range(600)})
        model = PolarsTableModel(df, chunk_size=100)
        model.set_page(1)  # view row 0 is absolute row 250
        model.data(model.createIndex(0, 0), Qt.DisplayRole)
        self.assertIn(200, model._data_cache)  # chunk starting at row 200

    def test_vertical_header_numbers_are_absolute(self):
        model = self._model()
        self.assertEqual(model.headerData(0, Qt.Vertical, Qt.DisplayRole), "1")

        model.set_page(2)
        self.assertEqual(model.headerData(0, Qt.Vertical, Qt.DisplayRole), "501")

    def test_page_size_change_keeps_first_visible_row(self):
        model = self._model()
        model.set_page(2)  # offset 500
        model.set_page_size(100)
        self.assertEqual(model.page_offset, 500)

    def test_sort_ascending_and_descending(self):
        model = PolarsTableModel(pl.DataFrame({"n": [3, 1, 2]}))

        model.sort_by(0)
        self.assertEqual(model.sort_column, 0)
        self.assertFalse(model.sort_descending)
        self.assertEqual(
            [model.data(model.createIndex(r, 0), Qt.DisplayRole) for r in range(3)],
            ["1", "2", "3"],
        )

        model.sort_by(0, descending=True)
        self.assertTrue(model.sort_descending)
        self.assertEqual(
            [model.data(model.createIndex(r, 0), Qt.DisplayRole) for r in range(3)],
            ["3", "2", "1"],
        )

    def test_sort_puts_nulls_last(self):
        model = PolarsTableModel(pl.DataFrame({"n": [1, None, 2]}))

        model.sort_by(0)
        self.assertEqual(
            [model.data(model.createIndex(r, 0), Qt.DisplayRole) for r in range(3)],
            ["1", "2", "NULL"],
        )

        model.sort_by(0, descending=True)
        self.assertEqual(
            [model.data(model.createIndex(r, 0), Qt.DisplayRole) for r in range(3)],
            ["2", "1", "NULL"],
        )

    def test_sort_resets_paging_and_clears_cache(self):
        model = self._model()
        model.set_page(1)
        model.data(model.createIndex(0, 0), Qt.DisplayRole)
        self.assertTrue(model._data_cache)

        model.sort_by(0, descending=True)
        self.assertEqual(model.page_index, 0)
        self.assertEqual(model._data_cache, {})

    def test_sort_ignores_invalid_column(self):
        model = self._model(rows=3)
        model.sort_by(99)
        self.assertIsNone(model.sort_column)


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
                # A genuinely mixed column needs an explicit Object dtype;
                # Polars' inference rejects mixed values outright.
                "mixed_nulls": pl.Series(
                    "mixed_nulls", [1, None, "text"], dtype=pl.Object
                ),
            }
        )

        model = PolarsTableModel(mixed_df)

        # Test each column type
        for col in range(model.columnCount()):
            for row in range(model.rowCount()):
                index = model.createIndex(row, col)
                data = model.data(index, Qt.DisplayRole)
                self.assertIsNotNone(data)  # Should always return something
