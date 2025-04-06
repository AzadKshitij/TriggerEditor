from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trigger_designer.qt.docks.result import ResultDock


class Logger:
    def __init__(self) -> None:
        self.logs: list[dict] = list()
        self.result_dock: 'ResultDock'

    def set_result_dock(self, result_dock: 'ResultDock') -> None:
        self.result_dock = result_dock

    def log(self, message: str, log_type: str = 'info') -> None:
        # log_entry = {'message': message, 'type': log_type}
        # self.logs.append(log_entry)
        # print("self.result_dock")
        # print(self.result_dock)
        # print("self.result_dock")
        if self.result_dock:
            self.result_dock.add_log(message, log_type)

    def get_logs(self):
        return "\n".join([f"[{log['type'].upper()}] {log['message']}" for log in self.logs])

    def clear_logs(self) -> None:
        self.logs = []
        if self.result_dock:
            self.result_dock.clear_logs()
