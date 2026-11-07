# SPDX-License-Identifier: Apache-2.0
# TEMPORARY probe (removed before merge): the real app's playback with and without the start-up guard.
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
import PySide6  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from pet_projection_data_visualization import _refcount_guard as guard  # noqa: E402

use_guard = sys.argv[1] == "guard"
if not use_guard:
    guard.protect_singletons = lambda: False          # what the app did before this fix
app = QtWidgets.QApplication([])
from pet_projection_data_visualization.app import build  # noqa: E402

print(f"python {sys.version.split()[0]} PySide6 {PySide6.__version__} guard={use_guard}", flush=True)
vm, win = build()
win.resize(1200, 800)
win.show()
vm.load_demo()
vm.set_playing(True)
for frame in range(1, 1001):
    vm.tick()
    win.repaint()
    app.processEvents()
    if frame % 100 == 0:
        print(f"frame {frame}: refcounts None/True/False {[sys.getrefcount(o) for o in guard.SINGLETONS]}",
              flush=True)
print("survived 1000 frames", flush=True)
os._exit(0)
