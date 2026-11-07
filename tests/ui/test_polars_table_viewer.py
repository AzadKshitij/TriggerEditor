"""Widget-level behaviour of the Polars table viewer.

Construction, header-click sorting, search and shortcut scoping. The model
itself is covered by ``tests/unit/test_polars_table_model.py``.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import polars as pl
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence, QShortcut
from qtpy.QtWidgets import QApplication, QFileDialog, QMessageBox

from trigger_designer.qt.models.polars_table_viewer import (
    ALL_COLUMNS_LABEL,
    PolarsTableModel,
    PolarsTableViewer,
)


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
        )

        copy_shortcuts = [
            shortcut
            for shortcut in viewer.table_view.findChildren(QShortcut)
            if shortcut.key() == QKeySequence.Copy
        ]

        self.assertTrue(copy_shortcuts)
        self.assertTrue(
            all(
                shortcut.context() == Qt.ShortcutContext.WidgetShortcut
                for shortcut in copy_shortcuts
            )
        )

        viewer.close()


class TestViewerSortingInteraction(unittest.TestCase):
    """Header clicks drive model-side sorting on the viewer."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_header_click_toggles_sort_direction(self):
        viewer = PolarsTableViewer(dataframe=pl.DataFrame({"n": [2, 1, 3]}))
        try:
            viewer._on_header_clicked(0)
            self.assertEqual(viewer.model.sort_column, 0)
            self.assertFalse(viewer.model.sort_descending)
            first = viewer.model.data(viewer.model.createIndex(0, 0), Qt.DisplayRole)
            self.assertEqual(first, "1")

            viewer._on_header_clicked(0)
            self.assertTrue(viewer.model.sort_descending)
            first = viewer.model.data(viewer.model.createIndex(0, 0), Qt.DisplayRole)
            self.assertEqual(first, "3")
        finally:
            viewer.close()

    def _export_csv_frame(self, viewer: PolarsTableViewer) -> pl.DataFrame:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "export.csv"
            with (
                mock.patch.object(
                    QFileDialog, "getSaveFileName", return_value=(str(target), "")
                ),
                mock.patch.object(QMessageBox, "warning") as warning,
            ):
                viewer.export_csv()
            warning.assert_not_called()
            return pl.read_csv(target)

    def test_export_follows_the_model_sort_order(self):
        viewer = PolarsTableViewer(
            dataframe=pl.DataFrame({"n": [2, 3, 1], "s": ["b", "c", "a"]})
        )
        try:
            viewer.model.sort_by(0, descending=True)
            exported = self._export_csv_frame(viewer)
            self.assertEqual(exported["n"].to_list(), [3, 2, 1])
            self.assertEqual(exported["s"].to_list(), ["c", "b", "a"])
        finally:
            viewer.close()

    def test_export_of_a_filtered_view_is_filtered_and_sorted(self):
        viewer = PolarsTableViewer(
            dataframe=pl.DataFrame(
                {
                    "n": [5, 1, 4, 2, 3],
                    "city": ["Berlin", "Paris", "Berlin", "Paris", "Berlin"],
                }
            )
        )
        try:
            viewer.apply_search("Berlin", "city")
            viewer.model.sort_by(0)
            exported = self._export_csv_frame(viewer)
            self.assertEqual(exported["n"].to_list(), [3, 4, 5])
            self.assertEqual(exported["city"].to_list(), ["Berlin"] * 3)
        finally:
            viewer.close()


class TestViewerSearchAndHeader(unittest.TestCase):
    """One-line headers, row height, and the programmatic search API."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _viewer(self, **kwargs) -> PolarsTableViewer:
        data = pl.DataFrame(
            {
                "id": [1, 2, 3],
                "name": ["Alice", "Bob", "Charlie"],
                "city": ["Berlin", "Paris", "Berlin"],
            }
        )
        viewer = PolarsTableViewer(
            dataframe=data,
            show_controls=False,
            show_info=False,
            show_search=False,
            show_export=False,
            **kwargs,
        )
        self.addCleanup(viewer.close)
        return viewer

    def test_column_header_carries_dtype_on_one_line(self):
        model = PolarsTableModel(pl.DataFrame({"id": [1], "name": ["a"]}))

        id_header = model.headerData(0, Qt.Horizontal, Qt.DisplayRole)
        self.assertEqual(id_header, "id (Int64)")
        name_header = model.headerData(1, Qt.Horizontal, Qt.DisplayRole)
        self.assertEqual(name_header, "name (String)")
        self.assertNotIn("\n", name_header)

    def test_row_height_is_a_constructor_option(self):
        viewer = self._viewer(row_height=24)
        self.assertEqual(viewer.table_view.verticalHeader().defaultSectionSize(), 24)

    def test_search_columns_lists_the_loaded_frame(self):
        self.assertEqual(self._viewer().search_columns(), ["id", "name", "city"])

    def test_apply_search_matches_string_columns(self):
        viewer = self._viewer()
        self.assertEqual(viewer.apply_search("Berlin"), 2)
        self.assertEqual(viewer.model.total_rows, 2)

    def test_apply_search_narrows_to_one_column(self):
        viewer = self._viewer()
        self.assertEqual(viewer.apply_search("Berlin", "city"), 2)
        self.assertEqual(viewer.apply_search("Berlin", "name"), 0)
        self.assertEqual(viewer.model.total_rows, 0)

    def test_apply_search_unknown_column_matches_nothing(self):
        viewer = self._viewer()
        self.assertEqual(viewer.apply_search("Berlin", "nope"), 0)

    def test_apply_search_always_filters_the_loaded_frame(self):
        viewer = self._viewer()
        self.assertEqual(viewer.apply_search("Ali"), 1)
        # The second search must see all three rows again, not the 1-row result.
        self.assertEqual(viewer.apply_search("Berlin"), 2)

    def test_empty_search_and_clear_search_restore_the_frame(self):
        viewer = self._viewer()
        viewer.apply_search("Berlin")
        self.assertEqual(viewer.apply_search("   "), 3)
        self.assertEqual(viewer.model.total_rows, 3)

        viewer.apply_search("Ali")
        viewer.clear_search()
        self.assertEqual(viewer.model.total_rows, 3)
        self.assertIsNone(viewer.filtered_dataframe)

    def test_builtin_controls_still_apply_and_clear(self):
        viewer = PolarsTableViewer(
            dataframe=pl.DataFrame({"city": ["Berlin", "Paris"]})
        )
        self.addCleanup(viewer.close)

        viewer.search_input.setText("Berlin")
        viewer._apply_filter()
        self.assertEqual(viewer.model.total_rows, 1)

        viewer._clear_filter()
        self.assertEqual(viewer.model.total_rows, 2)

    def _mixed_viewer(self) -> PolarsTableViewer:
        viewer = PolarsTableViewer(
            dataframe=pl.DataFrame(
                {
                    "id": [1001, 1002],
                    "d": [date(2024, 1, 5), date(2024, 1, 6)],
                    "s": ["x", "y"],
                    "c": pl.Series(["red", "blue"], dtype=pl.Categorical),
                }
            ),
            show_controls=False,
            show_info=False,
            show_search=False,
            show_export=False,
        )
        self.addCleanup(viewer.close)
        return viewer

    def test_zero_row_frame_lists_its_search_columns(self):
        viewer = PolarsTableViewer(
            dataframe=pl.DataFrame(schema={"a": pl.Int64, "b": pl.String}),
            show_controls=False,
            show_info=False,
            show_search=False,
            show_export=False,
        )
        self.addCleanup(viewer.close)
        self.assertEqual(viewer.search_columns(), ["a", "b"])
        self.assertEqual(viewer.model.columnCount(), 2)

    def test_column_filter_lists_columns_of_a_zero_row_frame(self):
        viewer = PolarsTableViewer(dataframe=pl.DataFrame({"n": [1]}))
        self.addCleanup(viewer.close)
        viewer.set_dataframe(pl.DataFrame(schema={"a": pl.Int64, "b": pl.String}))
        filter_items = [
            viewer.column_filter.itemText(i)
            for i in range(viewer.column_filter.count())
        ]
        self.assertEqual(filter_items, [ALL_COLUMNS_LABEL, "a", "b"])

    def test_search_with_no_matches_keeps_the_headers(self):
        viewer = self._viewer()
        self.assertEqual(viewer.apply_search("Zurich"), 0)
        self.assertEqual(viewer.model.columnCount(), 3)
        self.assertEqual(
            viewer.model.headerData(0, Qt.Horizontal, Qt.DisplayRole), "id (Int64)"
        )

    def test_all_columns_search_matches_integer_values(self):
        self.assertEqual(self._mixed_viewer().apply_search("1001"), 1)

    def test_all_columns_search_matches_date_values(self):
        self.assertEqual(self._mixed_viewer().apply_search("2024-01-06"), 1)

    def test_all_columns_search_matches_categorical_values(self):
        self.assertEqual(self._mixed_viewer().apply_search("blu"), 1)

    def test_all_columns_search_skips_nested_binary_and_object_columns(self):
        viewer = PolarsTableViewer(
            dataframe=pl.DataFrame(
                {
                    "s": ["x", "y"],
                    "l": [[1001], [2002]],
                    "b": [b"1001", b"2002"],
                    "o": pl.Series([1001, "z"], dtype=pl.Object),
                }
            ),
            show_controls=False,
            show_info=False,
            show_search=False,
            show_export=False,
        )
        self.addCleanup(viewer.close)
        self.assertEqual(viewer.apply_search("1001"), 0)
        self.assertEqual(viewer.apply_search("x"), 1)

    def test_single_column_search_casts_the_picked_column(self):
        viewer = self._mixed_viewer()
        self.assertEqual(viewer.apply_search("1001", "id"), 1)
        self.assertEqual(viewer.apply_search("1001", "s"), 0)

    def test_empty_search_restores_the_full_row_count(self):
        viewer = self._mixed_viewer()
        self.assertEqual(viewer.apply_search("x"), 1)
        self.assertEqual(viewer.apply_search(""), 2)
