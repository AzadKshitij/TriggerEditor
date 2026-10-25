"""Shared config-dock widgets: one style, no per-node UI rewrites.

The style system (``base.qss`` + theme JSONs) owns colour, geometry and
states; these widgets own structure and change signals only
(docs/DESIGN_SYSTEM.md §3, §17). Every widget here is painted through its
``objectName`` - no inline QSS, no per-node forks.
"""

from collections.abc import Callable, Iterable

from qtpy.QtCore import QEvent, QSize, Qt, Signal
from qtpy.QtGui import QIcon, QPainter, QPixmap
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Layout tokens (docs/DESIGN_SYSTEM.md §17). Node files must use these
# instead of repeating the numbers.
STRIP_H = 36
TOOLBAR_H = 40
CONTROL_H = 30
CHIP_H = 24
ROW_H = 28
DENSE_ROW_H = 24
ICON_SIZE = 12
#: Air above every config section, so two adjacent sections do not merge.
SECTION_GAP = 4


def _resource_id_for(pixmap: QPixmap) -> str | None:
    """The ResourceManager id a rendered pixmap came from, if known.

    Imported lazily: the widgets in this module are imported by every node,
    and the resource manager pulls in the theme stack.
    """
    try:
        from trigger_designer.qt.resource_manager import ResourceManager

        return ResourceManager.resource_id_for(pixmap)
    except Exception:  # noqa: BLE001 - a missing id is not fatal
        return None


class IconButton(QPushButton):
    """Icon-only button: 30x30, 12px icon, tooltip + accessible name required.

    Resolves the icon via ResourceManager id first, then a compiled
    ``:/qss_icons`` fallback, then ``QIcon.fromTheme`` (last resort —
    blank on Windows, see docs/DESIGN_SYSTEM.md §4).
    """

    def __init__(
        self,
        tooltip: str,
        icon: QIcon | QPixmap | str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setText("")
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setFixedSize(QSize(30, 30))
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        #: The resource id the icon was loaded from, when it came from the
        #: ResourceManager. Used to re-resolve the icon after a theme switch.
        self._resource_id: str | None = None
        if isinstance(icon, QIcon):
            self.setIcon(icon)
        elif isinstance(icon, QPixmap):
            self.setIcon(QIcon(icon))
            self._resource_id = _resource_id_for(icon)
        elif isinstance(icon, str):
            self.setIcon(QIcon(icon))

    def apply_theme(self) -> None:
        """Re-resolve the icon after a theme change.

        The monochrome ``ui/`` glyphs are re-rendered for the active theme
        (see :mod:`trigger_designer.qt.theme_icons`). A button that was
        built before the switch still holds the old pixmap, so it has to
        ask the resource manager for the icon again.
        """
        if not self._resource_id:
            return
        from trigger_designer.qt.resource_manager import ResourceManager

        pixmap = ResourceManager().get(self._resource_id)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.setIcon(QIcon(pixmap))

    @classmethod
    def themed(
        cls,
        tooltip: str,
        rsm_icon: QIcon | QPixmap | None = None,
        qss_fallback: str | None = None,
        theme_fallback: str | None = None,
        parent: QWidget | None = None,
    ) -> "IconButton":
        """Build an IconButton trying rsm -> :/qss_icons -> fromTheme."""
        icon: QIcon | QPixmap | None = None
        if isinstance(rsm_icon, QPixmap):
            # The pixmap is kept as it is: the resource it was rendered from
            # is what lets ``apply_theme`` resolve it again after a theme
            # switch. Wrapping it in a QIcon here would lose that.
            icon = rsm_icon
        elif isinstance(rsm_icon, QIcon) and not rsm_icon.isNull():
            icon = rsm_icon
        if icon is None and qss_fallback:
            candidate = QIcon(qss_fallback)
            if not candidate.isNull():
                icon = candidate
        if icon is None and theme_fallback:
            candidate = QIcon.fromTheme(theme_fallback)
            if not candidate.isNull():
                icon = candidate
        return cls(tooltip, icon, parent)


class TextButton(QPushButton):
    """Labelled button for bulk actions whose icon alone is ambiguous.

    Reserved for pairs like "All" / "None" (select-all vs deselect-all) where
    two near-identical checkbox glyphs cannot be told apart at a glance.
    Everything else in the Config Dock stays icon-only; see
    docs/DESIGN_SYSTEM.md §4.3.
    """

    def __init__(
        self,
        text: str,
        tooltip: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("TextButton")
        self.setToolTip(tooltip or text)
        self.setAccessibleName(tooltip or text)
        self.setMinimumHeight(CONTROL_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class NoWheelComboBox(QComboBox):
    """Combo box that ignores the mouse wheel unless its popup is open.

    Prevents accidental selection changes when scrolling a sidebar with
    the cursor resting over a dropdown (a focused combo would otherwise
    keep stealing wheel events long after it was touched).
    """

    def wheelEvent(self, event) -> None:
        try:
            popup_open = self.view().isVisible()
        except RuntimeError:
            popup_open = False
        if not popup_open:
            event.ignore()
            return
        super().wheelEvent(event)


class Chip(QLabel):
    """24px identity/count chip for the dock context strip.

    ``tone`` selects a QSS variant: ``""`` (default), ``"accent"`` for the
    one piece of live state a dock highlights, or ``"muted"``.
    """

    def __init__(
        self, text: str, tone: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("Chip")
        self.setProperty("tone", tone)
        self.setFixedHeight(CHIP_H)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class StatusBadge(QLabel):
    """18px status badge; by exception only (§0.1: status by exception)."""

    def __init__(
        self, text: str, tone: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("StatusBadge")
        self.setProperty("tone", tone)
        self.setFixedHeight(18)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class InspectorHeader(QFrame):
    """Dock identity: category rail, node glyph and title.

    The rail carries the node-category colour (§0.2) so the dock names the
    family the same way the canvas does. No status badge is shown by
    default - status appears only when the normal state does not apply.
    """

    def __init__(
        self,
        title: str,
        icon: QIcon | QPixmap | None = None,
        category: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorHeader")
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        rail = QFrame(self)
        rail.setObjectName("InspectorRail")
        rail.setFixedWidth(3)
        rail.setProperty("category", category or "")
        layout.addWidget(rail)

        self._icon = QLabel(self)
        self._icon.setObjectName("InspectorIcon")
        self._icon.setFixedSize(QSize(20, 20))
        self.set_icon(icon)
        layout.addWidget(self._icon)

        self._title = QLabel(title, self)
        self._title.setObjectName("InspectorTitle")
        layout.addWidget(self._title)
        layout.addStretch(1)

        self._badge: StatusBadge | None = None

    def set_icon(self, icon: QIcon | QPixmap | None) -> None:
        if icon is None or (isinstance(icon, QIcon) and icon.isNull()):
            self._icon.clear()
            return
        pixmap = icon.pixmap(QSize(18, 18)) if isinstance(icon, QIcon) else icon
        if pixmap.isNull():
            return
        self._icon.setPixmap(
            pixmap.scaled(
                QSize(18, 18),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_status(self, text: str, tone: str = "") -> None:
        """Show a status badge; pass an empty ``text`` to hide it again."""
        if not text:
            if self._badge is not None:
                self._badge.hide()
            return
        if self._badge is None:
            self._badge = StatusBadge("", tone, self)
            self.layout().addWidget(self._badge)
        self._badge.setText(text)
        self._badge.setProperty("tone", tone)
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self._badge.show()


class ContextStrip(QFrame):
    """Schema/configuration summary under the identity header.

    Chips describe configuration only - column counts, checked counts,
    mapping counts. Evaluated results (rows read, rows matched, previews)
    belong to the Data Preview, never to this strip.
    """

    def __init__(
        self,
        chips: Iterable[tuple[str, str]] = (),
        label: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ContextStrip")
        self.setFixedHeight(30)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 0, 6, 0)
        self._layout.setSpacing(4)

        self._chips: list[Chip] = []
        self._label = QLabel(label, self)
        self._label.setObjectName("ContextLabel")
        self._layout.addStretch(1)
        self._layout.addWidget(self._label)
        self.set_chips(chips)

    def set_chips(self, chips: Iterable[tuple[str, str]]) -> None:
        for chip in self._chips:
            self._layout.removeWidget(chip)
            chip.deleteLater()
        self._chips = []
        for text, tone in chips:
            chip = Chip(text, tone, self)
            # Insert before the trailing stretch + label.
            self._layout.insertWidget(len(self._chips), chip)
            self._chips.append(chip)

    def set_label(self, text: str) -> None:
        self._label.setText(text)


class ConfigSection(QFrame):
    """Flat section: overline heading + hairline, no group-box frame.

    Optional ``collapsible`` gives the header a chevron and turns the whole
    header row into the hit target. Folding is for content that is genuinely
    long (a rule stack, a formula card); a label, a mode switch or a
    two-field form stays visible.
    """

    def __init__(
        self,
        title: str = "",
        info: str | None = None,
        parent: QWidget | None = None,
        *,
        collapsible: bool = False,
        collapsed: bool = False,
        count: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ConfigSection")
        # A section is a divider, not a group box. A title only earns its
        # 20px row when the controls below cannot say what they do on their
        # own (a checklist, a mapping grid); a single combo or a form with
        # its own labels passes an empty title and costs nothing.
        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        self._has_header = bool(title) or collapsible
        # Sections that read as different things get real air between them; a
        # bare section adds its hairline on top of the same gap. Without this
        # the pane reads as one undifferentiated stack of controls.
        outer.setContentsMargins(0, SECTION_GAP, 0, 0)

        self._collapsible = collapsible
        self._collapsed = collapsed and collapsible
        self._header: QFrame | None = None
        self._chevron: QLabel | None = None
        self._title: QLabel | None = None

        if self._has_header:
            self._header = QFrame(self)
            self._header.setObjectName("SectionHeader")
            self._header.setFixedHeight(20)
            self._header.setProperty("collapsible", "true" if collapsible else "false")
            header_layout = QHBoxLayout(self._header)
            header_layout.setContentsMargins(2, 0, 2, 0)
            header_layout.setSpacing(4)

            self._chevron = QLabel(self._header)
            self._chevron.setObjectName("SectionChevron")
            self._chevron.setFixedWidth(10)
            self._chevron.hide()
            header_layout.addWidget(self._chevron)
            if collapsible:
                self._chevron.show()

            self._title = QLabel(title.upper(), self._header)
            self._title.setObjectName("SectionTitle")
            header_layout.addWidget(self._title)
            header_layout.addStretch(1)

            if collapsible:
                self._header.setCursor(Qt.CursorShape.PointingHandCursor)
                self._header.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                self._header.mousePressEvent = self._on_header_pressed  # type: ignore[method-assign]
                self._header.keyPressEvent = self._on_header_key  # type: ignore[method-assign]

            outer.addWidget(self._header)
        else:
            # Bare sections have no title line, so a hairline does the
            # grouping instead of text.
            divider = QFrame(self)
            divider.setObjectName("SectionDivider")
            divider.setFixedHeight(1)
            outer.addWidget(divider)

        self._body = QFrame(self)
        self._body.setObjectName("SectionBody")
        self._layout = QVBoxLayout(self._body)
        self._layout.setSpacing(2)
        self._layout.setContentsMargins(0, 2 if self._has_header else 0, 0, 0)
        outer.addWidget(self._body)

        if info:
            # Explanations used to wrap to a second line at 300px; hover
            # reads the same sentence for free.
            self.setToolTip(info)
            if self._header is not None:
                self._header.setToolTip(info)

        if collapsible:
            self._apply_collapsed()

    # -- composition -----------------------------------------------------
    def addWidget(self, widget: QWidget, stretch: int = 0) -> None:
        self._layout.addWidget(widget, stretch)

    def addLayout(self, layout: QLayout, stretch: int = 0) -> None:
        self._layout.addLayout(layout, stretch)

    def set_count(self, text: str) -> None:
        """Counts are no longer rendered in section headers.

        The same number was repeated in three places (strip, header, table)
        and the header row cannot afford it at this dock height. The method
        stays so count call sites do not need re-plumbing.
        """

    def add_header_action(self, widget: QWidget) -> None:
        """Place an action (e.g. Add) at the right end of the section header.

        The header is a 20px row; a 30px control dropped into it is taller
        than its parent and draws over the body below (reading as two
        controls overlapping). Grow the header to whatever the action needs
        instead of letting the action escape its row.
        """
        if self._header is None:
            return
        # ``sizeHint`` alone under-reports a button that pins its own size
        # (IconButton is fixed 30x30), so take the fixed minimum too.
        needed = max(widget.sizeHint().height(), widget.minimumHeight())
        if needed > self._header.height():
            self._header.setFixedHeight(needed)
        self._header.layout().addWidget(widget)

    def set_title(self, title: str) -> None:
        if self._title is not None:
            self._title.setText(title.upper())

    # -- folding ---------------------------------------------------------
    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        if not self._collapsible:
            return
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._apply_collapsed()

    def _apply_collapsed(self) -> None:
        self._body.setVisible(not self._collapsed)
        self._chevron.setText("\u25b8" if self._collapsed else "\u25be")

    def _on_header_pressed(self, event) -> None:
        self.set_collapsed(not self._collapsed)

    def _on_header_key(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.set_collapsed(not self._collapsed)
            return
        event.ignore()


class SegmentedControl(QWidget):
    """Exclusive 30px mode switch (Simple/Expression, By name/By position).

    Emits its own ``changed`` signal, so the undo layer must not also bind
    the buttons nested inside it - that would record one edit twice.
    """

    _undo_composite = True

    changed = Signal(str)

    def __init__(
        self,
        options: Iterable[str],
        current: str | None = None,
        parent: QWidget | None = None,
        *,
        expanded: bool = False,
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Segmented")
        options = list(options)
        self._value = current if current in options else (options[0] if options else "")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for option in options:
            button = QPushButton(option, self)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setFixedHeight(CONTROL_H)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setChecked(option == self._value)
            button.toggled.connect(self._on_toggled)
            if expanded:
                button.setMinimumWidth(0)
                button.setSizePolicy(
                    QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
                )
            if compact:
                button.setProperty("compact", True)
            self._group.addButton(button)
            self._buttons[option] = button
            layout.addWidget(button, 1 if expanded else 0)
        if not expanded:
            layout.addStretch(1)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        button = self._buttons.get(value)
        if button is None or value == self._value:
            return
        self._value = value
        was_blocked = button.blockSignals(True)
        button.setChecked(True)
        button.blockSignals(was_blocked)

    def _on_toggled(self, checked: bool) -> None:
        if not checked:
            return
        button = self.sender()
        value = button.text() if isinstance(button, QPushButton) else ""
        if not value or value == self._value:
            return
        self._value = value
        self.changed.emit(value)


class FormRow(QFrame):
    """One setting: label left, control right, optional hint under both."""

    def __init__(
        self,
        label: str,
        field: QWidget,
        hint: str | None = None,
        parent: QWidget | None = None,
        *,
        label_width: int = 0,
        action: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FieldRow")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        label_widget = QLabel(label, self)
        label_widget.setObjectName("FieldLabel")
        if label_width:
            label_widget.setFixedWidth(label_width)
        row.addWidget(label_widget)
        row.addWidget(field, 1)
        if action is not None:
            # A trailing control (browse, clear) sits in the same 30px row
            # instead of owning a line of its own.
            row.addWidget(action)
        layout.addLayout(row)

        self._row = row
        self._field = field

        if hint:
            hint_label = QLabel(hint, self)
            hint_label.setObjectName("FieldHint")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)

    # -- composition -----------------------------------------------------
    def field(self) -> QWidget:
        """The control this row shows."""
        return self._field

    def replace_field(self, widget: QWidget) -> None:
        """Swap the control in place, keeping the label and stretch.

        Nodes that rebuild their control when a type changes (generate rows)
        need this: ``widget.parent().layout().replaceWidget`` would land on
        the row's outer layout and silently drop the widget.
        """
        self._row.replaceWidget(self._field, widget)
        self._field = widget


class FormGrid(QFrame):
    """Columns of labelled fields: label above control, one cell per field."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FieldStack")
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(6)
        self._grid.setVerticalSpacing(4)

    def add(
        self,
        label: str,
        field: QWidget,
        row: int = 0,
        col: int = 0,
        colspan: int = 1,
    ) -> None:
        cell = QFrame(self)
        cell.setObjectName("FieldStack")
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label_widget = QLabel(label, cell)
        label_widget.setObjectName("FieldLabel")
        layout.addWidget(label_widget)
        layout.addWidget(field)
        self._grid.addWidget(cell, row, col, 1, colspan)
        self._grid.setColumnStretch(col, 1)


class ColumnChecklist(QWidget):
    """Scrollable checkbox list. Emits checked column names on change."""

    # Emits its own `changed` signal, so the undo layer must not also bind the
    # checkboxes nested inside it - that would record one edit twice.
    _undo_composite = True

    changed = Signal(list)

    def __init__(
        self,
        columns: Iterable[str] = (),
        checked: Iterable[str] = (),
        label_fn: Callable[[str], str] | None = None,
        min_height: int = 0,
        max_height: int = 320,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ColumnChecklist")
        self._label_fn = label_fn or (lambda col: col)
        self._suspend = False
        self._fitting = False
        self.checkboxes: dict[str, QCheckBox] = {}

        # The list keeps its own scrollbar and its height tracks the rows: one
        # column is one row tall, a dozen columns a dozen rows, and past
        # ``max_height`` the rows scroll inside the section instead of growing
        # the pane. Rows are never squeezed (a checkbox's minimum ignores the
        # stylesheet padding, so a forced height draws the labels over each
        # other), and spare height never lands between them.
        self._min_height = min_height
        self._max_height = max_height
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("ColumnChecklistScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._inner = QWidget(self._scroll)
        self._inner.setObjectName("ColumnChecklistContent")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(2)
        self._scroll.setWidget(self._inner)
        layout.addWidget(self._scroll)

        self.setColumns(columns, checked)

    def setColumns(self, columns: Iterable[str], checked: Iterable[str] = ()) -> None:
        self._suspend = True
        try:
            while self._inner_layout.count():
                item = self._inner_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    # Unparent before the deferred delete: a widget that stays
                    # a child until the event loop runs keeps painting itself
                    # over the rows that replaced it.
                    widget.setParent(None)
                    widget.deleteLater()
            self.checkboxes.clear()
            checked_set = set(checked)
            for col in columns:
                checkbox = QCheckBox(self._label_fn(col))
                checkbox.setChecked(col in checked_set)
                # A row keeps the height its text needs: free to grow, it
                # spreads the spare space out and a three-column schema ends
                # up with three rows across half the pane.
                checkbox.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
                )
                checkbox.stateChanged.connect(self._on_state_changed)
                self.checkboxes[col] = checkbox
                self._inner_layout.addWidget(checkbox)
            # Spare height collects under the rows, not between them.
            self._inner_layout.addStretch(1)
        finally:
            self._suspend = False
        self._fit_rows()

    def _fit_rows(self) -> None:
        """Size the view to the rows, capped, so it never squeezes or pads.

        A scroll area sizes its widget from the layout's *minimum*, and a
        checkbox's minimum ignores the stylesheet's padding - left alone, the
        rows are compressed until the labels overlap. Pinning the container to
        the layout's hint keeps every row at its natural height; the view then
        takes exactly as much as those rows need, up to ``max_height``, so a
        one-column schema is one row tall instead of a fixed empty box.
        """
        needed = self._inner_layout.sizeHint().height()
        self._inner.setMinimumHeight(needed)
        if self._fitting:
            return
        self._fitting = True
        try:
            frame = 2 * self._scroll.frameWidth()
            view = min(max(needed, self._min_height), self._max_height) + frame
            self._scroll.setFixedHeight(view)
            self.setFixedHeight(view)
        finally:
            self._fitting = False

    def showEvent(self, event) -> None:
        # The stylesheet is what gives a row its height, and it lands on the
        # checkboxes when they are polished - after ``setColumns`` measured
        # them. Re-measure on show so a themed row is never squeezed.
        super().showEvent(event)
        self._fit_rows()

    def event(self, event) -> bool:
        # A theme swap changes the row height (and the scroll frame), so the
        # measured view height has to follow it.
        if event.type() in (
            QEvent.Type.Polish,
            QEvent.Type.StyleChange,
            QEvent.Type.FontChange,
        ):
            self._fit_rows()
        return super().event(event)

    def setChecked(self, checked: Iterable[str]) -> None:
        self._suspend = True
        try:
            checked_set = set(checked)
            for col, checkbox in self.checkboxes.items():
                checkbox.setChecked(col in checked_set)
        finally:
            self._suspend = False

    def set_all_checked(self, checked: bool) -> None:
        """Check/uncheck every box, emitting :attr:`changed` exactly once.

        Bulk actions (All/None buttons) must use this instead of looping over
        :attr:`checkboxes`: each raw ``setChecked`` fires ``changed``, and
        every handler run re-evaluates the whole downstream workflow, so one
        click costs N full recomputes on an N-column frame.
        """
        self._suspend = True
        try:
            for checkbox in self.checkboxes.values():
                checkbox.setChecked(checked)
        finally:
            self._suspend = False
        self.changed.emit(self.checked())

    def checked(self) -> list[str]:
        return [col for col, cb in self.checkboxes.items() if cb.isChecked()]

    def _on_state_changed(self, _state: int) -> None:
        if not self._suspend:
            self.changed.emit(self.checked())


class ElidedLabel(QLabel):
    """A one-line label that elides instead of widening its parent."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = str(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(self._full_text)
        super().setText(self._full_text)

    def set_full_text(self, text: str) -> None:
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        super().setText(self._full_text)
        self.update()

    def full_text(self) -> str:
        return self._full_text

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(0, hint.height())

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        text = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            max(self.width(), 0),
        )
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        painter.end()


class RuleStack(QWidget):
    """Ordered cards with summary-first headers and one add button.

    The owner keeps the list; this widget only draws it and emits intents.
    A card can collapse to a one-line summary, which is the default for long
    rule lists. The summary is supplied by the owner and can be refreshed
    without rebuilding the card.
    """

    add_requested = Signal()
    remove_requested = Signal(int)
    move_requested = Signal(int, int)
    duplicate_requested = Signal(int)

    def __init__(self, add_tooltip: str, rsm=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RuleStack")
        self._rsm = rsm
        self._cards: list[QFrame] = []
        self._headers: list[QFrame] = []
        self._bodies: list[QWidget] = []
        self._summaries: list[QLabel] = []
        self._chevrons: list[QLabel] = []
        self._callbacks: list = []
        self._collapsed: list[bool] = []
        self._titles: list[QLabel] = []
        self._ups: list[QWidget] = []
        self._downs: list[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SECTION_GAP)
        self._cards_layout = QVBoxLayout()
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(SECTION_GAP)

        # The add button sits above the cards: appending a card then never
        # moves a new control under the pointer that just clicked Add.
        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_row.addStretch(1)
        self.add_button = IconButton.themed(
            add_tooltip,
            rsm_icon=self._icon("icon_add"),
            qss_fallback=":/qss_icons/dark/rc/arrow_right.png",
            parent=self,
        )
        self.add_button.clicked.connect(self.add_requested.emit)
        add_row.addWidget(self.add_button)
        layout.addLayout(add_row)
        layout.addLayout(self._cards_layout)

    def _icon(self, name: str):
        if self._rsm is None:
            return None
        try:
            return self._rsm.get(name)
        except Exception:  # noqa: BLE001 - icon lookup is advisory
            return None

    def clear(self) -> None:
        self._cards, self._headers, self._bodies = [], [], []
        self._summaries, self._chevrons, self._callbacks = [], [], []
        self._collapsed = []
        self._titles, self._ups, self._downs = [], [], []
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def remove_card(self, index: int) -> None:
        """Remove one card without touching the others (no full rebuild)."""
        if not 0 <= index < len(self._cards):
            return
        card = self._cards.pop(index)
        for rows in (
            self._headers,
            self._bodies,
            self._summaries,
            self._chevrons,
            self._callbacks,
            self._collapsed,
            self._titles,
            self._ups,
            self._downs,
        ):
            rows.pop(index)
        self._cards_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self._renumber()

    def _renumber(self) -> None:
        count = len(self._cards)
        for position, title in enumerate(self._titles):
            title.setText(str(position + 1))
        for position, (up, down) in enumerate(zip(self._ups, self._downs)):
            up.setEnabled(position > 0)
            down.setEnabled(position < count - 1)

    def add_card(
        self,
        index: int,
        count: int,
        body: QWidget,
        *,
        summary: str = "",
        collapsible: bool = False,
        collapsed: bool = False,
        on_toggle=None,
    ) -> QFrame:
        card = QFrame(self)
        card.setObjectName("RuleCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 2, 4, 4)
        card_layout.setSpacing(2)

        header = QFrame(card)
        header.setObjectName("RuleCardHeader")
        header.setFixedHeight(30)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 0, 2, 0)
        header_layout.setSpacing(2)

        chevron = QLabel("", header)
        chevron.setObjectName("RuleChevron")
        chevron.setFixedWidth(10)
        chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if collapsible:
            header_layout.addWidget(chevron)
        else:
            chevron.hide()

        title = QLabel(str(index + 1), header)
        title.setObjectName("RuleNumber")
        title.setFixedWidth(20)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)

        summary_label = ElidedLabel(summary or f"Rule {index + 1}", header)
        summary_label.setObjectName("RuleSummary")
        header_layout.addWidget(summary_label, 1)

        up = IconButton.themed(
            "Move up",
            rsm_icon=self._icon("icon_move_up"),
            qss_fallback=":/qss_icons/dark/rc/arrow_up.png",
            parent=header,
        )
        down = IconButton.themed(
            "Move down",
            rsm_icon=self._icon("icon_move_down"),
            qss_fallback=":/qss_icons/dark/rc/arrow_down.png",
            parent=header,
        )
        duplicate = IconButton.themed(
            "Duplicate",
            rsm_icon=self._icon("icon_copy"),
            qss_fallback=":/qss_icons/dark/rc/window_new.png",
            parent=header,
        )
        remove = IconButton.themed(
            "Remove",
            rsm_icon=self._icon("icon_remove"),
            qss_fallback=":/qss_icons/dark/rc/window_close.png",
            parent=header,
        )
        up.setEnabled(index > 0)
        down.setEnabled(index < count - 1)

        def position() -> int:
            try:
                return self._cards.index(card)
            except ValueError:
                return -1

        up.clicked.connect(lambda _=False: self.move_requested.emit(position(), -1))
        down.clicked.connect(lambda _=False: self.move_requested.emit(position(), 1))
        duplicate.clicked.connect(
            lambda _=False: self.duplicate_requested.emit(position())
        )
        remove.clicked.connect(lambda _=False: self.remove_requested.emit(position()))
        header_layout.addWidget(up)
        header_layout.addWidget(down)
        header_layout.addWidget(duplicate)
        header_layout.addWidget(remove)

        body.setObjectName("RuleCardBody")
        card_layout.addWidget(header)
        card_layout.addWidget(body)
        self._cards_layout.addWidget(card)

        self._cards.append(card)
        self._headers.append(header)
        self._bodies.append(body)
        self._summaries.append(summary_label)
        self._chevrons.append(chevron)
        self._callbacks.append(on_toggle)
        self._collapsed.append(False)
        self._titles.append(title)
        self._ups.append(up)
        self._downs.append(down)

        if collapsible:
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            header.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            header.setToolTip("Expand or collapse this card")
            header.mousePressEvent = (  # type: ignore[method-assign]
                lambda event: self._toggle(position())
            )
            header.keyPressEvent = (  # type: ignore[method-assign]
                lambda event: self._toggle_key(event, position())
            )

        self._apply_collapsed(index, collapsed and collapsible)
        self._renumber()
        return card

    def set_card_summary(self, index: int, text: str) -> None:
        if 0 <= index < len(self._summaries):
            label = self._summaries[index]
            if isinstance(label, ElidedLabel):
                label.set_full_text(text or f"Rule {index + 1}")
            else:
                label.setText(text or f"Rule {index + 1}")
            label.setToolTip(text)

    def is_collapsed(self, index: int) -> bool:
        return 0 <= index < len(self._collapsed) and self._collapsed[index]

    def _apply_collapsed(self, index: int, collapsed: bool) -> None:
        if not (0 <= index < len(self._bodies)):
            return
        self._collapsed[index] = bool(collapsed)
        self._bodies[index].setVisible(not collapsed)
        self._chevrons[index].setText("\u25b8" if collapsed else "\u25be")
        self._headers[index].setProperty("collapsed", collapsed)
        self._headers[index].style().unpolish(self._headers[index])
        self._headers[index].style().polish(self._headers[index])

    def _toggle(self, index: int) -> None:
        if not (0 <= index < len(self._bodies)):
            return
        collapsed = not self._collapsed[index]
        self._apply_collapsed(index, collapsed)
        callback = self._callbacks[index]
        if callable(callback):
            callback(not collapsed)

    def _toggle_key(self, event, index: int) -> None:
        if event.key() in (
            Qt.Key.Key_Space,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self._toggle(index)
            return
        event.ignore()


class EmptyStateLabel(QLabel):
    """Centered gray placeholder for nodes with no incoming data."""

    def __init__(
        self,
        text: str = "No incoming data available",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("EmptyStateLabel")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
