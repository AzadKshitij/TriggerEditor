"""Phase 0 spike: build the target layout with QtAds over a QMdiArea."""
import sys

import PySide6QtAds as QtAds
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QMdiArea, QTextEdit

offscreen = "--offscreen" in sys.argv
if offscreen:
    import os

    os.environ["QT_QPA_PLATFORM"] = "offscreen"

app = QApplication([])
win = QMainWindow()
QtAds.CDockManager.setConfigFlags(
    QtAds.CDockManager.DefaultOpaqueConfig
    | QtAds.CDockManager.DragPreviewHasWindowFrame
)
mgr = QtAds.CDockManager(win)
win.setCentralWidget(mgr)

mdi = QMdiArea()
mdi.setViewMode(QMdiArea.ViewMode.TabbedView)
canvas = QtAds.CDockWidget("Workflow")
canvas.setWidget(mdi)
canvas.setFeature(QtAds.CDockWidget.DockWidgetFeature.NoTab, True)
central = mgr.setCentralWidget(canvas)

def dock(title, widget):
    d = QtAds.CDockWidget(title)
    d.setWidget(widget)
    return d

config = dock("Node Configuration", QLabel("config"))
logs, preview, history = (dock(n, QTextEdit(n)) for n in ("Logs", "Data Preview", "Run History"))

left = mgr.addDockWidget(QtAds.LeftDockWidgetArea, config)           # full height
bottom = mgr.addDockWidget(QtAds.BottomDockWidgetArea, logs, central)  # under canvas only
mgr.addDockWidgetTabToArea(preview, bottom)
mgr.addDockWidgetTabToArea(history, bottom)

state = mgr.saveState()
print("state bytes:", len(state))
win.resize(1200, 800)
win.show()
app.processEvents()
print("config area h:", left.height(), "window h:", win.height())
print("canvas area:", central.geometry(), "bottom area:", bottom.geometry())
ok = left.height() > bottom.height() * 1.5 and bottom.y() > central.y()
print("TARGET LAYOUT:", "OK" if ok else "FAIL")
print("restore:", mgr.restoreState(state))
if not offscreen:
    app.exec()
