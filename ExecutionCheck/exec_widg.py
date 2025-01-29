from PyQt5.QtWidgets import QPushButton, QTextEdit, QVBoxLayout, QWidget


class NodeExecutionWidget(QWidget):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.executor = NodeExecutor()  # Shared across nodes

        self.execute_button = QPushButton(f"Run {node.title}")
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.execute_button)
        layout.addWidget(self.output_area)
        self.setLayout(layout)

        self.execute_button.clicked.connect(self.run_code)

    def run_code(self):
        output = self.executor.execute_node(self.node)
        self.output_area.setText(output)
