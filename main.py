from trigger_window import TriggerWindow
import os
import sys
from qtpy.QtWidgets import QApplication, QStyleFactory

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


if __name__ == '__main__':
    app = QApplication(sys.argv)

    print(QStyleFactory.keys())
    app.setStyle('windows11')

    wnd = TriggerWindow()
    wnd.show()

    sys.exit(app.exec_())
