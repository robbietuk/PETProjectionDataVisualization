# SPDX-License-Identifier: Apache-2.0
"""A long playback session in the real window: hundreds of repaints of the image, colour bar and TOF plot.

On Linux with Python 3.11 and PySide6 6.12.0 (forced in one CI job) each repaint gives back references to
None/True/False that PySide6 never took; without the start-up guard (_refcount_guard.py) this test aborted
the interpreter. It also checks that locked levels hold over a long session.
"""
import os
import sys

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from pet_projection_data_visualization import _refcount_guard as guard  # noqa: E402
from pet_projection_data_visualization.app import build  # noqa: E402

FRAMES = 300


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_long_locked_playback_repaints_without_losing_none_true_or_false(app):
    vm, win = build()
    try:
        win.resize(1200, 800)
        win.show()
        assert vm.load_demo()
        vm.pane.toggle_level_lock()
        app.processEvents()
        bar = (tuple(win.pane.hist.getLevels()), tuple(win.pane.hist.getHistogramRange()))
        before = [sys.getrefcount(o) for o in guard.SINGLETONS]
        vm.pane.set_playing(True)
        for _ in range(FRAMES):
            vm.pane.tick()
            win.repaint()
            app.processEvents()
        vm.pane.set_playing(False)
        assert (tuple(win.pane.hist.getLevels()), tuple(win.pane.hist.getHistogramRange())) == bar
        if guard.needs_guard():
            after = [sys.getrefcount(o) for o in guard.SINGLETONS]
            assert all(a > guard.EXTRA_REFERENCES // 2 for a in after), (before, after)
    finally:
        win._timer.stop()
        win.close()
