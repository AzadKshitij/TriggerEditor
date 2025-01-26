from qtpy.QtWidgets import QFileDialog


class FileDialogLogic:
    def __init__(self, parent):
        self.parent = parent

    def open_file_dialog(self, file_types: str):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(
            self.parent, "Open File", "", file_types, options=options)
        return fileName
