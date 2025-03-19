class Logger:
    def __init__(self):
        self.logs = []
        self.result_dock = None

    def set_result_dock(self, result_dock):
        self.result_dock = result_dock

    def log(self, message, log_type='info'):
        log_entry = {'message': message, 'type': log_type}
        self.logs.append(log_entry)
        print("self.result_dock")
        print(self.result_dock)
        print("self.result_dock")
        if self.result_dock:
            self.result_dock.add_log(message, log_type)

    def get_logs(self):
        return "\n".join([f"[{log['type'].upper()}] {log['message']}" for log in self.logs])

    def clear_logs(self):
        self.logs = []
        if self.result_dock:
            self.result_dock.clear_logs()
