import io
import sys
import threading

from trigger_designer.qt.helpers.logger import Logger


class NodeExecutor:
    def __init__(self, logger: Logger = None):
        self.execution_context = {}  # Shared execution context
        self.logger = logger
        # self.logger = logger

    def execute_node(self, node):
        """
        Executes a single node's code and returns its output.
        thread: 0.02495574951171875
        no_thread: 
        """
        # def run():
        code = node.get_code()
        output_buffer = io.StringIO()
        sys.stdout = output_buffer  # Redirect stdout to capture print output

        try:
            # code = code  # Each node should implement a get_code() method
            exec(code, self.execution_context)  # Execute in shared context
            exec(code, self.execution_context)
            # threading.Thread(target=lambda: exec(
            #     code, self.execution_context), daemon=True).start()
            self.logger.log(
                f" Executed Node {node.__class__.__name__}", "debug")

        except Exception as e:
            self.logger.log(
                f"Error in Node {node.__class__.__name__}: {e}", "error")
            return f"Error in {code}: {str(e)}"
        finally:
            sys.stdout = sys.__stdout__  # Reset stdout

        return output_buffer.getvalue()
