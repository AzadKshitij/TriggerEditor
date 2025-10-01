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

        n1_result = executor.execute_node(node1)
        n2_result = executor.execute_node(node2)
        
        print(f"Node 1 - Success: {n1_result.success}")
        if n1_result.success:
            print(f"Node 1 Output: {n1_result.output}")
        else:
            print(f"Node 1 Error: {n1_result.error}")
            
        print(f"Node 2 - Success: {n2_result.success}")
        if n2_result.success:
            print(f"Node 2 Output: {n2_result.output}")
        else:
            print(f"Node 2 Error: {n2_result.error}")

        # self.output_area.setText(output)


if __name__ == "__main__":
    #     app = QApplication([])
    window = MainApp()
#     window.show()
#     app.exec_()
