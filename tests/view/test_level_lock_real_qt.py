# SPDX-License-Identifier: Apache-2.0
"""The level lock in the real window (PySide6 + pyqtgraph, offscreen). Skipped where Qt is not installed."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtTest, QtWidgets  # noqa: E402

from fakes import small_demo  # noqa: E402
from pet_projection_data_visualization.model import SliceMode, TofMode  # noqa: E402
from pet_projection_data_visualization.view.window import ViewerWindow  # noqa: E402
from pet_projection_data_visualization.viewmodel import LevelMode, ViewerViewModel  # noqa: E402

Key = QtCore.Qt.Key


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(scope="module")
def shown_window(app):
    """One shown window for the whole module, like one session (cheaper than a window per test)."""
    w = ViewerWindow(ViewerViewModel(lambda o: o))
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    yield w
    w._timer.stop()
    w.close()


@pytest.fixture
def win(shown_window, app):
    """The shared window with freshly loaded demo data (adaptive levels, linear display, initial slice)."""
    vm = shown_window.vm
    vm.set_playing(False)
    vm.set_log_display(False)
    assert vm.load(small_demo())
    assert vm.level_mode is LevelMode.ADAPTIVE and vm.slice_mode is SliceMode.SINOGRAM
    app.processEvents()
    yield shown_window
    vm.set_playing(False)


def _button(win, mode):
    return win.level_control._buttons[list(LevelMode).index(mode)]


def _press(widget, key):
    QtTest.QTest.keyClick(widget, key)
    QtWidgets.QApplication.processEvents()


def _colour_bar(win):
    """What the user sees of the colour scale: the level region and the colour bar's axis range."""
    return tuple(win.hist.getLevels()), tuple(win.hist.getHistogramRange())


def test_toggle_drives_the_view_model_and_follows_it(win):
    assert win.level_control.choice() is LevelMode.ADAPTIVE
    _button(win, LevelMode.LOCKED).click()
    assert win.vm.level_mode is LevelMode.LOCKED
    win.vm.set_level_mode(LevelMode.ADAPTIVE)
    assert win.level_control.choice() is LevelMode.ADAPTIVE and _button(win, LevelMode.ADAPTIVE).isChecked()
    win.vm.set_manual_levels(1.0, 2.0)                       # an edit locks: the toggle shows it
    assert win.level_control.choice() is LevelMode.LOCKED


def test_toggle_has_an_accessible_name_and_tooltip(win):
    assert "adaptive or locked" in win.level_control.accessibleName()
    assert "(L)" in win.level_control.toolTip() and "Locked" in win.level_control.toolTip()
    assert win.global_button.accessibleName() and win.global_button.toolTip()


def test_colour_bar_is_identical_while_stepping_views_when_locked(win):
    win.vm.set_slice_mode(SliceMode.VIEWGRAM)                # views are the stepped index here
    _button(win, LevelMode.LOCKED).click()
    locked = _colour_bar(win)
    assert locked[0] == pytest.approx(win.vm.levels, rel=0, abs=0)
    for view in range(win.vm.dataset.info.num_views):
        win.vm.set_value("view", view)
        QtWidgets.QApplication.processEvents()
        assert _colour_bar(win) == locked, view
        assert float(win.level_edits["high"].text()) == pytest.approx(locked[0][1], rel=1e-5)
    for cmd in (lambda: win.vm.set_tof_mode(TofMode.SUM), lambda: win.vm.set_slice_mode(SliceMode.TANGENTIAL),
                lambda: win.vm.step("segment", 1), lambda: win.vm.set_tof_mode(TofMode.BIN)):
        cmd()
        QtWidgets.QApplication.processEvents()
        assert _colour_bar(win) == locked


def test_colour_bar_moves_with_the_slice_when_adaptive(win):
    win.vm.set_slice_mode(SliceMode.VIEWGRAM)
    levels = set()
    for view in range(win.vm.dataset.info.num_views):
        win.vm.set_value("view", view)
        levels.add(tuple(win.hist.getLevels()))
    assert len(levels) > 1


def test_playback_keeps_the_colour_bar_when_locked(win):
    win.vm.toggle_level_lock()
    locked = _colour_bar(win)
    win.play_button.click()
    for _ in range(7):
        win._on_timer()
        assert _colour_bar(win) == locked
    win.play_button.click()


def test_dragging_the_histogram_while_locked_keeps_the_lock_at_the_new_values(win):
    win.vm.toggle_level_lock()
    win.hist.setLevels(0.5, 1.25)
    win.hist.sigLevelChangeFinished.emit(win.hist)
    assert win.vm.level_mode is LevelMode.LOCKED and win.vm.levels == (0.5, 1.25)
    assert win.level_control.choice() is LevelMode.LOCKED
    bar = _colour_bar(win)
    win.vm.set_value("axial", 0)
    assert _colour_bar(win) == bar and bar[0] == (0.5, 1.25)


def test_typing_a_level_while_locked_keeps_the_lock(win):
    win.vm.toggle_level_lock()
    edit = win.level_edits["high"]
    edit.setText("1.5")
    edit.editingFinished.emit()
    assert win.vm.level_mode is LevelMode.LOCKED and win.vm.levels[1] == 1.5


def test_global_range_button_locks_at_the_data_set_range(win):
    win.global_button.click()
    assert win.vm.level_mode is LevelMode.LOCKED
    assert win.vm.levels == win.vm.dataset.global_range(win.vm.selection)
    assert win.level_control.choice() is LevelMode.LOCKED


def test_unlocking_gives_the_colour_bar_back_to_the_data(win):
    win.vm.set_manual_levels(1.0, 2.0)
    win.level_control._buttons[0].click()                    # Adaptive
    assert win.vm.level_mode is LevelMode.ADAPTIVE
    assert tuple(win.hist.getLevels()) == pytest.approx(win.vm.levels)
    assert win.vm.levels != (1.0, 2.0)


def test_locked_chip_is_shown_in_the_header(win):
    assert not any(t.startswith("Levels locked") for t in win.chips.texts())
    win.vm.set_manual_levels(0.0, 3.86)
    assert "Levels locked 0 – 3.86" in win.chips.texts()
    win.vm.toggle_level_lock()
    assert not any(t.startswith("Levels locked") for t in win.chips.texts())


def test_L_toggles_the_lock(win):
    win.play_button.setFocus()                               # a widget with no use for L
    _press(win.play_button, Key.Key_L)
    assert win.vm.level_mode is LevelMode.LOCKED
    seg = win.dim_controls["segment"]._slider                # sliders do not use letters either
    seg.setFocus()
    _press(seg, Key.Key_L)
    assert win.vm.level_mode is LevelMode.ADAPTIVE


@pytest.mark.parametrize("widget", ["path_edit", "level_low", "info_view", "colour_map"])
def test_L_is_handed_to_a_focused_text_field_or_combo_not_the_shortcut(win, monkeypatch, widget):
    """Drives the shortcut handler directly and records what it forwards (whatever the platform does with
    ShortcutOverride, the handler itself must hand a text widget its key)."""
    target = {"path_edit": win.path_edit, "level_low": win.level_edits["low"], "info_view": win.info_view,
              "colour_map": win.cmap_control._combo}[widget]
    target.setFocus()
    QtWidgets.QApplication.processEvents()
    sent = []
    monkeypatch.setattr(QtWidgets.QApplication, "sendEvent",
                        staticmethod(lambda obj, ev: sent.append((obj, ev.type(), ev.text()))))
    win._on_shortcut(Key.Key_L)
    assert win.vm.level_mode is LevelMode.ADAPTIVE
    assert [(o, t) for o, t, _ in sent] == [(target, QtCore.QEvent.Type.KeyPress),
                                            (target, QtCore.QEvent.Type.KeyRelease)]
    assert {text for *_, text in sent} == {"l"}             # the letter is forwarded, so it is still typed


def test_L_forwarded_to_a_text_field_types_the_letter(win):
    win.info_view.setReadOnly(False)
    try:
        win.info_view.setPlainText("")
        win.info_view.setFocus()
        QtWidgets.QApplication.processEvents()
        win._on_shortcut(Key.Key_L)
        assert win.info_view.toPlainText() == "l" and win.vm.level_mode is LevelMode.ADAPTIVE
    finally:
        win.info_view.setReadOnly(True)                      # the window is shared by the whole module


def test_typing_L_into_the_path_box_types_it(win):
    win.path_edit.setFocus()
    win.path_edit.setText("/data/fi")
    _press(win.path_edit, Key.Key_L)
    assert win.path_edit.text() == "/data/fil" and win.vm.level_mode is LevelMode.ADAPTIVE


# ---- the colour bar's axis when a lock is made ------------------------------------------------------
def _axis(win):
    QtWidgets.QApplication.processEvents()
    return tuple(win.hist.getHistogramRange())


def test_locking_from_the_toggle_keeps_the_colour_bar_axis_on_screen(win):
    before = _axis(win)
    _button(win, LevelMode.LOCKED).click()
    assert _axis(win) == pytest.approx(before, rel=1e-9)
    win.vm.set_value("axial", 0)
    assert _axis(win) == pytest.approx(before, rel=1e-9)


def test_dragging_the_histogram_while_adaptive_locks_without_moving_the_axis(win):
    """The drag ends on sigLevelChangeFinished: the axis must not rescale under the mouse at release."""
    before = _axis(win)
    lo, hi = win.vm.levels
    win.hist.setLevels(lo + 0.25 * (hi - lo), hi - 0.25 * (hi - lo))      # what the drag left on screen
    win.hist.sigLevelChangeFinished.emit(win.hist)
    assert win.vm.level_mode is LevelMode.LOCKED
    assert win.vm.levels == pytest.approx((lo + 0.25 * (hi - lo), hi - 0.25 * (hi - lo)))
    pinned = _axis(win)
    assert pinned == pytest.approx(before, rel=1e-3)          # no visible jump (was rescaled to the levels)
    for view in (0, 3, 5):
        win.vm.set_value("axial", view)
        assert _axis(win) == pinned and tuple(win.hist.getLevels()) == win.vm.levels


def test_typed_levels_fit_the_axis_to_the_new_lock(win):
    _button(win, LevelMode.LOCKED).click()
    edit = win.level_edits["high"]
    edit.setText("40")
    edit.editingFinished.emit()
    lo, hi = _axis(win)
    assert win.vm.levels[1] == 40.0 and lo <= win.vm.levels[0] and hi >= 40.0
    assert hi - lo < 1.5 * (40.0 - win.vm.levels[0])           # fitted to the lock, not left at the old axis
