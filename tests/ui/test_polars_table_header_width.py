"""Column headers show their whole "name (dtype)" text (issue #32)."""

from __future__ import annotations

import polars as pl
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.models.polars_table_viewer import (
    MAX_HEADER_WIDTH,
    PolarsTableViewer,
)

_APP = QApplication.instance() or QApplication([])

LONG = "total_attendances_over_four_hours_from_arrival"


def _viewer(frame: pl.DataFrame) -> PolarsTableViewer:
    viewer = PolarsTableViewer(
        dataframe=frame,
        show_controls=False,
        show_info=False,
        show_search=False,
        show_export=False,
    )
    viewer.resize(900, 300)
    viewer.show()
    _APP.processEvents()
    return viewer


def _needed(viewer: PolarsTableViewer, column: int) -> int:
    text = str(
        viewer.model.headerData(
            column, viewer.table_view.horizontalHeader().orientation()
        )
    )
    return viewer.table_view.horizontalHeader().fontMetrics().horizontalAdvance(text)


def test_long_header_gets_room_for_its_text() -> None:
    viewer = _viewer(pl.DataFrame({"id": [1], LONG: [2]}))
    try:
        header = viewer.table_view.horizontalHeader()
        assert header.sectionSize(1) >= _needed(viewer, 1)
        assert header.sectionSize(0) >= header.defaultSectionSize()
    finally:
        viewer.close()


def test_widths_are_refit_after_the_frame_changes() -> None:
    viewer = _viewer(pl.DataFrame({"id": [1]}))
    try:
        viewer.set_dataframe(pl.DataFrame({LONG: [1]}))
        _APP.processEvents()
        header = viewer.table_view.horizontalHeader()
        assert header.sectionSize(0) >= _needed(viewer, 0)
    finally:
        viewer.close()


def test_absurd_header_is_capped() -> None:
    viewer = _viewer(pl.DataFrame({"x" * 400: [1]}))
    try:
        assert viewer.table_view.horizontalHeader().sectionSize(0) <= MAX_HEADER_WIDTH
    finally:
        viewer.close()
