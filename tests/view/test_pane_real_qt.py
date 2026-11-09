# SPDX-License-Identifier: Apache-2.0
"""The projection data pane of #36 in real PySide6 + pyqtgraph, offscreen: the level controls beside the
colour bar and the readout overlay (phase 4)."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from fakes import small_demo  # noqa: E402
from pet_projection_data_visualization.view.window import ViewerWindow  # noqa: E402
from pet_projection_data_visualization.viewmodel import Corner, LevelMode, ViewerViewModel  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def win(app):
    vm = ViewerViewModel(lambda o: o)
    w = ViewerWindow(vm)
    vm.load(small_demo())
    w.resize(1320, 840)
    w.show()
    app.processEvents()
    yield w
    w._timer.stop()
    w.close()


def _rect_in(widget, ancestor):
    top_left = widget.mapTo(ancestor, widget.rect().topLeft())
    return top_left.x(), top_left.y(), widget.width(), widget.height()


def test_the_level_controls_sit_beside_the_colour_bar(win):
    pane = win.pane
    glw_x, glw_y, glw_w, glw_h = _rect_in(pane.glw, win)
    panel_x, panel_y, _, panel_h = _rect_in(pane.level_panel, win)
    assert panel_x >= glw_x + glw_w                            # right of the image and its colour bar
    assert panel_y < glw_y + glw_h and panel_y + panel_h > glw_y
    hist_right = pane.glw.mapFromScene(pane.hist.sceneBoundingRect()).boundingRect().right()
    assert hist_right >= 0.8 * pane.glw.width()                # the colour bar is the right edge of the plot area
    _, high_y, _, _ = _rect_in(pane.level_edits["high"], win)
    _, low_y, _, _ = _rect_in(pane.level_edits["low"], win)
    assert high_y < low_y                                      # Max at the top, Min at the bottom, like the bar
    for w in (pane.level_control, pane.global_button, *pane.level_edits.values()):
        assert w.isVisible()


def test_the_level_controls_drive_the_pane(win, app):
    pane = win.pane
    pane.level_control._buttons[1].click()                      # Locked
    assert win.vm.pane.level_mode is LevelMode.LOCKED
    pane.level_edits["high"].setText("42")
    pane.level_edits["high"].editingFinished.emit()
    assert win.vm.pane.levels[1] == 42.0
    pane.global_button.click()
    assert win.vm.pane.level_mode is LevelMode.LOCKED
    pane.level_control._buttons[0].click()
    assert win.vm.pane.level_mode is LevelMode.ADAPTIVE


def _cursor_at(win, fx, fy):
    im = win.vm.pane.image
    win.vm.pane.hover_at(im.x0 + fx * im.width, im.y0 + fy * im.height)
    QtWidgets.QApplication.processEvents()


def test_the_readout_floats_over_the_image_and_avoids_the_cursor(win):
    pane = win.pane
    assert pane.readout.isHidden()                              # nothing under the cursor yet
    _cursor_at(win, 0.5, 0.5)
    assert pane.readout.isVisible() and "Segment" in pane.readout.text() and "Value" in pane.readout.text()
    box = pane.glw.mapFromScene(pane.plot.vb.sceneBoundingRect()).boundingRect()
    geo = pane.readout.geometry()
    assert box.contains(geo.topLeft()) and box.contains(geo.bottomRight())     # inside the image
    assert geo.center().x() > box.center().x() and geo.center().y() < box.center().y()   # top right
    _cursor_at(win, 0.95, 0.05)                                 # the cursor comes close: it moves left
    assert win.vm.pane.readout_corner is Corner.TOP_LEFT
    geo = pane.readout.geometry()
    assert geo.center().x() < box.center().x() and geo.center().y() < box.center().y()
    win.vm.pane.hover_leave()
    assert pane.readout.isHidden()


def test_the_readout_lets_the_mouse_through(win):
    from PySide6 import QtCore
    assert win.pane.readout.testAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
