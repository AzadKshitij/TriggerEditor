from typing import Optional, Dict
import pandas as pd
import numpy as np
from qtpy.QtWidgets import (QWidget, QVBoxLayout, QLabel, QGroupBox,
                            QSpinBox, QHBoxLayout)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal, Qt
from trigger_designer.core.node_configuration import register_node, PreparationNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException


class SplitContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Split data into estimation, validation, and holdout samples.

    Features:
    - Configurable estimation and validation percentages
    - Random seed for reproducibility
    - Automatic holdout calculation
    - Maintains data integrity
    """

    evaluate = Signal()

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        self.node = node

        # Data tracking
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None
        # Combined estimation + validation
        self.main_data: Optional[pd.DataFrame] = None
        self.holdout_data: Optional[pd.DataFrame] = None

        # Configuration
        self.main_percent: int = 80  # Total percentage for main data
        self.random_seed: int = 1

        # Variable names for outputs
        self.main_var = f'var_main_{self.id}'
        self.holdout_var = f'var_holdout_{self.id}'

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon_: QPixmap = self.node.rsm.get(f'{self.node.icon}')
        super().initUI(icon_)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            # Outer layout
            outer_layout = QVBoxLayout()
            outer_layout.setSpacing(2)
            outer_layout.setContentsMargins(5, 5, 5, 5)

            # Sample Size Controls
            size_group = QGroupBox("Sample Size")
            size_layout = QVBoxLayout()

            # Main percentage
            percent_layout = QHBoxLayout()  # Changed from main_layout to percent_layout
            main_label = QLabel("Main Data %:")
            self.main_spin = QSpinBox()
            self.main_spin.setRange(1, 99)
            self.main_spin.setValue(self.main_percent)
            self.main_spin.valueChanged.connect(self.on_main_changed)
            percent_layout.addWidget(main_label)
            percent_layout.addWidget(self.main_spin)
            size_layout.addLayout(percent_layout)

            # Random seed
            seed_layout = QHBoxLayout()
            seed_label = QLabel("Random Seed:")
            self.seed_spin = QSpinBox()
            self.seed_spin.setRange(1, 1000)
            self.seed_spin.setValue(self.random_seed)
            self.seed_spin.valueChanged.connect(self.on_seed_changed)
            seed_layout.addWidget(seed_label)
            seed_layout.addWidget(self.seed_spin)
            size_layout.addLayout(seed_layout)

            size_group.setLayout(size_layout)
            outer_layout.addWidget(size_group)

            dock_layout.addLayout(outer_layout)

        else:
            no_data_label = QLabel('No incoming data available')
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet('color: gray;')
            dock_layout.addWidget(no_data_label)

    def get_code(self) -> str:
        """Generate code for split operation"""
        if self.incom_data is None or self.incoming_variable is None:
            return "print('No data available for split operation')\n"

        code_lines = [
            f"import numpy as np",
            f"# Set random seed and shuffle indices",
            f"np.random.seed({self.random_seed})",
            f"n_rows = len({self.incoming_variable})",
            f"indices = np.random.permutation(n_rows)",
            f"",
            f"# Calculate split size",
            f"main_size = int(np.ceil(n_rows * {self.main_percent} / 100))",
            f"",
            f"# Create samples",
            f"{self.main_var} = {self.incoming_variable}.iloc[indices[:main_size]].copy()",
            f"{self.holdout_var} = {self.incoming_variable}.iloc[indices[main_size:]].copy()"
        ]

        return "\n".join(code_lines) + "\n"

    def on_estimation_changed(self, value: int) -> None:
        """Handle estimation percentage changes"""
        self.estimation_percent = value
        # self.process_data()
        self.evaluate.emit()

    def on_validation_changed(self, value: int) -> None:
        """Handle validation percentage changes"""
        self.validation_percent = value
        # self.process_data()
        self.evaluate.emit()

    def on_seed_changed(self, value: int) -> None:
        """Handle random seed changes"""
        self.random_seed = value
        # self.process_data()
        self.evaluate.emit()

    def on_main_changed(self, value: int) -> None:
        """Handle main data percentage changes"""
        self.main_percent = value
        # self.process_data()
        self.evaluate.emit()

    def serialize(self) -> dict:
        """Serialize node content"""
        res = super().serialize()
        res.update({
            'main_percent': self.main_percent,
            'random_seed': self.random_seed
        })
        return res

    def deserialize(self, data: dict, hashmap={}) -> bool:
        """Deserialize node content"""
        res = super().deserialize(data, hashmap)
        try:
            self.main_percent = data.get('main_percent', 80)
            self.random_seed = data.get('random_seed', 1)
            return True & res
        except Exception as e:
            dumpException(e)
            return res


@register_node(PreparationNodes.SPLIT, NodeTypes.PREPARATION)
class TriggerNode_Split(TriggerNode):
    icon = "node_split"
    node_code = PreparationNodes.SPLIT
    node_title = "Split"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_split"

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[
            3, 3], output_text=['E', 'H'])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content: SplitContent = SplitContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)

            self.content.incom_data = input_value.get('data')
            print("🐍 File: Preparation/split.py:187 | processInputs ~ input_value.get('data')",
                  input_value.get('data'))
            self.content.incoming_variable = input_value.get('variable_name')

            self.evalChildren()
            self.param = [
                {'data': self.content.main_data,
                 'variable_name': self.content.main_var},
                {'data': self.content.holdout_data,
                 'variable_name': self.content.holdout_var}
            ]
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return None

    def get_code(self) -> str:
        """Generate code for split operation"""
        return self.content.get_code()
