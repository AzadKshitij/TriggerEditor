import io
import sys
import threading

from trigger_designer.qt.helpers.logger import Logger


class NodeExecutor:
    def __init__(self, logger: Logger = None) -> None:
        self.execution_context: dict = {}  # Shared execution context
        self.logger = logger
        # self.logger = logger

    def execute_node(self, node) -> str:
        """
        Executes a single node's code and returns its output.
        """
        # def run():
        code: str = node.get_code()
        output_buffer: io.StringIO = io.StringIO()
        sys.stdout = output_buffer  # Redirect stdout to capture print output
        if not self.logger:
            self.logger = Logger()
        try:
            # code = code  # Each node should implement a get_code() method
            exec(code, self.execution_context)  # Execute in shared context
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
