import io
import sys
import threading


class NodeExecutor:
    def __init__(self):
        self.execution_context = {}  # Shared execution context
        # self.logger = logger

    def execute_node(self, code):
        """
        Executes a single node's code and returns its output.
        """
        def run():
            output_buffer = io.StringIO()
            sys.stdout = output_buffer  # Redirect stdout to capture print output

            try:
                code = code  # Each node should implement a get_code() method
                print(code)
                exec(code, self.execution_context)  # Execute in shared context
            except Exception as e:
                # self.logger.log(f"Error in Node {index+1}: {e}")
                return f"Error in {code}: {str(e)}"
            finally:
                sys.stdout = sys.__stdout__  # Reset stdout

            return output_buffer.getvalue()

        threading.Thread(target=run, daemon=True).start()
