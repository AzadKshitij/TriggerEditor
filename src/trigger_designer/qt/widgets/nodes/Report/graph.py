from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLayout,
    QComboBox,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QDialogButtonBox,
    QDialog,
    QColorDialog,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import (
    register_node,
    NodeTypes,
    ReportNodes,
)
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.node_node import Node
from nodeeditor.utils_no_qt import dumpException
import polars as pl
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    OrderedDict,
    Type,
    cast,
    Union,
)

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene


def _materialize_graph_data(
    incom_data: Optional[Union[pl.DataFrame, pl.LazyFrame]],
) -> Optional[pl.DataFrame]:
    if incom_data is None:
        return None
    if isinstance(incom_data, pl.LazyFrame):
        return incom_data.collect()
    return incom_data


def _create_graph_canvas(parent=None, width=5, height=4, dpi=100):
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    from matplotlib.figure import Figure

    class _MplCanvas(FigureCanvasQTAgg):
        def __init__(self, parent=None, width=5, height=4, dpi=100):
            fig = Figure(figsize=(width, height), dpi=dpi)
            self.axes = fig.add_subplot(111)
            super().__init__(fig)
            fig.tight_layout()

    return _MplCanvas(parent, width=width, height=height, dpi=dpi)


def _create_graph_toolbar(canvas, save_context, parent):
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT

    class _CustomNavigationToolbar(NavigationToolbar2QT):
        def __init__(self, canvas, save_context, parent):
            super().__init__(canvas, parent)
            self.save_context = save_context
            self.parent_widget = parent

        def save_figure(self, *args):
            file_choices = (
                "PNG (*.png)|*.png;PDF (*.pdf)|*.pdf;JPG (*.jpg)|*.jpg;SVG (*.svg)|*.svg"
            )
            path, ext = QFileDialog.getSaveFileName(
                self.save_context, "Save figure", "", file_choices
            )
            if path:
                self.canvas.figure.savefig(path)

    return _CustomNavigationToolbar(canvas, save_context, parent)


class GraphDialog(QDialog):
    def __init__(self, save_context, parent=None):
        super().__init__(save_context)
        self.setWindowTitle("Graph View")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.canvas = _create_graph_canvas(self, width=8, height=6, dpi=100)
        self.toolbar = _create_graph_toolbar(self.canvas, save_context, self)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)  # Add toolbar to the layout
        layout.addWidget(self.canvas)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def plot_graph(self, graph_type, x_column, y_column, title, incom_data):
        """Plot the graph based on the selected settings."""
        plot_data = _materialize_graph_data(incom_data)
        if plot_data is None or not x_column or not y_column:
            return
        if x_column not in plot_data.columns or y_column not in plot_data.columns:
            return

        # Clear the old plot
        self.canvas.axes.cla()

        # Plot the data
        try:
            x_data = plot_data.get_column(x_column).to_list()
            y_data = plot_data.get_column(y_column).to_list()
            if graph_type == "line":
                self.canvas.axes.plot(x_data, y_data)
            elif graph_type == "bar":
                self.canvas.axes.bar(x_data, y_data)
            elif graph_type == "scatter":
                self.canvas.axes.scatter(x_data, y_data)

            self.canvas.axes.set_xlabel(x_column)
            self.canvas.axes.set_ylabel(y_column)
            self.canvas.axes.set_title(title)
            self.canvas.axes.grid()
        except Exception as e:
            print(f"Error plotting graph: {e}")

        # Refresh the canvas
        self.canvas.draw()


class GraphContent(QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin):
    evaluate = Signal()  # Emit when evaluate button is clicked
    serialized_state_schema = {
        "graph_type": {"default": "line"},
        "x_column": {"default": ""},
        "y_column": {"default": ""},
        "title": {"default": ""},
    }

    def __init__(
        self, node: "TriggerNode", parent: Optional[QDMNodeIconContentWidget] = None
    ) -> None:
        # super().__init__(graph_node, parent)
        QDMNodeIconContentWidget.__init__(self, node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        self._node = node

        # local variables
        # Graph settings
        self.graph_type: str = "line"  # Default graph type
        self.x_column: str = ""
        self.y_column: str = ""
        self.title: str = ""

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[Union[pl.DataFrame, pl.LazyFrame]] = None
        self.workflow_ran_successfully = False

        # pass on variables
        self.data: list = []
        self.variable_name = f"var_graph_{self.id}"

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        # Graph Type Selection
        self.graph_type_combo = QComboBox()
        self.graph_type_combo.addItems(["line", "bar", "scatter"])
        self.graph_type_combo.currentTextChanged.connect(self.on_graph_type_changed)
        dock_layout.addWidget(QLabel("Graph Type:"))
        dock_layout.addWidget(self.graph_type_combo)

        # X Column Selection
        self.x_column_combo = QComboBox()
        self.x_column_combo.currentTextChanged.connect(self.on_x_column_changed)
        dock_layout.addWidget(QLabel("X Column:"))
        dock_layout.addWidget(self.x_column_combo)

        # Y Column Selection
        self.y_column_combo = QComboBox()
        self.y_column_combo.currentTextChanged.connect(self.on_y_column_changed)
        dock_layout.addWidget(QLabel("Y Column:"))
        dock_layout.addWidget(self.y_column_combo)

        # Graph Title Input
        self.title_edit = QLineEdit()
        self.title_edit.textChanged.connect(self.on_title_changed)
        dock_layout.addWidget(QLabel("Title:"))
        dock_layout.addWidget(self.title_edit)

        # Matplotlib Canvas
        # self.sc = MplCanvas(self, width=5, height=4, dpi=100)
        # dock_layout.addWidget(self.sc)
        # Add button to open graph in new window
        self.open_graph_button = QPushButton("Open Graph in New Window")
        self.open_graph_button.clicked.connect(self.open_graph_in_new_window)
        dock_layout.addWidget(self.open_graph_button)

        self.update_column_options()
        self._update_open_graph_button_visibility()

        # return layout

    def _update_open_graph_button_visibility(self) -> None:
        button = getattr(self, "open_graph_button", None)
        if button is None:
            return

        can_open_graph = self.workflow_ran_successfully and self.incom_data is not None
        button.setVisible(can_open_graph)
        button.setEnabled(can_open_graph)

    def update_column_options(self):
        """Update the column options in the combo boxes based on the incoming data."""
        if self.incom_data is not None:
            columns = list(self.incom_data.columns)
        else:
            columns = []

        if getattr(self, "x_column_combo", None) is not None:
            self.x_column_combo.clear()
            self.x_column_combo.addItems(columns)
        if getattr(self, "y_column_combo", None) is not None:
            self.y_column_combo.clear()
            self.y_column_combo.addItems(columns)

        self._update_open_graph_button_visibility()

    def plot_graph(self):
        """Plot the graph based on the selected settings."""
        if self.incom_data is None or not self.x_column or not self.y_column:
            return

        pass

    def open_graph_in_new_window(self):
        """Open the graph in a new window."""
        if not self.workflow_ran_successfully:
            return

        dialog = GraphDialog(parent=self, save_context=self.parent())
        dialog.plot_graph(
            self.graph_type, self.x_column, self.y_column, self.title, self.incom_data
        )
        dialog.exec_()

    def on_graph_type_changed(self, text):
        self.graph_type = text
        # self.plot_graph()

    def on_x_column_changed(self, text):
        self.x_column = text
        # self.plot_graph()

    def on_y_column_changed(self, text):
        self.y_column = text
        # self.plot_graph()

    def on_title_changed(self, text):
        self.title = text
        # self.plot_graph()

    def get_code(self) -> str:
        code_lines = [
            "import matplotlib.pyplot as plt",
            "import polars as pl",
            f"graph_df = {self.incoming_variable}.collect() if hasattr({self.incoming_variable}, 'collect') else {self.incoming_variable}",
            f"x_data = graph_df.get_column('{self.x_column}').to_list()",
            f"y_data = graph_df.get_column('{self.y_column}').to_list()",
            "plt.figure(figsize=(8, 6))",  # Adjust figure size as needed
        ]

        if self.graph_type == "line":
            code_lines.append("plt.plot(x_data, y_data)")
        elif self.graph_type == "bar":
            code_lines.append("plt.bar(x_data, y_data)")
        elif self.graph_type == "scatter":
            code_lines.append("plt.scatter(x_data, y_data)")

        code_lines.extend(
            [
                f"plt.xlabel('{self.x_column}')",
                f"plt.ylabel('{self.y_column}')",
                f"plt.title('{self.title}')",
                "plt.grid(True)",
                "plt.show()",
            ]
        )

        return "\n".join(code_lines)

    def after_execution(self, context: Dict[str, Any]) -> None:
        self.workflow_ran_successfully = True
        self._update_open_graph_button_visibility()
        self.plot_graph()

    def serialize(self) -> OrderedDict[Any, Any]:
        return self.serialize_content_state(super().serialize())

    def deserialize(
        self, data: dict, hashmap: dict = {}, restore_id: Optional[bool] = True
    ) -> bool:
        res = super().deserialize(data, hashmap)

        try:
            self.deserialize_content_state(data)
            self.workflow_ran_successfully = False
            self._update_open_graph_button_visibility()

            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(ReportNodes.GRAPH, NodeTypes.REPORT)
class TriggerNode_Graph(TriggerNode):
    icon = "node_graph"
    node_code = ReportNodes.GRAPH
    node_type = NodeTypes.REPORT
    node_title = "Graph"
    content_label_objname = "trigger_node_graph"
    style = {}

    def __init__(self, scene: "Scene") -> None:
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self) -> None:
        self.content: GraphContent = GraphContent(self)  # type: ignore
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)  # type: ignore
        self.content.evaluate.connect(self.onInputChanged)
        self.param: List = []

    def processInputs(self, input_values: list[Any]) -> Optional[List[Dict]]:
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        if input_node is None:
            return None
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]
        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.content.update_column_options()
            self.evalChildren()
            self.param = [
                {"data": self.content.data, "variable_name": self.content.variable_name}
            ]
            return self.param
        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self):
        return self.content.get_code()
