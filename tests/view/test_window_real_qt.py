# SPDX-License-Identifier: Apache-2.0
"""Real PySide6 + pyqtgraph, offscreen. Skipped where they are not installed."""
import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from fakes import non_tof_source, small_demo  # noqa: E402
from pet_projection_data_visualization.model import SliceMode, TofMode  # noqa: E402
from pet_projection_data_visualization.view.window import ViewerWindow  # noqa: E402
from pet_projection_data_visualization.viewmodel import LevelMode, ViewerViewModel  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def win(app):
    vm = ViewerViewModel(lambda o: o)
    w = ViewerWindow(vm)
    vm.load(small_demo())
    yield w
    w._timer.stop()
    w.close()


def test_user_edits_flow_into_the_view_model(win):
    win.dim_controls["axial"]._spin.setValue(3)
    assert win.vm.pane.selection.axial == 3
    win.mode_control._buttons[1].click()
    assert win.vm.pane.slice_mode is SliceMode.VIEWGRAM
    win.tof_mode_control._buttons[list(TofMode).index(TofMode.SUM)].click()
    assert win.vm.pane.tof_mode is TofMode.SUM and not win.play_button.isEnabled()
    win.log_switch.setChecked(True)
    assert win.vm.pane.log_display
    win.level_control._buttons[list(LevelMode).index(LevelMode.LOCKED)].click()
    assert win.vm.pane.level_mode is LevelMode.LOCKED
    win.global_button.click()
    lo, hi = win.vm.pane.dataset.global_range(win.vm.pane.selection)
    assert win.vm.pane.level_mode is LevelMode.LOCKED and win.vm.pane.levels == pytest.approx((np.log1p(lo), np.log1p(hi)))


def test_view_model_changes_flow_into_the_widgets(win):
    vm = win.vm
    vm.pane.set_value("axial", 5)
    assert win.dim_controls["axial"]._spin.value() == 5
    vm.pane.set_slice_mode(SliceMode.TANGENTIAL)
    assert win.mode_control.choice() is SliceMode.TANGENTIAL
    assert win.dim_controls["tangential"].isEnabled() and not win.dim_controls["axial"].isEnabled()
    vm.pane.set_tof_mode(TofMode.MEAN)
    assert win.tof_mode_control.choice() is TofMode.MEAN and not win.dim_controls["tof"].isEnabled()
    assert "Source" in win.info_view.toPlainText()


def test_widget_updates_do_not_echo_back_as_commands(win):
    calls = []
    orig = win.vm.pane.set_value
    win.vm.pane.set_value = lambda *a: (calls.append(a), orig(*a))[1]
    win.vm.pane.set_value("view", 4)
    assert calls == [("view", 4)]                    # one command, not a feedback loop


def test_image_is_drawn_with_real_bin_coordinates(win):
    rect = win.pane.img.boundingRect()
    assert (rect.width(), rect.height()) == (15.0, 12.0)
    assert win.pane.img.image.shape == (12, 15)
    assert win.pane.plot.titleLabel.text.startswith("Sinogram")


def test_playback_timer_follows_the_view_model(win):
    assert not win._timer.isActive()
    win.vm.pane.set_playing(True)
    assert win._timer.isActive() and win.play_button.isChecked()
    before = win.vm.pane.selection.tof
    win._on_timer()
    assert win.vm.pane.selection.tof != before
    win.vm.pane.set_tof_mode(TofMode.SUM)
    assert not win._timer.isActive() and not win.play_button.isChecked()


def test_user_dragging_levels_makes_them_manual_and_applying_levels_does_not_echo(win):
    win.pane.hist.setLevels(1.0, 2.0)
    win.pane._on_user_levels()
    assert win.vm.pane.level_mode is LevelMode.LOCKED and win.vm.pane.levels == (1.0, 2.0)
    win.vm.pane.set_value("axial", 2)                     # programmatic setLevels must not re-enter set_manual_levels
    assert win.vm.pane.levels == (1.0, 2.0)


def test_non_tof_data_hides_the_tof_controls(win):
    win.vm.load(non_tof_source())
    assert win.tof_box.isHidden()
    assert win.pane.tof_dock.isHidden()


def test_load_error_is_shown_in_the_banner_and_can_be_dismissed(app):
    vm = ViewerViewModel(lambda o: (_ for _ in ()).throw(OSError("nope")))
    w = ViewerWindow(vm)
    assert vm.load("x") is False
    assert w.pages.currentIndex() == w.PAGE_EMPTY      # first load failed: still on the empty page
    assert w.banner.isVisibleTo(w)                    # ...and the banner is still reachable there
    assert not w.banner.isHidden() and "nope" in w.banner.label.text()
    w.banner.findChild(QtWidgets.QPushButton).click()
    assert w.banner.isHidden() and vm.error is None
    w.close()


def test_empty_state_until_data_is_loaded(app):
    vm = ViewerViewModel(lambda o: o)
    w = ViewerWindow(vm)
    assert w.pages.currentIndex() == w.PAGE_EMPTY
    vm.load(small_demo())
    assert w.pages.currentIndex() == w.PAGE_VIEWER
    assert w.pane.metrics.pairs() and "Sinogram" in w.pane.chips.texts()
    w.close()


def test_theme_switch_restyles_without_losing_state(win):
    from pet_projection_data_visualization.view.theme import LIGHT
    win.act_light.setChecked(True)
    assert win.palette_tokens is LIGHT
    assert win.vm.loaded and win.pane.img.image.shape == (12, 15)


def test_the_real_histogram_signal_reaches_the_view_model(win):
    """Emits pyqtgraph's own signal: guards against a wrong signal name (which would crash on startup)."""
    win.pane.hist.setLevels(1.0, 2.0)
    win.pane.hist.sigLevelChangeFinished.emit(win.pane.hist)
    assert win.vm.pane.level_mode is LevelMode.LOCKED and win.vm.pane.levels == (1.0, 2.0)


def _type_into(edit, text):
    edit.setText(text)
    edit.editingFinished.emit()


def test_typed_level_and_path_controls(win, tmp_path):
    import numpy as np
    _type_into(win.level_edits["high"], "123")
    assert win.vm.pane.level_mode is LevelMode.LOCKED and win.vm.pane.levels[1] == 123.0
    np.save(tmp_path / "a.npy", np.zeros((4, 3, 5), dtype=np.float32))
    win.vm._factory = __import__("pet_projection_data_visualization.sources.loader", fromlist=["x"]).make_source
    win.path_edit.setText(f'  "{tmp_path / "a.npy"}"  ')             # Windows "Copy as path" style
    win._load_typed_path()
    assert win.vm.pane.dataset.info.num_views == 4 and win.path_edit.text() == str(tmp_path / "a.npy")


def test_level_edits_handle_tiny_values_and_snap_back_on_rejection(app):
    """Review finding: 6 fixed decimals showed 1e-8-sized data as 0/0, and a rejected bound stayed displayed."""
    import numpy as np
    from pet_projection_data_visualization.sources import ArraySource
    vm = ViewerViewModel(lambda o: o)
    w = ViewerWindow(vm)
    try:
        vm.load(ArraySource({0: np.linspace(1e-9, 5e-8, 4 * 3 * 5, dtype=np.float32).reshape(4, 3, 5)}))
        lo, hi = vm.pane.levels
        assert float(w.level_edits["low"].text()) == pytest.approx(lo, rel=1e-5)
        assert float(w.level_edits["high"].text()) == pytest.approx(hi, rel=1e-5) and hi < 1e-7
        _type_into(w.level_edits["high"], "2.5e-8")
        assert vm.pane.levels[1] == pytest.approx(2.5e-8)
        _type_into(w.level_edits["low"], "1")                        # above high: rejected
        assert vm.pane.levels[0] == pytest.approx(lo)
        assert float(w.level_edits["low"].text()) == pytest.approx(lo, rel=1e-5)   # box snapped back
        _type_into(w.level_edits["low"], "not a number")
        assert float(w.level_edits["low"].text()) == pytest.approx(lo, rel=1e-5)
    finally:
        w.close()


def _press(widget, key):
    from PySide6 import QtTest
    QtTest.QTest.keyClick(widget, key)
    QtWidgets.QApplication.processEvents()


def test_arrow_keys_go_to_the_focused_slider_not_the_active_dimension(win, app):
    """Review finding: window-wide Left/Right shortcuts pre-empted a focused slider."""
    from PySide6 import QtCore
    win.show()
    app.processEvents()
    seg = win.dim_controls["segment"]._slider
    before = (win.vm.pane.selection.segment, win.vm.pane.selection.axial)
    seg.setFocus()
    _press(seg, QtCore.Qt.Key.Key_Left)
    assert win.vm.pane.selection.segment == before[0] - 1 and win.vm.pane.selection.axial == before[1]
    # focus on something without its own use for arrows (here: a button), the window steps the active dimension
    win.play_button.setFocus()
    _press(win.play_button, QtCore.Qt.Key.Key_Left)             # (Right would clamp: axial 3 is the last in segment -1)
    assert win.vm.pane.selection.axial == before[1] - 1 and win.vm.pane.selection.segment == before[0] - 1
    _press(win.play_button, QtCore.Qt.Key.Key_PageUp)
    assert win.vm.pane.selection.segment == before[0]
    win.mode_control._buttons[0].setFocus()                       # Space must not re-click a focused button
    _press(win.mode_control._buttons[0], QtCore.Qt.Key.Key_Space)
    assert win.vm.pane.playing
    _press(win.mode_control._buttons[0], QtCore.Qt.Key.Key_Space)
    assert not win.vm.pane.playing
    win.rail.open("data")
    win.path_edit.setFocus()                                      # ...but a text field gets its space
    _press(win.path_edit, QtCore.Qt.Key.Key_Space)
    assert not win.vm.pane.playing and win.path_edit.text().endswith(" ")


def test_save_image_writes_a_png(win, tmp_path, monkeypatch):
    out = tmp_path / "slice.png"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    win._save_image()
    assert out.exists() and out.stat().st_size > 0


def _view_range(win):
    (x0, x1), (y0, y1) = win.pane.plot.getViewBox().viewRange()
    return x0, x1, y0, y1


def _image_extent(win):
    im = win.vm.pane.image
    return im.x0, im.x0 + im.width, im.y0, im.y0 + im.height


def test_image_is_fixed_no_zoom_pan_or_menu_but_keeps_axes(win, app):
    win.resize(1200, 800)
    win.show()
    app.processEvents()
    vb = win.pane.plot.getViewBox()
    assert vb.state["mouseEnabled"] == [False, False]
    assert not win.pane.plot.menuEnabled() and not vb.menuEnabled()
    assert not win.pane.plot.autoBtn.isVisible()
    assert win.pane.plot.getAxis("left").isVisible() and win.pane.plot.getAxis("bottom").isVisible()
    assert _view_range(win) == pytest.approx(_image_extent(win))

    # a wheel event over the image must not change the range
    from PySide6 import QtCore, QtGui
    before = _view_range(win)
    view = win.pane.glw
    centre = view.mapFromScene(vb.mapViewToScene(vb.viewRect().center()))
    ev = QtGui.QWheelEvent(QtCore.QPointF(centre), QtCore.QPointF(view.mapToGlobal(centre)), QtCore.QPoint(0, 0),
                           QtCore.QPoint(0, 240), QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier,
                           QtCore.Qt.ScrollPhase.NoScrollPhase, False)
    QtWidgets.QApplication.sendEvent(view.viewport(), ev)
    app.processEvents()
    assert _view_range(win) == pytest.approx(before)


def test_view_refits_to_the_image_when_the_slice_geometry_changes(win, app):
    for mode in SliceMode:
        win.vm.pane.set_slice_mode(mode)
        app.processEvents()
        assert _view_range(win) == pytest.approx(_image_extent(win)), mode


# ---- TOF profile plot: x fixed to the TOF bins, mouse acts on y only ---------------------------
def _tof_x_range(win):
    return tuple(win.pane.tof_view.viewRange()[0])


def _tof_y_range(win):
    win.pane.tof_view.updateAutoRange()
    return tuple(win.pane.tof_view.viewRange()[1])


def _wheel_over_tof_plot(win, app, delta=240):
    from PySide6 import QtCore, QtGui
    vb, view = win.pane.tof_view, win.pane.tof_plot
    centre = view.mapFromScene(vb.mapViewToScene(vb.viewRect().center()))
    ev = QtGui.QWheelEvent(QtCore.QPointF(centre), QtCore.QPointF(view.mapToGlobal(centre)), QtCore.QPoint(0, 0),
                           QtCore.QPoint(0, delta), QtCore.Qt.MouseButton.NoButton,
                           QtCore.Qt.KeyboardModifier.NoModifier, QtCore.Qt.ScrollPhase.NoScrollPhase, False)
    QtWidgets.QApplication.sendEvent(view.viewport(), ev)
    app.processEvents()


class _DoubleClick:
    def __init__(self):
        self.accepted = False

    def double(self):
        return True

    def button(self):
        from PySide6 import QtCore
        return QtCore.Qt.MouseButton.LeftButton

    def accept(self):
        self.accepted = True


@pytest.fixture
def shown(win, app):
    win.resize(1200, 800)
    win.show()
    app.processEvents()
    return win


def test_tof_plot_mouse_moves_only_y_and_has_no_menu(shown):
    vb = shown.pane.tof_view
    assert vb.state["mouseEnabled"] == [False, True]
    assert vb.autoRangeEnabled()[0] is False and vb.autoRangeEnabled()[1]
    assert not shown.pane.tof_plot.getPlotItem().menuEnabled() and not vb.menuEnabled()


def test_tof_plot_x_range_matches_the_tof_bins_of_each_dataset(shown, app):
    from fakes import shifted_tof_source
    from pet_projection_data_visualization.view.tof_plot import tof_x_limits

    assert _tof_x_range(shown) == pytest.approx(tof_x_limits(0, 4))
    shown.vm.load(shifted_tof_source(-3, tof_bins=7))
    app.processEvents()
    assert _tof_x_range(shown) == pytest.approx(tof_x_limits(-3, 3))
    assert tof_x_limits(-3, 3)[0] < -3 and tof_x_limits(-3, 3)[1] > 3
    shown.vm.pane.hover_at(0, 3)
    app.processEvents()
    assert shown.vm.pane.tof_profile is not None
    assert _tof_x_range(shown) == pytest.approx(tof_x_limits(-3, 3))    # a new LOR keeps the x-range
    shown.vm.pane.hover_at(5, 2)
    app.processEvents()
    assert _tof_x_range(shown) == pytest.approx(tof_x_limits(-3, 3))


def test_tof_plot_wheel_zooms_y_only_and_double_click_or_auto_button_refits(shown, app):
    shown.vm.pane.hover_at(0, 3)
    app.processEvents()
    x0, fitted = _tof_x_range(shown), _tof_y_range(shown)
    assert fitted[0] >= 0                             # counts are >= 0: y never shows below 0

    _wheel_over_tof_plot(shown, app)
    assert _tof_x_range(shown) == pytest.approx(x0)
    zoomed = tuple(shown.pane.tof_view.viewRange()[1])
    assert zoomed[1] - zoomed[0] < fitted[1] - fitted[0]
    assert not shown.pane.tof_view.autoRangeEnabled()[1]   # the user zoomed: a new profile keeps the zoom
    shown.vm.pane.hover_at(1, 3)
    app.processEvents()
    assert tuple(shown.pane.tof_view.viewRange()[1]) == pytest.approx(zoomed)

    ev = _DoubleClick()
    shown.pane.tof_view.mouseClickEvent(ev)
    assert ev.accepted and shown.pane.tof_view.autoRangeEnabled()[1]
    assert shown.pane.tof_view.autoRangeEnabled()[0] is False
    refitted, counts = _tof_y_range(shown), shown.vm.pane.tof_profile.y
    assert refitted != pytest.approx(zoomed)
    assert refitted[0] <= min(counts) and max(counts) <= refitted[1]   # the whole profile is in view
    assert _tof_x_range(shown) == pytest.approx(x0)

    _wheel_over_tof_plot(shown, app)
    shown.pane.tof_plot.getPlotItem().autoBtnClicked()     # pyqtgraph's "A" button
    assert shown.pane.tof_view.autoRangeEnabled()[0] is False and shown.pane.tof_view.autoRangeEnabled()[1]
    assert _tof_y_range(shown) == pytest.approx(refitted)
    assert _tof_x_range(shown) == pytest.approx(x0)


def test_tof_plot_y_cannot_be_panned_below_zero_for_non_negative_counts(shown, app):
    shown.vm.pane.hover_at(0, 3)
    app.processEvents()
    vb = shown.pane.tof_view
    assert vb.state["limits"]["yLimits"][0] == 0.0
    vb.translateBy(y=-1e6)
    app.processEvents()
    assert vb.viewRange()[1][0] >= 0.0
    vb.set_counts((-1.0, 2.0))
    assert vb.state["limits"]["yLimits"][0] is None
