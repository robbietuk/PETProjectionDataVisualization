# SPDX-License-Identifier: Apache-2.0
"""The window layout of #36 (phase 1): icon rail with flyouts, a large image, the plot column and the
slice toolbar. Real PySide6 + pyqtgraph, offscreen."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from fakes import non_tof_source, small_demo  # noqa: E402
from pet_projection_data_visualization.view.pane import ProjectionDataPane  # noqa: E402
from pet_projection_data_visualization.view.rail import IconRail  # noqa: E402
from pet_projection_data_visualization.view.window import ViewerWindow  # noqa: E402
from pet_projection_data_visualization.viewmodel import ProjectionPaneViewModel, ViewerViewModel  # noqa: E402


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


def _global_rect(widget):
    top_left = widget.mapTo(widget.window(), widget.rect().topLeft())
    return top_left.x(), top_left.y(), widget.width(), widget.height()


def test_rail_has_the_four_flyouts_all_closed_at_start(win):
    assert list(win.rail.buttons) == ["data", "info", "display", "settings"]
    assert win.rail.open_flyout is None and win.rail.flyouts.isHidden()
    for button in win.rail.buttons.values():
        assert button.toolTip() and button.accessibleName() and button.focusPolicy() != 0


def test_clicking_a_rail_button_pins_its_flyout_and_clicking_again_closes_it(win, app):
    win.rail.buttons["display"].click()
    app.processEvents()
    assert win.rail.open_flyout == "display" and win.level_control.isVisible() and win.cmap_control.isVisible()
    assert win.rail.buttons["display"].isChecked()
    win.rail.buttons["data"].click()                    # another one replaces it
    app.processEvents()
    assert win.rail.open_flyout == "data" and win.path_edit.isVisible() and not win.level_control.isVisible()
    assert not win.rail.buttons["display"].isChecked()
    win.rail.buttons["data"].click()
    app.processEvents()
    assert win.rail.open_flyout is None and win.rail.flyouts.isHidden() and not win.rail.buttons["data"].isChecked()


def test_a_flyout_floats_beside_the_rail_without_resizing_anything(win, app):
    before = (win.size(), win.pane.glw.size())
    for key in win.rail.pages:
        win.rail.open(key)
        app.processEvents()
        assert (win.size(), win.pane.glw.size()) == before, key
        fly_x, fly_y, fly_w, fly_h = _global_rect(win.rail.flyouts)
        rail_x, rail_y, rail_w, _ = _global_rect(win.rail)
        assert fly_x > rail_x + rail_w and fly_y == rail_y and fly_h > 0
        assert fly_y + fly_h <= win.centralWidget().height()
    win.rail.open(None)


def test_every_old_card_control_has_a_home(win):
    """Nothing is lost: each control of the old left column is in a flyout or in the toolbar."""
    flyout = {key: win.rail.pages[key] for key in win.rail.pages}
    assert flyout["data"].isAncestorOf(win.path_edit)
    assert flyout["info"].isAncestorOf(win.info_view)
    for w in (win.cmap_control, win.level_control, win.global_button, win.log_switch, *win.level_edits.values()):
        assert flyout["display"].isAncestorOf(w)
    assert flyout["settings"].isAncestorOf(win.fps_spin)
    assert flyout["settings"].isAncestorOf(win.play_mode_control)
    for w in (win.mode_control, win.tof_mode_control, *win.dim_controls.values()):
        assert win.toolbar.isAncestorOf(w)


def test_the_image_is_the_largest_part_and_the_toolbar_is_under_it(win):
    _, img_y, img_w, img_h = _global_rect(win.pane.glw)
    _, bar_y, bar_w, bar_h = _global_rect(win.toolbar)
    _, _, rail_w, _ = _global_rect(win.rail)
    _, _, col_w, _ = _global_rect(win.pane.plot_column)
    assert bar_y >= img_y + img_h                        # the toolbar is under the image
    assert img_w > max(rail_w, col_w) and img_w * img_h > bar_w * bar_h
    assert img_w * img_h > 0.3 * win.centralWidget().width() * win.centralWidget().height()


def test_the_tof_plot_is_in_the_plot_column_right_of_the_image(win):
    assert win.pane.plot_column.isAncestorOf(win.pane.tof_plot)
    img_x, _, img_w, _ = _global_rect(win.pane.glw)
    col_x, _, _, _ = _global_rect(win.pane.plot_column)
    assert col_x >= img_x + img_w


def test_the_tof_plot_fits_its_narrow_column_with_a_long_lor_title(win, app):
    """A long pyqtgraph plot title set a minimum width wider than the column, so bins were cut off."""
    win.vm.pane.hover_at(0.0, 3.0)
    app.processEvents()
    assert "tangential" in win.pane.tof_title.text()
    item_width = win.pane.tof_plot.getPlotItem().geometry().width()
    assert item_width <= win.pane.tof_plot.viewport().width()
    vb = win.pane.tof_view
    first, last = win.vm.pane.tof_range
    from PySide6 import QtCore
    right = vb.mapViewToScene(QtCore.QPointF(last, 0)).x()
    assert right <= vb.sceneBoundingRect().right()              # the last TOF bin is on screen


def test_segment_buttons_leave_room_for_their_bold_checked_label(win):
    from PySide6 import QtGui
    for control in (win.mode_control, win.tof_mode_control):
        for button in control._buttons:
            bold = QtGui.QFont(button.font())
            bold.setBold(True)
            assert button.width() >= QtGui.QFontMetrics(bold).horizontalAdvance(button.text()), button.text()


def test_non_tof_data_hides_the_plot_column_and_the_image_widens(win, app):
    before = win.pane.glw.width()
    win.vm.load(non_tof_source())
    app.processEvents()
    assert win.pane.plot_column.isHidden() and win.dim_controls["tof"].isHidden()
    assert win.pane.glw.width() > before


def test_opening_a_flyout_keeps_the_pane_working(win, app):
    win.rail.open("display")
    app.processEvents()
    win.log_switch.setChecked(True)
    assert win.vm.pane.log_display and win.pane.img.image is not None


def test_rail_rejects_unknown_flyouts(app):
    rail = IconRail()
    rail.add_flyout("a", "A", "Alpha", "tip")
    seen = []
    rail.flyoutChanged.connect(seen.append)
    rail.toggle("a")
    rail.toggle("a")
    assert seen == ["a", None]
    with pytest.raises(KeyError):
        rail.open("b")


def test_a_pane_can_be_built_on_its_own(app):
    """The pane needs only its own view model: the window is not involved (several panes later, #20)."""
    from pet_projection_data_visualization.model import ProjDataset
    vm = ProjectionPaneViewModel()
    pane = ProjectionDataPane(vm)
    vm.show_dataset(ProjDataset(small_demo()))
    assert pane.img.image.shape == (12, 15) and "demo" in pane.title_label.text()
    assert pane.chips.texts() and pane.metrics.pairs()
    vm.hover_at(0.0, 3.0)
    assert pane.readout.text()
    pane.close()
