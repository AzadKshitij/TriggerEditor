from qtpy.QtWidgets import QDockWidget, QVBoxLayout, QLabel, QWidget, QLayout


class ConfigDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Node Configuration", parent)
        self.initUI()

    def initUI(self):
        self.configWidget = QWidget()
        # self.layout = QVBoxLayout()
        # self.configLabel = QLabel("Select a node to see its configuration")
        # self.layout.addWidget(self.configLabel)
        # self.configWidget.setLayout(self.layout)
        # self.setWidget(self.configWidget)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

    def updateConfig(self, node):
        if len(node) == 1:
            print("Node configuration:", node[0]._title)
            # self.configLabel.setText(f"Configuration for {node[0]._title}")
            # self.configLabel.setText(f"Configuration for {node[0].content}")
            # Add more configuration widgets based on the node's properties
            # Get the content from the node
            content = node[0].content
            print("------------")
            print(f"content: {content}")
            layout = content.layout
            print("***********")
            print(f"layout: {layout}")

            self.configWidget.setLayout(content.layout)
            self.setWidget(self.configWidget)

            # if isinstance(content.layout, QLayout):
            #     print("content.layout is a QLayout")

            # Use the content inside the Config Dock
            # if hasattr(content, 'initUI'):
            #     content.initUI(self)
            #     for i in reversed(range(content.layout.count())):
            #         print(f"content.layout.count {i}")
            # content.layout.itemAt(i).widget().setParent(None)
            # self.layout.addLayout(content.layout)

        # else:
        #     self.configLabel.setText("Select a node to see its configuration")
