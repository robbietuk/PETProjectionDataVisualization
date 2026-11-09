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


# ---- profiles (phase 5) --------------------------------------------------------------------------
class _Click:
    """What pyqtgraph's scene hands ``sigMouseClicked`` listeners."""

    def __init__(self, scene_pos, button=None, double=False):
        from PySide6 import QtCore
        self._pos, self._double = scene_pos, double
        self._button = QtCore.Qt.MouseButton.LeftButton if button is None else button

    def scenePos(self):
        return self._pos

    def button(self):
        return self._button

    def double(self):
        return self._double


def _click_image(win, x, y, **kw):
    from PySide6 import QtCore
    scene_pos = win.pane.plot.vb.mapViewToScene(QtCore.QPointF(x, y))
    win.pane._on_mouse_clicked(_Click(scene_pos, **kw))
    QtWidgets.QApplication.processEvents()


def test_a_click_on_the_image_freezes_and_marks_it_and_esc_releases(win):
    from PySide6 import QtCore
    pane = win.pane
    _click_image(win, -3.0, 4.0, button=QtCore.Qt.MouseButton.RightButton)   # only the left button
    _click_image(win, -3.0, 4.0, double=True)
    assert win.vm.pane.frozen_at is None
    _click_image(win, -3.0, 4.0)
    assert win.vm.pane.frozen_at == (-3.0, 4.0)
    assert [(p.pos().x(), p.pos().y()) for p in pane.freeze_marker.points()] == [(-3.0, 4.0)]
    assert "FROZEN" in pane.tof_dock.title_label.text()
    win.rail.open("display")
    win._on_escape()                                     # Esc closes an open flyout first ...
    assert win.rail.open_flyout is None and win.vm.pane.frozen_at == (-3.0, 4.0)
    win._on_escape()                                     # ... then releases the profiles
    assert win.vm.pane.frozen_at is None and len(pane.freeze_marker.points()) == 0
    assert "CURSOR" in pane.tof_dock.title_label.text()


def test_f_freezes_and_releases_from_the_keyboard(win):
    from PySide6 import QtCore
    win.dim_controls["tof"].play_button.setFocus()
    win._on_shortcut(QtCore.Qt.Key.Key_F)
    assert win.vm.pane.frozen_at is not None
    win._on_shortcut(QtCore.Qt.Key.Key_F)
    assert win.vm.pane.frozen_at is None


def test_collapsed_tof_draws_the_profile_as_context_with_a_reference_line(win):
    pane = win.pane
    _cursor_at(win, 0.5, 0.4)
    assert pane.tof_marker_line.isVisible() and pane.tof_context.isHidden() and not pane.tof_reference_line.isVisible()
    win.tof_mode_control._buttons[1].click()            # Sum
    QtWidgets.QApplication.processEvents()
    assert not pane.tof_marker_line.isVisible() and pane.tof_reference_line.isVisible()
    assert pane.tof_context.isVisible() and "the image shows their Sum" in pane.tof_context.text()
    assert pane.tof_reference_line.value() == pytest.approx(win.vm.pane.tof_profile.reference)


def test_the_line_profile_plots_row_column_and_free(win):
    pane = win.pane
    _cursor_at(win, 0.5, 0.4)
    assert pane.line_curve.getData()[1] is not None and len(pane.line_curve.getData()[1]) == 15   # tangential bins
    assert pane.line_plot.getPlotItem().getAxis("bottom").labelText == "tangential"
    tips = [b.toolTip() for b in pane.line_mode_control._buttons]
    assert tips[:2] == ["Along tangential", "Along view"]
    assert not pane.free_roi.isVisible()
    pane.line_mode_control._buttons[2].click()          # Free
    QtWidgets.QApplication.processEvents()
    assert pane.free_roi.isVisible()
    x0, y0, x1, y1 = win.vm.pane.free_line
    ends = [pane.free_roi.mapToParent(h.pos()) for h in pane.free_roi.getHandles()]
    assert [c for p in ends for c in (p.x(), p.y())] == pytest.approx([x0, y0, x1, y1])
    from PySide6 import QtCore
    pane.free_roi.movePoint(pane.free_roi.getHandles()[1], QtCore.QPointF(x1 - 2.0, y0))   # the user drags an end
    assert win.vm.pane.free_line == pytest.approx((x0, y0, x1 - 2.0, y0))
    assert pane.line_plot.getPlotItem().getAxis("bottom").labelText == "distance (bins)"
    pane.line_mode_control._buttons[0].click()
    assert not pane.free_roi.isVisible()


def test_the_per_tof_bin_overlay_adds_faint_curves(win):
    pane = win.pane
    _cursor_at(win, 0.5, 0.4)
    assert pane.overlay_curves == [] and pane.overlay_switch.isVisible()
    pane.overlay_switch.setChecked(True)
    assert len(pane.overlay_curves) == 5 and win.vm.pane.show_tof_overlay
    assert pane.overlay_curves[0].opts["pen"].color().alpha() < 255
    pane.overlay_switch.setChecked(False)
    assert pane.overlay_curves == []


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_readout_has_its_own_background_in_both_themes(win, theme):
    """A card's labels are transparent; the readout floats over the image, so it must paint the surface."""
    from PySide6 import QtGui
    from pet_projection_data_visualization.view.theme import PALETTES
    win.set_palette(PALETTES[theme])
    _cursor_at(win, 0.5, 0.5)
    image = win.pane.readout.grab().toImage()
    inside = image.pixelColor(image.width() // 2, 3)       # inside the border, above the text
    assert inside.name() == QtGui.QColor(PALETTES[theme].surface).name()
