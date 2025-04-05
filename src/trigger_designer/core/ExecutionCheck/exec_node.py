class InputNode:
    def __init__(self, title, variable_name: str, value) -> None:
        self.title = title
        self.variable_name = variable_name
        self.value = value

    def get_code(self) -> str:
        return f"{self.variable_name} = {self.value}"


class PrintNode:
    def __init__(self, title, input_variable) -> None:
        self.title = title
        self.input_variable = input_variable

    def get_code(self) -> str:
        return f"print({self.input_variable})"
