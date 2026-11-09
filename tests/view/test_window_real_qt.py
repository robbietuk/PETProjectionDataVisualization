# SPDX-License-Identifier: Apache-2.0
"""Real PySide6 + pyqtgraph, offscreen. Skipped where they are not installed."""
import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets  # noqa: E402

from fakes import non_tof_source, small_demo  # noqa: E402
from pet_projection_data_visualization.model import SliceMode, TofMode  # noqa: E402
from pet_projection_data_visualization.view.styling import apply_theme  # noqa: E402
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
    w.deleteLater()                            # gone now, not at some later test's processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def test_user_edits_flow_into_the_view_model(win):
    win.dim_controls["axial"]._spin.setValue(3)
    assert win.vm.pane.selection.axial == 3
    win.mode_control._buttons[1].click()
    assert win.vm.pane.slice_mode is SliceMode.VIEWGRAM
    win.tof_mode_control._buttons[list(TofMode).index(TofMode.SUM)].click()
    tof_play = win.dim_controls["tof"].play_button
    assert win.vm.pane.tof_mode is TofMode.SUM and not tof_play.isEnabled() and "Sum" in tof_play.toolTip()
    win.dim_controls["segment"].play_button.click()
    assert win.vm.pane.play_axis == "segment"
    win.dim_controls["segment"]._next.click()
    assert win.vm.pane.selection.segment == 1
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
    assert not win.dim_controls["tangential"].isHidden() and win.dim_controls["axial"].isHidden()
    vm.pane.set_tof_mode(TofMode.MEAN)
    tof = win.dim_controls["tof"]
    assert win.tof_mode_control.choice() is TofMode.MEAN and not tof._spin.isEnabled()
    assert not tof.play_button.isEnabled() and win.tof_mode_control.isEnabled()      # Bin can be chosen again
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
    tof_play = win.dim_controls["tof"].play_button
    assert win._timer.isActive() and tof_play.isChecked()
    before = win.vm.pane.selection.tof
    win._on_timer()
    assert win.vm.pane.selection.tof != before
    win.vm.pane.set_tof_mode(TofMode.SUM)
    assert not win._timer.isActive() and not tof_play.isChecked()


def test_row_play_buttons_play_one_axis_at_a_time(win):
    seg, axial = win.dim_controls["segment"].play_button, win.dim_controls["axial"].play_button
    seg.click()
    assert win._timer.isActive() and seg.isChecked() and not axial.isChecked()
    axial.click()
    assert win.vm.pane.play_axis == "axial" and axial.isChecked() and not seg.isChecked()
    assert "pauses the axial" in win.space_hint.text()
    axial.click()
    assert not win._timer.isActive() and not axial.isChecked()


def test_play_mode_and_speed_controls_in_the_settings_flyout(win):
    from pet_projection_data_visualization.viewmodel import PlayMode
    win.play_mode_control._buttons[list(PlayMode).index(PlayMode.BOUNCE)].click()
    assert win.vm.pane.play_mode is PlayMode.BOUNCE
    win.vm.pane.set_play_mode(PlayMode.LOOP)
    assert win.play_mode_control.choice() is PlayMode.LOOP


def test_user_dragging_levels_makes_them_manual_and_applying_levels_does_not_echo(win):
    win.pane.hist.setLevels(1.0, 2.0)
    win.pane._on_user_levels()
    assert win.vm.pane.level_mode is LevelMode.LOCKED and win.vm.pane.levels == (1.0, 2.0)
    win.vm.pane.set_value("axial", 2)                     # programmatic setLevels must not re-enter set_manual_levels
    assert win.vm.pane.levels == (1.0, 2.0)


def test_non_tof_data_hides_the_tof_controls(win):
    win.vm.load(non_tof_source())
    assert win.dim_controls["tof"].isHidden() and not win.tof_mode_control.isVisibleTo(win)
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
    button = win.dim_controls["tof"].play_button
    button.setFocus()
    _press(button, QtCore.Qt.Key.Key_Left)             # (Right would clamp: axial 3 is the last in segment -1)
    assert win.vm.pane.selection.axial == before[1] - 1 and win.vm.pane.selection.segment == before[0] - 1
    _press(button, QtCore.Qt.Key.Key_PageUp)
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


def _settle(app):
    for _ in range(5):
        app.processEvents()


def test_level_boxes_are_not_fixed_width(win):
    for edit in win.level_edits.values():
        assert edit.minimumWidth() < edit.maximumWidth()


def test_narrow_window_does_not_cut_off_the_plot_or_the_header(win, app):
    apply_theme(app)
    win.show()
    win.resize(760, 600)
    _settle(app)
    pane = win.pane
    scene_min = pane.glw.ci.effectiveSizeHint(QtCore.Qt.SizeHint.MinimumSize).width()
    assert pane.glw.width() >= scene_min                                      # histogram fully visible
    assert pane.chips.width() >= pane.chips.sizeHint().width()                # chips are not squeezed
    assert pane.title_label.text() == win.vm.pane.title                       # elided on screen, full text kept


def test_plot_minimum_follows_the_scene_when_its_layout_changes_later(win, app):
    """Tick-label widths (and fonts) change after a render, e.g. on a resize or a range change: the view's
    minimum must follow, or a narrow window cuts off the histogram."""
    apply_theme(app)
    win.show()
    win.resize(760, 600)
    _settle(app)
    pane = win.pane
    before = pane.glw.minimumWidth()
    pane.plot.getAxis("left").setWidth(300)           # what a wider tick label does, without a re-render
    _settle(app)
    scene_min = pane.glw.ci.effectiveSizeHint(QtCore.Qt.SizeHint.MinimumSize).width()
    assert scene_min > before
    assert pane.glw.minimumWidth() >= scene_min
    assert pane.glw.width() >= scene_min                                      # histogram fully visible
    pane.plot.getAxis("left").setWidth(None)          # back to automatic: the minimum shrinks again
    _settle(app)
    assert pane.glw.minimumWidth() < scene_min


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


# ---- orientation (docs/ORIENTATION.md; the model side is pinned in tests/model/test_orientation.py) ----------
def _asymmetric_source():
    """views 2..5, axial 5..7, tangential -2..2; each bin holds 100 * view + 10 * axial + tangential."""
    import dataclasses

    from pet_projection_data_visualization.sources import ArraySource
    arr = np.array([[[100 * v + 10 * a + t for t in range(-2, 3)] for a in range(5, 8)] for v in range(2, 6)],
                   dtype=np.float32)
    src = ArraySource({0: arr}, name="asymmetric")
    src.info = dataclasses.replace(src.info, min_view=2, max_view=5, axial_ranges={0: (5, 7)})
    return src


@pytest.mark.parametrize("mode, rows, cols", [(SliceMode.SINOGRAM, ("view", 2, 5), ("tangential", -2, 2)),
                                              (SliceMode.VIEWGRAM, ("axial", 5, 7), ("tangential", -2, 2)),
                                              (SliceMode.TANGENTIAL, ("view", 2, 5), ("axial", 5, 7))])
def test_row_0_is_drawn_at_the_top_and_column_0_at_the_left(shown, app, mode, rows, cols):
    win = shown
    win.vm.load(_asymmetric_source())
    win.vm.pane.set_slice_mode(mode)
    _settle(app)
    vb = win.pane.plot.getViewBox()
    assert vb.yInverted() and not vb.xInverted()
    assert win.pane.plot.getAxis("left").labelText == rows[0] and win.pane.plot.getAxis("bottom").labelText == cols[0]
    n_rows, n_cols = rows[2] - rows[1] + 1, cols[2] - cols[1] + 1
    assert win.pane.img.image.shape == (n_rows, n_cols)
    rect = win.pane.img.mapRectToView(win.pane.img.boundingRect())
    assert (rect.left(), rect.top(), rect.width(), rect.height()) == pytest.approx(
        (cols[1] - 0.5, rows[1] - 0.5, n_cols, n_rows))           # integer axis values are pixel centres

    def scene_of(r, c):         # where the centre of image pixel (row r, column c) lands in the scene
        p = win.pane.img.mapToScene(QtCore.QPointF(c + 0.5, r + 0.5))
        return p.x(), p.y()

    def axes_of(r, c):          # the axis values at that pixel centre
        p = vb.mapSceneToView(win.pane.img.mapToScene(QtCore.QPointF(c + 0.5, r + 0.5)))
        return p.x(), p.y()

    top_left, bottom_left, top_right = scene_of(0, 0), scene_of(n_rows - 1, 0), scene_of(0, n_cols - 1)
    assert bottom_left[1] > top_left[1] and bottom_left[0] == pytest.approx(top_left[0])    # last row is lower
    assert top_right[0] > top_left[0] and top_right[1] == pytest.approx(top_left[1])        # last column is right
    assert axes_of(0, 0) == pytest.approx((cols[1], rows[1]))
    assert axes_of(n_rows - 1, n_cols - 1) == pytest.approx((cols[2], rows[2]))
