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


_CAPMAN = []


def _trace(msg):  # TEMPORARY CI diagnostic: bypasses capture and buffering
    import sys
    with _CAPMAN[0].global_and_fixture_disabled():
        sys.stdout.write(f"\n[lock-trace] {msg}\n")
        sys.stdout.flush()


@pytest.fixture(autouse=True)
def _trace_tests(request):
    _CAPMAN[:] = [request.config.pluginmanager.getplugin("capturemanager")]
    _trace(f"start {request.node.name}")
    yield
    _trace(f"end {request.node.name}")


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def win(app):
    vm = ViewerViewModel(lambda o: o)
    w = ViewerWindow(vm)
    vm.load(small_demo())
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    yield w
    _trace("teardown")
    w._timer.stop()
    w.close()
    _trace("closed")


def _button(win, mode):
    return win.level_control._buttons[list(LevelMode).index(mode)]


def _press(widget, key):
    _trace(f"press {type(widget).__name__} {key}")
    QtTest.QTest.keyClick(widget, key)
    QtWidgets.QApplication.processEvents()
    _trace("pressed")


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


def test_L_goes_to_a_focused_text_field_not_the_shortcut(win):
    win.path_edit.setFocus()
    win.path_edit.setText("/data/fi")
    _press(win.path_edit, Key.Key_L)
    assert win.path_edit.text() == "/data/fil" and win.vm.level_mode is LevelMode.ADAPTIVE
    edit = win.level_edits["low"]
    edit.setFocus()
    _press(edit, Key.Key_L)
    assert win.vm.level_mode is LevelMode.ADAPTIVE
    win.info_view.setFocus()                                 # read-only text: still its key (selection, search)
    _press(win.info_view, Key.Key_L)
    assert win.vm.level_mode is LevelMode.ADAPTIVE
