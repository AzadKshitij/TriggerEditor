"""Graph node: a charting sink whose window opens after a run.

The Graph configures *what* to chart; the shared
:mod:`trigger_designer.core.charts` model decides what the data means, and
the window's renderer draws it in the non-modal window: matplotlib by
default, or pyqtgraph when the node's Renderer is set to it.

Two data paths feed the chart:

* Live evaluation hands the frame to ``ShapingContent.frames[0]``; the dock
  projects the live schema into the column choices without rewriting a saved
  selection.
* A workflow run publishes the frame the node passed through over the
  ``runDataReady`` signal. The executor calls ``after_execution`` on the
  worker thread, so that hook only emits; the slot runs on the GUI thread and
  unlocks the window.

The generated code is data-only: it assigns the incoming frame to the node's
output variable. It never imports a plotting library, shows a window or writes
a file.
"""

from typing import Any

from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import QLineEdit, QVBoxLayout

from trigger_designer.core.charts import build_chart_spec, effective_aggregation
from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    register_node,
)
from trigger_designer.core.shaping import graph as core
from trigger_designer.qt.helpers.shaping_support import ShapingContent, ShapingNode
from trigger_designer.qt.node_base import frame_schema
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    FormRow,
    IconButton,
    NoWheelComboBox,
)

#: Display label -> stored value for the chart type combo.
_CHART_TYPE_ITEMS = (
    ("Line", "line"),
    ("Bar", "bar"),
    ("Scatter", "scatter"),
)

#: Display label -> stored value for the aggregation combo.
_AGGREGATION_ITEMS = (
    ("None", "none"),
    ("Sum", "sum"),
    ("Count", "count"),
    ("Mean", "mean"),
    ("Median", "median"),
    ("Min", "min"),
    ("Max", "max"),
)

#: Display label -> stored value for the renderer combo. The values are the
#: library names themselves: the tooltip has to describe the real difference.
_RENDERER_ITEMS = (
    ("matplotlib", "matplotlib"),
    ("pyqtgraph", "pyqtgraph"),
)

#: The renderer every saved workflow drew with before this setting existed.
_DEFAULT_RENDERER = "matplotlib"

#: Color-by entry that clears the setting.
_NO_COLOR_LABEL = "(none)"
#: Placeholder for a column column setting with no value yet.
_NO_COLUMN_LABEL = "(select column)"

_WINDOW_REFRESH_DEBOUNCE_MS = 300


def _label_for(
    items: tuple[tuple[str, str], ...], value: str, default: str = ""
) -> str:
    for label, item_value in items:
        if item_value == value:
            return label
    return default


def _value_for(
    items: tuple[tuple[str, str], ...], label: str, default: str = ""
) -> str:
    for item_label, value in items:
        if item_label == label:
            return value
    return default


class GraphContent(ShapingContent):
    """Chart configuration dock; the data itself is a pass-through."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.graph"
    OUTPUT_KINDS = ("graph",)
    INPUTS = 1
    HISTORY = "Graph"
    SUMMARY = "chart, pass-through"
    PRESENTATION_SETTINGS = ("renderer",)

    #: Carries the frame a workflow run passed through the node. Emitted from
    #: the executor's worker thread; the connection queues the slot onto the
    #: GUI thread, which is what makes ``after_execution`` widget-safe.
    runDataReady = Signal(object)

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        #: Frame handed over by the executor on its worker thread. Kept apart
        #: from ``frames[0]`` so a run's result survives until the GUI slot
        #: and any dock rebuild have seen it.
        self._run_frame: Any = None
        self.workflow_ran_successfully = False
        self._refresh_timer: QTimer | None = None
        self._chart_window: Any | None = None
        self.runDataReady.connect(self._on_run_data_ready)

    # -- settings helpers -------------------------------------------------
    def _value(self, key: str, default: Any = "") -> Any:
        return self.settings.get(key, default)

    @property
    def renderer(self) -> str:
        """The library that draws the window; matplotlib unless chosen."""
        return str(self._value("renderer", _DEFAULT_RENDERER) or _DEFAULT_RENDERER)

    def _frame(self) -> Any:
        if self.frames and self.frames[0] is not None:
            return self.frames[0]
        if self.outputs:
            return self.outputs[0]
        return None

    def _columns(self) -> list[str]:
        frame = self._frame()
        if frame is None:
            return []
        try:
            return list(frame_schema(frame))
        except Exception:  # noqa: BLE001 - schema peek only
            return []

    # -- dock construction ----------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self.open_graph_button = None
        self.graph_section = None

        section = ConfigSection()
        section._undo_composite = True
        self.graph_section = section

        self.open_graph_button = IconButton.themed(
            "Show graph",
            rsm_icon=self.node.rsm.get("icon_external"),
            qss_fallback=":/qss_icons/dark/rc/window_undock.png",
            theme_fallback="window-new",
        )
        self.open_graph_button.clicked.connect(self.open_graph_in_new_window)

        self.graph_type_combo = self._make_choice_combo(_CHART_TYPE_ITEMS)
        self.graph_type_combo.currentIndexChanged.connect(
            lambda _index: self._commit(
                "graph_type", self.graph_type_combo.currentData(), "Type"
            )
        )
        section.addWidget(FormRow("Type", self.graph_type_combo, label_width=72))

        self.renderer_combo = self._make_choice_combo(_RENDERER_ITEMS)
        self.renderer_combo.setToolTip(
            "Library that draws the chart window. pyqtgraph replaces the "
            "navigation toolbar with reset-view and save-PNG buttons."
        )
        self.renderer_combo.setAccessibleName("Chart renderer")
        self.renderer_combo.currentIndexChanged.connect(
            lambda _index: self.set_setting(
                "renderer",
                self.renderer_combo.currentData(),
                "Graph Renderer Changed",
                evaluate=False,
            )
        )
        section.addWidget(FormRow("Renderer", self.renderer_combo, label_width=72))

        self.x_column_combo = self._make_column_combo()
        self.x_column_combo.currentIndexChanged.connect(
            lambda _index: self._commit(
                "x_column", self.x_column_combo.currentData() or "", "X column"
            )
        )
        section.addWidget(FormRow("X column", self.x_column_combo, label_width=72))

        self.y_column_combo = self._make_column_combo()
        self.y_column_combo.currentIndexChanged.connect(
            lambda _index: self._commit(
                "y_column", self.y_column_combo.currentData() or "", "Y column"
            )
        )
        section.addWidget(FormRow("Y column", self.y_column_combo, label_width=72))

        self.color_column_combo = self._make_column_combo()
        self.color_column_combo.currentIndexChanged.connect(
            lambda _index: self._commit(
                "color_column",
                self.color_column_combo.currentData() or "",
                "Color by",
            )
        )
        section.addWidget(FormRow("Color by", self.color_column_combo, label_width=72))

        self.aggregation_combo = self._make_choice_combo(_AGGREGATION_ITEMS)
        self.aggregation_combo.currentIndexChanged.connect(
            lambda _index: self._commit(
                "aggregation",
                self.aggregation_combo.currentData() or "",
                "Aggregate",
            )
        )
        section.addWidget(FormRow("Aggregate", self.aggregation_combo, label_width=72))

        self.title_edit = QLineEdit()
        self.title_edit.setMinimumHeight(30)
        self.title_edit.setPlaceholderText("Chart title")
        self._debounced(
            self.title_edit.textChanged,
            lambda: self._commit("title", self.title_edit.text(), "Title"),
        )
        section.addWidget(FormRow("Title", self.title_edit, label_width=72))

        dock_layout.addWidget(section)
        dock_layout.addStretch()

        self.update_column_options()
        self._sync_widgets_from_model()
        self._refresh_graph_counts()

    @staticmethod
    def _make_choice_combo(
        items: tuple[tuple[str, str], ...],
    ) -> NoWheelComboBox:
        combo = NoWheelComboBox()
        combo.setMinimumHeight(30)
        for label, value in items:
            combo.addItem(label, value)
        return combo

    @staticmethod
    def _make_column_combo() -> NoWheelComboBox:
        combo = NoWheelComboBox()
        combo.setMinimumHeight(30)
        return combo

    def dock_actions(self) -> list:
        """One obvious action, mounted on the dock's label row."""
        button = getattr(self, "open_graph_button", None)
        return [button] if button is not None else []

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        """Configuration summary for the dock context strip."""
        graph_type = str(self._value("graph_type", "line"))
        chips: list[tuple[str, str]] = [(graph_type, "accent")]
        if self.renderer != _DEFAULT_RENDERER:
            chips.append((self.renderer, ""))
        x_column = str(self._value("x_column", ""))
        y_column = str(self._value("y_column", ""))
        if x_column and y_column:
            chips.append((f"{x_column} \u2192 {y_column}", ""))
        aggregation = effective_aggregation(graph_type, self._value("aggregation", ""))
        if aggregation != "none":
            chips.append((aggregation, ""))
        color = str(self._value("color_column", ""))
        if color:
            chips.append((f"by {color}", ""))
        return chips, str(self._value("title", ""))

    def _refresh_graph_counts(self) -> None:
        """Keep the section header count in step with the configuration."""
        self.refresh_dock_context()
        section = getattr(self, "graph_section", None)
        if section is not None:
            section.set_count(str(self._value("graph_type", "line")))

    # -- one model change ------------------------------------------------
    def _commit(self, key: str, value: Any, label: str) -> None:
        self.set_setting(key, value, f"Graph {label} Changed")

    def after_change(self) -> None:
        """Refresh the displayed aggregation and any open chart window."""
        self._sync_aggregation_widget()
        self._refresh_graph_counts()
        self._update_open_graph_button_state()
        self._schedule_window_refresh()

    # -- model -> widgets ------------------------------------------------
    def _sync_widgets_from_model(self) -> None:
        """Project every setting onto the live widgets without emitting."""
        self._set_combo_value(
            getattr(self, "graph_type_combo", None),
            self._value("graph_type", "line"),
        )
        self._set_combo_value(
            getattr(self, "renderer_combo", None),
            self.renderer,
        )
        self.update_column_options()
        self._sync_aggregation_widget()

        edit = getattr(self, "title_edit", None)
        if edit is not None:
            blocked = edit.blockSignals(True)
            try:
                edit.setText(str(self._value("title", "") or ""))
            finally:
                edit.blockSignals(blocked)

        self._refresh_graph_counts()

    def _sync_aggregation_widget(self) -> None:
        combo = getattr(self, "aggregation_combo", None)
        if combo is None:
            return
        effective = effective_aggregation(
            self._value("graph_type", "line"), self._value("aggregation", "")
        )
        self._set_combo_value(combo, effective)

    @staticmethod
    def _set_combo_value(combo: NoWheelComboBox | None, value: Any) -> None:
        if combo is None:
            return
        index = combo.findData(value)
        if index < 0:
            return
        blocked = combo.blockSignals(True)
        try:
            combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(blocked)

    def update_column_options(self) -> None:
        """Project the live schema into the column combos.

        Saved values are never rewritten: a column that disappeared stays
        selected and is shown as ``<name> (missing)``; an empty value shows a
        placeholder. The chart builder reports the problem when opened.
        """
        columns = self._columns()
        self._fill_column_combo(
            getattr(self, "x_column_combo", None),
            columns,
            str(self._value("x_column", "")),
            placeholder=_NO_COLUMN_LABEL,
        )
        self._fill_column_combo(
            getattr(self, "y_column_combo", None),
            columns,
            str(self._value("y_column", "")),
            placeholder=_NO_COLUMN_LABEL,
        )
        self._fill_column_combo(
            getattr(self, "color_column_combo", None),
            columns,
            str(self._value("color_column", "")),
            placeholder=_NO_COLOR_LABEL,
        )
        self._update_open_graph_button_state()
        self._schedule_window_refresh()

    @staticmethod
    def _fill_column_combo(
        combo: NoWheelComboBox | None,
        columns: list[str],
        value: str,
        *,
        placeholder: str,
    ) -> None:
        if combo is None:
            return
        blocked = combo.blockSignals(True)
        try:
            combo.clear()
            if not columns:
                return
            combo.addItem(placeholder, "")
            for name in columns:
                combo.addItem(name, name)
            if value and value not in columns:
                combo.addItem(f"{value} (missing)", value)
            index = combo.findData(value) if value else 0
            combo.setCurrentIndex(max(0, index))
        finally:
            combo.blockSignals(blocked)

    def _update_open_graph_button_state(self) -> None:
        """Unlock Show graph only once a run has produced a drawable frame."""
        button = getattr(self, "open_graph_button", None)
        if button is None:
            return
        has_data = self._frame() is not None or self._run_frame is not None
        columns = self._columns()
        x_column = str(self._value("x_column", ""))
        y_column = str(self._value("y_column", ""))
        ready = bool(
            self.workflow_ran_successfully
            and has_data
            and x_column in columns
            and y_column in columns
        )
        if not self.workflow_ran_successfully:
            text = "Show graph (run the workflow first)"
        elif not ready:
            text = "Show graph (no data to draw)"
        else:
            text = "Show graph"
        button.setEnabled(ready)
        button.setToolTip(text)
        button.setAccessibleName(text)

    # -- chart window ----------------------------------------------------
    def build_spec(self):
        """The chart the current settings and data produce."""
        return build_chart_spec(
            self._frame(),
            chart_type=self._value("graph_type", "line"),
            x_column=self._value("x_column", ""),
            y_column=self._value("y_column", ""),
            color_column=self._value("color_column", ""),
            aggregation=self._value("aggregation", ""),
            title=self._value("title", ""),
        )

    def _schedule_window_refresh(self) -> None:
        """Debounce a redraw so an open window follows edits live."""
        timer = getattr(self, "_refresh_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(_WINDOW_REFRESH_DEBOUNCE_MS)
            timer.timeout.connect(self._refresh_open_window)
            self._refresh_timer = timer
        timer.start()

    def _refresh_open_window(self) -> None:
        window = getattr(self, "_chart_window", None)
        if window is None:
            return
        try:
            if window.isVisible():
                window.set_renderer(self.renderer)
                window.setWindowTitle(self._window_title())
                window.set_spec(self.build_spec())
        except RuntimeError:
            self._chart_window = None

    # -- actions and handlers --------------------------------------------
    def _window_title(self) -> str:
        """Window caption; a non-default renderer is named, per disclosure."""
        title = str(self._value("title", "") or "")
        base = f"Graph \u2014 {title}" if title else "Graph"
        if self.renderer != _DEFAULT_RENDERER:
            base += f" ({self.renderer})"
        return base

    def open_graph_in_new_window(self) -> None:
        """Open (or re-show) the non-modal chart window."""
        if not self.workflow_ran_successfully:
            return
        if self._frame() is None and self._run_frame is not None:
            self.frames[0] = self._run_frame
        window = getattr(self, "_chart_window", None)
        title = self._window_title()
        if window is not None:
            try:
                window.set_renderer(self.renderer)
                window.setWindowTitle(title)
            except RuntimeError:
                window = None
        if window is None:
            from trigger_designer.qt.widgets.nodes.Report.chart_window import (
                ChartWindow,
            )

            window = ChartWindow(renderer=self.renderer)
            self._chart_window = window
            window.setWindowTitle(title)
        window.set_spec(self.build_spec())
        window.show()
        window.raise_()
        window.activateWindow()
        self._update_open_graph_button_state()

    # -- run data --------------------------------------------------------
    def after_execution(self, context: dict[str, Any]) -> None:
        """Publish the frame the run passed through, from the worker thread."""
        data = None
        if isinstance(context, dict):
            data = context.get(self.variable_name)
            if data is None:
                data = context.get("graph_df")
        self.workflow_ran_successfully = True
        if data is not None:
            self._run_frame = data
        try:
            self.runDataReady.emit(data)
        except RuntimeError:
            # The content was deleted while the run was still finishing.
            pass

    def _on_run_data_ready(self, data: Any) -> None:
        """GUI-thread slot: adopt the run's frame and unlock the window."""
        self.workflow_ran_successfully = True
        frame = data if data is not None else self._run_frame
        if frame is not None:
            self.frames[0] = frame
            self._run_frame = frame
        self.update_column_options()
        self._update_open_graph_button_state()

    # -- persistence -----------------------------------------------------
    def deserialize(self, data, hashmap={}):  # noqa: B006
        res = super().deserialize(data, hashmap)
        self.workflow_ran_successfully = False
        self._run_frame = None
        self._sync_widgets_from_model()
        return res


@register_node(ReportNodes.GRAPH, NodeTypes.REPORT)
class TriggerNode_Graph(ShapingNode):
    icon = "node_graph"
    node_code = ReportNodes.GRAPH
    node_type = NodeTypes.REPORT
    node_title = "Graph"
    content_class = GraphContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_graph"
    style = {}  # noqa: RUF012 - shared empty node style
