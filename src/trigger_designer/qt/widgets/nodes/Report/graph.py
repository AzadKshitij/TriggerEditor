"""Graph node: a charting sink whose window opens after a run.

The Graph configures *what* to chart; the shared
:mod:`trigger_designer.core.charts` model decides what the data means, and
the window's renderer draws it: :class:`chart_view.ChartView` with
matplotlib by default, :class:`pyqtgraph_view.PyqtgraphChartView` on
request. The Config Dock has no preview: the window is the
chart, and its Show graph button stays disabled until a workflow run has
succeeded.

Two data paths feed the node:

* Evaluation sets ``incom_data`` and refreshes the column lists without ever
  clobbering a saved X/Y selection.
* A workflow run publishes the frame the node passed through over the
  ``runDataReady`` signal. The executor calls ``after_execution`` on the
  worker thread, so that hook only emits; the slot runs on the GUI thread and
  unlocks the window.

The generated code is data-only: it assigns the incoming frame to the node's
output variable. It never imports a plotting library, shows a window or writes
a file.
"""

from collections import OrderedDict
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
)

from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import QLineEdit, QVBoxLayout

from trigger_designer.core.charts import (
    ChartSpec,
    build_chart_spec,
    effective_aggregation,
)
from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    register_node,
)
from trigger_designer.qt.helpers import global_logger
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerGraphicsNode,
    TriggerNode,
    frame_schema,
    upstream_rename_map,
)
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    FormRow,
    IconButton,
    NoWheelComboBox,
)

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene


#: Display label -> stored value for the chart type combo.
_CHART_TYPE_ITEMS = (
    ("Line", "line"),
    ("Bar", "bar"),
    ("Scatter", "scatter"),
)

#: Display label -> stored value for the renderer combo. The values are the
#: library names themselves: there is no friendlier word for them, and the
#: tooltip has to describe the real difference anyway.
_RENDERER_ITEMS = (
    ("matplotlib", "matplotlib"),
    ("pyqtgraph", "pyqtgraph"),
)

#: The renderer every saved workflow drew with before this setting existed.
_DEFAULT_RENDERER = "matplotlib"

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

#: Color-by entry that clears the setting.
_NO_COLOR_LABEL = "(none)"

#: Open-window refresh debounce, matching the text/search pause of the design
#: system. Only an already-open window is refreshed; the dock previews nothing.
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


class GraphContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    evaluate = Signal()  # Emit when evaluate button is clicked
    #: Carries the frame a workflow run passed through the node. Emitted from
    #: the executor's worker thread; the connection below queues the slot onto
    #: the GUI thread, which is what makes ``after_execution`` widget-safe.
    runDataReady = Signal(object)

    serialized_state_schema: ClassVar[dict[str, Any]] = {
        "graph_type": {"default": "line"},
        "renderer": {"default": _DEFAULT_RENDERER},
        "x_column": {"default": ""},
        "y_column": {"default": ""},
        "title": {"default": ""},
        "color_column": {"default": ""},
        "aggregation": {"default": ""},
    }

    def __init__(
        self, node: TriggerNode, parent: QDMNodeIconContentWidget | None = None
    ) -> None:
        QDMNodeIconContentWidget.__init__(self, node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        self._node = node
        self.history = getattr(self.node.scene, "history", None)

        # Graph settings
        self.graph_type: str = "line"
        self.renderer: str = _DEFAULT_RENDERER
        self.x_column: str = ""
        self.y_column: str = ""
        self.color_column: str = ""
        self.aggregation: str = ""
        self.title: str = ""

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Any = None
        #: Frame handed over by the executor on its worker thread. Kept apart
        #: from ``incom_data`` so a run's result survives until the GUI slot
        #: and any dock rebuild have seen it.
        self._run_frame: Any = None
        self.workflow_ran_successfully = False

        # pass on variables
        self.data: Any = None
        self.variable_name = f"var_graph_{self.id}"

        self._refresh_timer: QTimer | None = None
        self._chart_window: Any | None = None
        self.runDataReady.connect(self._on_run_data_ready)

    @property
    def node(self) -> TriggerNode:
        return self._node

    @node.setter
    def node(self, value: TriggerNode) -> None:
        self._node = value

    def initUI(self, icon_=None) -> None:
        icon = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    # -- dock construction ----------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self.open_graph_button = None
        self.graph_section = None

        graph_section = ConfigSection()
        self.graph_section = graph_section

        # Show graph rides on the dock's label row (ConfigDock mounts
        # ``dock_actions()`` there) instead of spending a 30px row of its own.
        # It stays disabled until a run has produced the frame, so the dock
        # never offers a chart of data the workflow has not computed.
        self.open_graph_button = IconButton.themed(
            "Show graph",
            rsm_icon=self.node.rsm.get("icon_external"),
            qss_fallback=":/qss_icons/dark/rc/window_undock.png",
            theme_fallback="window-new",
        )
        self.open_graph_button.clicked.connect(self.open_graph_in_new_window)

        self.graph_type_combo = NoWheelComboBox()
        self.graph_type_combo.setMinimumHeight(30)
        self.graph_type_combo.addItems([label for label, _ in _CHART_TYPE_ITEMS])
        self.graph_type_combo.currentTextChanged.connect(self.on_graph_type_changed)
        graph_section.addWidget(FormRow("Type", self.graph_type_combo, label_width=72))

        self.renderer_combo = NoWheelComboBox()
        self.renderer_combo.setMinimumHeight(30)
        self.renderer_combo.addItems([label for label, _ in _RENDERER_ITEMS])
        self.renderer_combo.setToolTip(
            "Library that draws the chart window. pyqtgraph replaces the "
            "navigation toolbar with reset-view and save-PNG buttons."
        )
        self.renderer_combo.setAccessibleName("Chart renderer")
        self.renderer_combo.currentTextChanged.connect(self.on_renderer_changed)
        graph_section.addWidget(
            FormRow("Renderer", self.renderer_combo, label_width=72)
        )

        self.x_column_combo = NoWheelComboBox()
        self.x_column_combo.setMinimumHeight(30)
        self.x_column_combo.currentTextChanged.connect(self.on_x_column_changed)
        graph_section.addWidget(
            FormRow("X column", self.x_column_combo, label_width=72)
        )

        self.y_column_combo = NoWheelComboBox()
        self.y_column_combo.setMinimumHeight(30)
        self.y_column_combo.currentTextChanged.connect(self.on_y_column_changed)
        graph_section.addWidget(
            FormRow("Y column", self.y_column_combo, label_width=72)
        )

        self.color_column_combo = NoWheelComboBox()
        self.color_column_combo.setMinimumHeight(30)
        self.color_column_combo.currentTextChanged.connect(self.on_color_column_changed)
        graph_section.addWidget(
            FormRow("Color by", self.color_column_combo, label_width=72)
        )

        self.aggregation_combo = NoWheelComboBox()
        self.aggregation_combo.setMinimumHeight(30)
        self.aggregation_combo.addItems([label for label, _ in _AGGREGATION_ITEMS])
        self.aggregation_combo.currentTextChanged.connect(self.on_aggregation_changed)
        graph_section.addWidget(
            FormRow("Aggregate", self.aggregation_combo, label_width=72)
        )

        self.title_edit = QLineEdit()
        self.title_edit.setMinimumHeight(30)
        self.title_edit.setPlaceholderText("Chart title")
        self.title_edit.textChanged.connect(self.on_title_changed)
        graph_section.addWidget(FormRow("Title", self.title_edit, label_width=72))

        dock_layout.addWidget(graph_section)
        dock_layout.addStretch()

        self._sync_widgets_from_model()
        self._update_open_graph_button_state()
        self._refresh_graph_counts()

    def dock_actions(self) -> list:
        """One obvious action, mounted on the dock's label row."""
        button = getattr(self, "open_graph_button", None)
        return [button] if button is not None else []

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        """Configuration summary for the dock context strip."""
        chips: list[tuple[str, str]] = [(self.graph_type, "accent")]
        if self.renderer != _DEFAULT_RENDERER:
            chips.append((self.renderer, ""))
        if self.x_column and self.y_column:
            chips.append((f"{self.x_column} \u2192 {self.y_column}", ""))
        aggregation = effective_aggregation(self.graph_type, self.aggregation)
        if aggregation != "none":
            chips.append((aggregation, ""))
        if self.color_column:
            chips.append((f"by {self.color_column}", ""))
        return chips, self.title

    def _refresh_graph_counts(self) -> None:
        """Keep the section header count in step with the configuration."""
        self.refresh_dock_context()
        section = getattr(self, "graph_section", None)
        if section is None:
            return
        section.set_count(self.graph_type)

    # -- model -> widgets ------------------------------------------------
    def _sync_widgets_from_model(self) -> None:
        """Project every setting onto the live widgets without emitting.

        Called after a dock rebuild and after undo/redo restores. All writes
        are blocked, so a restore cannot look like a user edit (and the
        generic bindings never see a programmatic change).
        """
        self._set_combo_selection(
            getattr(self, "graph_type_combo", None),
            _label_for(_CHART_TYPE_ITEMS, self.graph_type, "Line"),
        )
        self._set_combo_selection(
            getattr(self, "renderer_combo", None),
            _label_for(_RENDERER_ITEMS, self.renderer, _DEFAULT_RENDERER),
        )
        self.update_column_options()
        self._sync_aggregation_widget()

        edit = getattr(self, "title_edit", None)
        if edit is not None:
            blocked = edit.blockSignals(True)
            try:
                edit.setText(self.title or "")
            finally:
                edit.blockSignals(blocked)

        self._refresh_graph_counts()

    def _sync_aggregation_widget(self) -> None:
        combo = getattr(self, "aggregation_combo", None)
        if combo is None:
            return
        effective = effective_aggregation(self.graph_type, self.aggregation)
        self._set_combo_selection(
            combo, _label_for(_AGGREGATION_ITEMS, effective, "None")
        )

    @staticmethod
    def _set_combo_selection(combo: NoWheelComboBox | None, label: str) -> None:
        if combo is None or not label:
            return
        index = combo.findText(label)
        if index < 0:
            return
        blocked = combo.blockSignals(True)
        try:
            combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(blocked)

    @staticmethod
    def _set_combo_items(
        combo: NoWheelComboBox | None, items: list[str], selected: str
    ) -> None:
        """Replace a combo's items without letting the change reach the model.

        The old code cleared and refilled the combos while their
        ``currentTextChanged`` handlers were connected, so every schema
        refresh overwrote the saved X and Y with the first column. Signals
        stay blocked here for exactly that reason.
        """
        if combo is None:
            return
        blocked = combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItems(items)
            if selected:
                index = combo.findText(selected)
                if index >= 0:
                    combo.setCurrentIndex(index)
            elif combo.count():
                combo.setCurrentIndex(0)
        finally:
            combo.blockSignals(blocked)

    def _frame_columns(self) -> list[str]:
        if self.incom_data is None:
            return []
        try:
            return list(frame_schema(self.incom_data))
        except Exception as exc:  # noqa: BLE001 - schema peek only
            global_logger.debug(f"Graph: cannot read incoming schema: {exc}")
            return []

    def _apply_rename_map(self, columns: list[str]) -> None:
        """Follow an upstream rename instead of treating it as a drop + add."""
        if not columns:
            return
        try:
            upstream = self.node.getInput(0)
        except Exception:  # noqa: BLE001 - node may be half-built
            upstream = None
        if upstream is None:
            return
        mapping = upstream_rename_map(upstream)
        if not mapping:
            return
        for attr in ("x_column", "y_column", "color_column"):
            current = getattr(self, attr, "")
            if current and current not in columns:
                renamed = mapping.get(current)
                if renamed in columns:
                    setattr(self, attr, renamed)

    def update_column_options(self) -> None:
        """Refresh the column combos from the incoming schema.

        Selections survive the refresh: a saved X/Y is kept whenever the
        column still exists and only falls back when it genuinely went away.
        With no incoming data the model is left alone entirely - a node can be
        selected before its upstream has evaluated, and blanking the saved
        columns there would lose configuration for good.
        """
        columns = self._frame_columns()
        if columns:
            self._apply_rename_map(columns)
            x = self.x_column if self.x_column in columns else columns[0]
            y = (
                self.y_column
                if self.y_column in columns
                else self._default_y(columns, x)
            )
            color = self.color_column if self.color_column in columns else ""
            self.x_column = x
            self.y_column = y
            self.color_column = color
        else:
            x, y, color = self.x_column, self.y_column, self.color_column

        self._set_combo_items(getattr(self, "x_column_combo", None), columns, x)
        self._set_combo_items(getattr(self, "y_column_combo", None), columns, y)
        color_label = color if color in columns else _NO_COLOR_LABEL
        self._set_combo_items(
            getattr(self, "color_column_combo", None),
            [_NO_COLOR_LABEL] + columns,
            color_label,
        )
        self._update_open_graph_button_state()
        self._schedule_window_refresh()

    @staticmethod
    def _default_y(columns: list[str], x_column: str) -> str:
        for column in columns:
            if column != x_column:
                return column
        return columns[0] if columns else ""

    def _update_open_graph_button_state(self) -> None:
        """Unlock Show graph only once a run has produced the frame.

        The window charts what the *run* computed, so a frame from a mere
        evaluation or a reload is not enough. The unlock latches for the
        lifetime of the node and is reset when a saved workflow is loaded.
        """
        button = getattr(self, "open_graph_button", None)
        if button is None:
            return
        has_data = self.incom_data is not None or self._run_frame is not None
        ready = (
            self.workflow_ran_successfully
            and has_data
            and bool(self.x_column)
            and bool(self.y_column)
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
    def build_spec(self) -> ChartSpec:
        """The chart the current settings and data produce."""
        return build_chart_spec(
            self.incom_data,
            chart_type=self.graph_type,
            x_column=self.x_column,
            y_column=self.y_column,
            color_column=self.color_column,
            aggregation=self.aggregation,
            title=self.title,
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

    def _window_title(self) -> str:
        """Window caption; a non-default renderer is named, per disclosure.

        matplotlib is what every pre-phase-7 workflow drew with, so its
        window keeps the old, unchanged caption.
        """
        base = f"Graph \u2014 {self.title}" if self.title else "Graph"
        if self.renderer != _DEFAULT_RENDERER:
            base += f" ({self.renderer})"
        return base

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
    def open_graph_in_new_window(self) -> None:
        """Open (or re-show) the non-modal chart window.

        Guarded on the run latch: the window charts what the workflow
        computed, not whatever a bare evaluation left in ``incom_data``. The
        click re-establishes the run's frame itself, so a dropped or late GUI
        signal can never make the button appear to do nothing.
        """
        if not self.workflow_ran_successfully:
            return
        if self.incom_data is None and self._run_frame is not None:
            self.incom_data = self._run_frame
        if not self.x_column or not self.y_column:
            # A run can complete before the dock ever listed the columns.
            self.update_column_options()
        window = getattr(self, "_chart_window", None)
        title = self._window_title()
        if window is not None:
            try:
                window.set_renderer(self.renderer)
                window.setWindowTitle(title)
            except RuntimeError:
                # Closed since the last click: build a fresh one.
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

    def on_graph_type_changed(self, label: str) -> None:
        value = _value_for(_CHART_TYPE_ITEMS, label, self.graph_type)
        if value != self.graph_type:
            self.graph_type = value
        self._sync_aggregation_widget()
        self._refresh_graph_counts()
        self._schedule_window_refresh()

    def on_renderer_changed(self, label: str) -> None:
        """Swap the drawing library; the open window rebuilds on the debounce.

        The renderer is not part of the chart's meaning, only of how the
        window draws and feels, so the model change is one attribute and the
        window swap rides the same 300 ms refresh as every other edit.
        """
        value = _value_for(_RENDERER_ITEMS, label, self.renderer)
        if value != self.renderer:
            self.renderer = value
            self._refresh_graph_counts()
            self._schedule_window_refresh()

    def on_x_column_changed(self, text: str) -> None:
        self.x_column = text
        self._refresh_graph_counts()
        self._schedule_window_refresh()

    def on_y_column_changed(self, text: str) -> None:
        self.y_column = text
        self._refresh_graph_counts()
        self._schedule_window_refresh()

    def on_color_column_changed(self, label: str) -> None:
        self.color_column = "" if label == _NO_COLOR_LABEL else label
        self._refresh_graph_counts()
        self._schedule_window_refresh()

    def on_aggregation_changed(self, label: str) -> None:
        self.aggregation = _value_for(_AGGREGATION_ITEMS, label, self.aggregation)
        self._refresh_graph_counts()
        self._schedule_window_refresh()

    def on_title_changed(self, text: str) -> None:
        self.title = text
        self._refresh_graph_counts()
        self._schedule_window_refresh()

    # -- run data --------------------------------------------------------
    def after_execution(self, context: dict[str, Any]) -> None:
        """Publish the frame the run passed through, from the worker thread.

        Runs inside ``NodeExecutor.execute_node`` on the workflow worker.
        No widget is touched here; the queued ``runDataReady`` slot does that
        on the GUI thread. The latch is set *here* as well as in that slot:
        the slot is queued, so it is skipped if this content is destroyed
        while the run finishes - and then the dock would show a button that
        stays locked no matter how often the workflow ran.
        """
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
            self.incom_data = frame
            self._run_frame = frame
        self.update_column_options()
        self._update_open_graph_button_state()

    # -- code generation --------------------------------------------------
    def get_code(self) -> str:
        if not self.incoming_variable:
            # Fallback: always define the output so downstream code never
            # NameErrors.
            return f"import polars as pl\n{self.variable_name} = pl.DataFrame()\n"
        return (
            "import polars as pl\n"
            "# Graph is a visualization sink: pass the frame through.\n"
            f"{self.variable_name} = {self.incoming_variable}\n"
        )

    # -- serialization ----------------------------------------------------
    def serialize(self) -> OrderedDict[Any, Any]:
        return self.serialize_content_state(super().serialize())

    def deserialize(
        self, data: dict, hashmap: dict | None = None, restore_id: bool | None = True
    ) -> bool:
        res = super().deserialize(data, hashmap if hashmap is not None else {})

        try:
            self.deserialize_content_state(data)
            self.workflow_ran_successfully = False
            self._run_frame = None
            self._sync_widgets_from_model()
            return True and res
        except Exception as e:  # noqa: BLE001 - a bad state must not abort the load
            dumpException(e)
        return res


@register_node(ReportNodes.GRAPH, NodeTypes.REPORT)
class TriggerNode_Graph(TriggerNode):
    icon = "node_graph"
    node_code = ReportNodes.GRAPH
    node_type = NodeTypes.REPORT
    node_title = "Graph"
    content_label_objname = "trigger_node_graph"
    style: ClassVar[dict] = {}

    def __init__(self, scene: Scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[3])

    def initInnerClasses(self) -> None:
        self.content: GraphContent = GraphContent(self)  # type: ignore
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)  # type: ignore
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values: list[Any]) -> list[dict] | None:
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        if input_node is None:
            return None
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]
        if input_value:
            data = input_value.get("data")
            self.content.incom_data = data
            self.content.incoming_variable = input_value.get("variable_name")
            self.content.data = data
            self.content.update_column_options()
            # The sink still forwards its input, so a downstream node sees the
            # frame the user charted instead of the old empty list.
            self.param = [{"data": data, "variable_name": self.content.variable_name}]
            return self.param
        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self):
        return self.content.get_code()
