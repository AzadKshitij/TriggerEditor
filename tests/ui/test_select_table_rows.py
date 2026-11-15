#!/usr/bin/env python3
"""Row by row, the Select table shows where one column ends and the next begins.

The table turns Qt's grid off (DESIGN_SYSTEM §11: one hairline per row, no
vertical lines), so with nothing painting that hairline the 23 rows of a real
workflow read as one block and a rename could not be tied to its column
(issue #33).

These tests read the pixels the view actually paints, not the attributes that
were set: the hairline has to run under every row and the row height has to
stay 28px, because the Select dock measures its minimum height by it.
"""

from qtpy.QtCore import QModelIndex, QRect
from qtpy.QtGui import QColor, QImage, QPainter
from qtpy.QtWidgets import QApplication, QStyleOptionViewItem

from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.select_table_widget import (
    RenameDelegate,
    RowSeparatorDelegate,
    SelectTableView,
    rename_text_rect,
    row_separator_y,
)

_APP = QApplication.instance() or QApplication([])

_ROW_W = 240
_ROW_H = 28
BACKGROUND = QColor("#14171B")


def _row_option(view: SelectTableView) -> QStyleOptionViewItem:
    """A view item option the way QTableView hands one to a delegate."""
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, _ROW_W, _ROW_H)
    option.font = view.font()
    option.fontMetrics = view.fontMetrics()
    option.palette = view.palette()
    option.widget = view
    return option


def _render(delegate, option: QStyleOptionViewItem) -> QImage:
    image = QImage(option.rect.size(), QImage.Format.Format_ARGB32)
    image.fill(BACKGROUND)
    painter = QPainter(image)
    try:
        # An invalid index paints the plain cell, which is the row itself.
        delegate.paint(painter, option, QModelIndex())
    finally:
        painter.end()
    return image


def _make_view() -> SelectTableView:
    view = SelectTableView()
    view.resize(_ROW_W + 40, _ROW_H * 4)
    view.show()
    _APP.processEvents()
    return view


def _drop(view: SelectTableView) -> None:
    view.hide()
    view.deleteLater()
    _APP.processEvents()


def _separator_colour() -> int:
    return ResourceManager().get_theme_color("border_primary").rgba()


def _painted(image: QImage, x: int, y: int) -> bool:
    return image.pixelColor(x, y).rgba() != BACKGROUND.rgba()


def test_row_hairline_is_painted_under_the_row() -> None:
    view = _make_view()
    try:
        option = _row_option(view)
        image = _render(RowSeparatorDelegate(view), option)

        y = row_separator_y(option)
        assert y == option.rect.bottom()
        # The hairline runs the whole row, corners included, or a row boundary
        # fades out exactly where two columns meet.
        drawn = [
            x
            for x in (option.rect.left(), option.rect.center().x(), option.rect.right())
            if _painted(image, x, y)
        ]
        assert drawn == [
            option.rect.left(),
            option.rect.center().x(),
            option.rect.right(),
        ], f"only {len(drawn)} of 3 points along the row's last pixel are painted"
        assert (
            image.pixelColor(option.rect.center().x(), y).rgba() == _separator_colour()
        )
        # Nothing above it: the row itself is not boxed in.
        assert not _painted(image, option.rect.center().x(), y - 2)
    finally:
        _drop(view)


def test_hairline_stays_inside_the_28px_row() -> None:
    view = _make_view()
    try:
        option = _row_option(view)
        image = _render(RowSeparatorDelegate(view), option)

        painted = [
            y
            for y in range(image.height())
            if _painted(image, option.rect.center().x(), y)
        ]
        assert painted, "the row separator never reached the row it belongs to"
        # A line on the row's own pixels keeps the row 28px, which the Select
        # dock measures its minimum height by.
        assert max(painted) <= option.rect.height() - 1
        assert view.verticalHeader().defaultSectionSize() == _ROW_H
    finally:
        _drop(view)


def test_view_uses_the_row_separator_delegate() -> None:
    view = _make_view()
    try:
        assert isinstance(view.itemDelegate(), RowSeparatorDelegate)
        assert not view.showGrid(), "vertical grid lines are not part of the design"
    finally:
        _drop(view)


def test_rename_cell_leaves_the_row_background_alone() -> None:
    """The rename cell styles its text only; the row stays one surface."""
    view = _make_view()
    try:
        option = _row_option(view)
        image = _render(RenameDelegate(view), option)

        text = rename_text_rect(option)
        for x, y in (
            (option.rect.left() + 1, 2),
            (text.left() - 2, option.rect.center().y()),
        ):
            assert not _painted(image, x, y), (
                f"the rename cell painted over the row at ({x}, {y})"
            )
        assert text.width() < option.rect.width()
    finally:
        _drop(view)
