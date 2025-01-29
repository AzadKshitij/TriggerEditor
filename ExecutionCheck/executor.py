import io
import sys


class NodeExecutor:
    def __init__(self):
        self.execution_context = {}  # Shared execution context

    def execute_node(self, node):
        """
        Executes a single node's code and returns its output.
        """
        output_buffer = io.StringIO()
        sys.stdout = output_buffer  # Redirect stdout to capture print output

        try:
            code = node.get_code()  # Each node should implement a get_code() method
            exec(code, self.execution_context)  # Execute in shared context
        except Exception as e:
            return f"Error in {node.title}: {str(e)}"
        finally:
            sys.stdout = sys.__stdout__  # Reset stdout

        return output_buffer.getvalue()
