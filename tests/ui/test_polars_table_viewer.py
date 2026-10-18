"""Widget-level behaviour of the Polars table viewer.

Construction, header-click sorting, search and shortcut scoping. The model
itself is covered by ``tests/unit/test_polars_table_model.py``.
"""

from __future__ import annotations

import unittest

import polars as pl
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence, QShortcut
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.models.polars_table_viewer import (
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
