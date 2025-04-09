from qtpy.QtWidgets import (QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget,
                            QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout, QDialogButtonBox, QDialog, QColorDialog)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import register_node, NodeTypes, ReportNodes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.node_node import Node
from nodeeditor.utils import dumpException
from typing import TYPE_CHECKING, Any, Dict, List, Optional, OrderedDict, Type, cast, Union

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    import pandas as pd


class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        fig.tight_layout()


class CustomNavigationToolbar(NavigationToolbar):

    def __init__(self, canvas, save_context, parent):
        super().__init__(canvas, parent)
        self.save_context = save_context
        self.parent_widget = parent

    # def edit_parameters(self):
    #     # Show a color selection dialog, parented to the graph dialog
    #     color = QColorDialog.getColor(
    #         parent=self.parent_widget)  # Use parent_widget

    #     if color.isValid():
    #         # Change the facecolor of the axes
    #         self.canvas.axes.set_facecolor(color.name())
    #         self.canvas.draw()

    def save_figure(self, *args):
        file_choices = "PNG (*.png)|*.png;PDF (*.pdf)|*.pdf;JPG (*.jpg)|*.jpg;SVG (*.svg)|*.svg"
        path, ext = QFileDialog.getSaveFileName(
            self.save_context, 'Save figure', '', file_choices)
        if path:
            self.canvas.figure.savefig(path)


class GraphDialog(QDialog):
    def __init__(self, save_context,  parent=None):
        super().__init__(save_context)
        self.setWindowTitle("Graph View")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.canvas = MplCanvas(self, width=8, height=6, dpi=100)
        self.toolbar = CustomNavigationToolbar(
            self.canvas, save_context, self)  # Add the toolbar
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)  # Add toolbar to the layout
        layout.addWidget(self.canvas)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def plot_graph(self, graph_type, x_column, y_column, title, incom_data):
        """Plot the graph based on the selected settings."""
        if incom_data is None or not x_column or not y_column:
            return

        # Clear the old plot
        self.canvas.axes.cla()

        # Plot the data
        try:
            if graph_type == 'line':
                self.canvas.axes.plot(
                    incom_data[x_column], incom_data[y_column])
            elif graph_type == 'bar':
                self.canvas.axes.bar(
                    incom_data[x_column], incom_data[y_column])
            elif graph_type == 'scatter':
                self.canvas.axes.scatter(
                    incom_data[x_column], incom_data[y_column])

            self.canvas.axes.set_xlabel(x_column)
            self.canvas.axes.set_ylabel(y_column)
            self.canvas.axes.set_title(title)
            self.canvas.axes.grid()
        except Exception as e:
            print(f"Error plotting graph: {e}")

        # Refresh the canvas
        self.canvas.draw()


class GraphContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: 'TriggerNode', parent: Optional[QDMNodeIconContentWidget] = None) -> None:
        # super().__init__(graph_node, parent)
        QDMNodeIconContentWidget.__init__(self, node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        self._node = node

        # local variables
        # Graph settings
        self.graph_type: str = 'line'  # Default graph type
        self.x_column: str = ''
        self.y_column: str = ''
        self.title: str = ''

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None

        # pass on variables
        self.data: list = []
        self.variable_name = f'var_graph_{self.id}'

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        # Graph Type Selection
        self.graph_type_combo = QComboBox()
        self.graph_type_combo.addItems(['line', 'bar', 'scatter'])
        self.graph_type_combo.currentTextChanged.connect(
            self.on_graph_type_changed)
        dock_layout.addWidget(QLabel("Graph Type:"))
        dock_layout.addWidget(self.graph_type_combo)

        # X Column Selection
        self.x_column_combo = QComboBox()
        self.x_column_combo.currentTextChanged.connect(
            self.on_x_column_changed)
        dock_layout.addWidget(QLabel("X Column:"))
        dock_layout.addWidget(self.x_column_combo)

        # Y Column Selection
        self.y_column_combo = QComboBox()
        self.y_column_combo.currentTextChanged.connect(
            self.on_y_column_changed)
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

        # return layout

    def update_column_options(self):
        """Update the column options in the combo boxes based on the incoming data."""
        if self.incom_data is not None:
            columns = list(self.incom_data.columns)
        else:
            columns = []

        if getattr(self, 'x_column_combo', None) is not None:
            self.x_column_combo.clear()
            self.x_column_combo.addItems(columns)
        if getattr(self, 'y_column_combo', None) is not None:
            self.y_column_combo.clear()
            self.y_column_combo.addItems(columns)

    def plot_graph(self):
        """Plot the graph based on the selected settings."""
        if self.incom_data is None or not self.x_column or not self.y_column:
            return

        pass

    def open_graph_in_new_window(self):
        """Open the graph in a new window."""
        dialog = GraphDialog(parent=self, save_context=self.parent())
        dialog.plot_graph(self.graph_type, self.x_column, self.y_column,
                          self.title, self.incom_data)
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
            f"x_data = {self.incoming_variable}['{self.x_column}']",
            f"y_data = {self.incoming_variable}['{self.y_column}']",
            "plt.figure(figsize=(8, 6))",  # Adjust figure size as needed
        ]

        if self.graph_type == 'line':
            code_lines.append("plt.plot(x_data, y_data)")
        elif self.graph_type == 'bar':
            code_lines.append("plt.bar(x_data, y_data)")
        elif self.graph_type == 'scatter':
            code_lines.append("plt.scatter(x_data, y_data)")

        code_lines.extend([
            f"plt.xlabel('{self.x_column}')",
            f"plt.ylabel('{self.y_column}')",
            f"plt.title('{self.title}')",
            "plt.grid(True)",
            "plt.show()"
        ])

        return "\n".join(code_lines)

    def after_execution(self, context: Dict[str, Any] = None) -> None:
        self.plot_graph()

    def serialize(self) -> OrderedDict[Any, Any]:
        res = super().serialize()
        res["graph_type"] = self.graph_type
        res["x_column"] = self.x_column
        res["y_column"] = self.y_column
        res["title"] = self.title
        return res

    def deserialize(self, data: dict, hashmap: dict = {}, restore_id: Optional[bool] = True) -> bool:
        res = super().deserialize(data, hashmap)

        try:
            # self.filePath = data.get('filePath', "")
            self.graph_type = data.get('graph_type', 'line')
            self.x_column = data.get('x_column', '')
            self.y_column = data.get('y_column', '')
            self.title = data.get('title', '')

            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(ReportNodes.GRAPH, NodeTypes.REPORT)
class TriggerNode_Graph(TriggerNode):
    icon = "node_file_input"
    node_code = ReportNodes.GRAPH
    node_type = NodeTypes.REPORT
    node_title = "Graph"
    content_label_objname = "trigger_node_node_title"
    style = {}

    def __init__(self, scene: 'Scene') -> None:
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self) -> None:
        self.content: GraphContent = GraphContent(self)  # type: ignore
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(
            self)  # type: ignore
        self.content.evaluate.connect(self.onInputChanged)

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
            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')
            self.content.update_column_options()
            self.evalChildren()
            return [{
                'data': self.content.data,
                'variable_name': self.content.variable_name
            }]
        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return None

    def get_code(self):
        return self.content.get_code()
