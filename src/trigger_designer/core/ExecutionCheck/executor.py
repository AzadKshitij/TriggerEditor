import io
import sys
import threading
from typing import Any, Optional, Dict, TYPE_CHECKING, Tuple

from trigger_designer.qt.helpers.logger import Logger

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class NodeExecutionError(Exception):
    """Custom exception for node execution errors."""
    pass


class NodeExecutor:
    def __init__(self, logger: Optional[Logger] = None) -> None:
        self.execution_context: Dict[str, Any] = {}  # Shared execution context
        self.logger = logger or Logger()
        # self.logger = logger

    def execute_node(self, node: 'TriggerNode') -> Tuple[str, dict[str, Any]]:
        """
        Executes a single node's code and returns its output.
        """
        # def run():
        code: str = node.get_code()
        output_buffer: io.StringIO = io.StringIO()
        sys.stdout = output_buffer  # Redirect stdout to capture print output

        local_variables: dict = {}

        if not self.logger:
            self.logger = Logger()
        try:
            exec(code, self.execution_context, local_variables)
            self.logger.log(
                f" Executed Node {node.__class__.__name__}", "debug")

        except Exception as e:
            self.logger.log(
                f"Error in Node {node.__class__.__name__}: {e}", "error")
            # raise NodeExecutionError(
            #     f"Error in Node {node.__class__.__name__}: {e}")
            return f"Error in Node {node.__class__.__name__}: {e}", self.execution_context
        finally:
            sys.stdout = sys.__stdout__  # Reset stdout

        self.execution_context.update(local_variables)

        return output_buffer.getvalue(), local_variables
