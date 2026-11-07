# TEMPORARY probe (removed before merge): where does None's refcount go on Python 3.11?
import gc
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RESERVE = [None] * 5_000_000          # so a decreasing count cannot abort the probe itself

import numpy as np  # noqa: E402
import PySide6  # noqa: E402
import pyqtgraph as pg  # noqa: E402
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

app = QtWidgets.QApplication([])
print(f"python {sys.version.split()[0]} {sys.platform} PySide6 {PySide6.__version__} pyqtgraph {pg.__version__} "
      f"numpy {np.__version__}", flush=True)


def m(label, fn, n=200):
    for _ in range(3):
        fn()
    gc.collect()
    r0 = sys.getrefcount(None)
    for _ in range(n):
        fn()
    gc.collect()
    print(f"  {label:44s} per call {(sys.getrefcount(None) - r0) / n:+.2f}", flush=True)


class Item(QtWidgets.QGraphicsItem):
    def boundingRect(self):
        return QtCore.QRectF(0, 0, 10, 10)

    def paint(self, p, opt, widget=None):
        pass


class Obj(QtWidgets.QGraphicsObject):
    def boundingRect(self):
        return QtCore.QRectF(0, 0, 10, 10)

    def paint(self, p, *args):
        return None


scene = QtWidgets.QGraphicsScene()
view = QtWidgets.QGraphicsView(scene)
for cls in (Item, Obj):
    scene.addItem(cls())
view.resize(200, 200)
view.show()
app.processEvents()
m("plain QGraphicsView grab, 2 py paint()", view.grab)
m("plain QGraphicsView repaint", lambda: view.viewport().repaint())

img = QtGui.QImage(200, 200, QtGui.QImage.Format.Format_ARGB32)
painter = QtGui.QPainter(img)
m("np.dtype(tuple)", lambda: np.dtype(tuple))
m("pg.mkColor((0,0,0,100))", lambda: pg.mkColor((0, 0, 0, 100)))
m("pg.mkPen('r')", lambda: pg.mkPen("r"))

for what in ("plot", "image", "hist", "curve", "region"):
    w = pg.GraphicsLayoutWidget()
    if what == "plot":
        w.addPlot()
    elif what == "image":
        w.addPlot().addItem(pg.ImageItem(np.random.rand(16, 16)))
    elif what == "hist":
        w.addItem(pg.HistogramLUTItem())
    elif what == "curve":
        w.addPlot().plot(np.arange(5.0), np.arange(5.0), symbol="o")
    elif what == "region":
        w.addPlot().addItem(pg.LinearRegionItem((1, 2)))
    w.resize(400, 300)
    w.show()
    app.processEvents()
    m(f"pyqtgraph {what}: grab", w.grab, 100)
    m(f"pyqtgraph {what}: viewport repaint", lambda: w.viewport().repaint(), 100)
    w.close()

h = pg.HistogramLUTItem()
m("HistogramLUTItem.paint called from Python", lambda: h.paint(painter, None, None))
painter.end()

# the application itself: demo data, locked levels, playback with a repaint per frame
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from pet_projection_data_visualization.app import build  # noqa: E402

vm, win = build()
win.resize(1200, 800)
win.show()
vm.load_demo()
app.processEvents()
vm.set_playing(True)


def frame():
    vm.tick()
    win.repaint()
    app.processEvents()


m("app: one playback frame (tick + repaint)", frame, 200)
vm.set_playing(False)
m("app: step view (Right) + repaint", lambda: (vm.step_active(1), win.repaint(), app.processEvents()), 200)
print(f"  None refcount now {sys.getrefcount(None)} (reserve {len(RESERVE)})", flush=True)
os._exit(0)
