from ExecutionCheck.executor import NodeExecutor
from ExecutionCheck.exec_node import InputNode, PrintNode


class MainApp():
    def __init__(self) -> None:
        super().__init__()
        # Create Nodes
        node1 = InputNode("Input Node", 'input', 1000)
        node2 = PrintNode("Print Node", node1.variable_name)

        # Execution Manager
        executor = NodeExecutor()

        n1_out = executor.execute_node(node1)
        n2_out = executor.execute_node(node2)
        print(n1_out)
        print(n2_out)

        # self.output_area.setText(output)


if __name__ == "__main__":
    #     app = QApplication([])
    window = MainApp()
#     window.show()
#     app.exec_()
