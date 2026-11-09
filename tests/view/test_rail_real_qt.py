# SPDX-License-Identifier: Apache-2.0
"""The icon rail of #36 (phase 2): hover peeks, click pins, Esc and clicks elsewhere close, keyboard
access, and the four flyouts' content. Real PySide6 + pyqtgraph, offscreen."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtTest, QtWidgets  # noqa: E402

from fakes import non_tof_source, small_demo  # noqa: E402
from pet_projection_data_visualization.view.rail import IconRail  # noqa: E402
from pet_projection_data_visualization.view.theme import DARK, LIGHT  # noqa: E402
from pet_projection_data_visualization.view.window import ViewerWindow  # noqa: E402
from pet_projection_data_visualization.viewmodel import KEYBOARD_SHORTCUTS, ViewerViewModel  # noqa: E402

Key = QtCore.Qt.Key


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _factory(obj):
    return small_demo() if isinstance(obj, str) else obj


@pytest.fixture
def win(app):
    vm = ViewerViewModel(_factory, demo_factory=small_demo, stir_probe=lambda: (False, "STIR not found. Install it"))
    w = ViewerWindow(vm)
    vm.load_demo()
    w.resize(1320, 840)
    w.show()
    app.processEvents()
    yield w
    w.rail.open(None)
    w._timer.stop()
    w.close()
    if w.palette_tokens is not DARK:
        w.set_palette(DARK)                    # the theme is application-wide: leave it as it was


def _hover(widget, inside=True):
    kind = QtCore.QEvent.Type.Enter if inside else QtCore.QEvent.Type.Leave
    QtWidgets.QApplication.sendEvent(widget, QtCore.QEvent(kind))
    QtWidgets.QApplication.processEvents()


def _press(widget, key):
    QtTest.QTest.keyClick(widget, key)
    QtWidgets.QApplication.processEvents()


def _click(widget, pos=None):
    QtTest.QTest.mouseClick(widget, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier,
                            pos if pos is not None else widget.rect().center())
    QtWidgets.QApplication.processEvents()


# ---- hover peeks ----
def test_hovering_a_rail_button_peeks_and_leaving_hides_it(win):
    button = win.rail.buttons["data"]
    _hover(button)
    assert win.rail.peeking == "data" and win.rail.peek.isVisible()
    assert "demo" in win.rail.peek.text() and "Format: synthetic" in win.rail.peek.text()
    _hover(button, inside=False)
    assert win.rail.peeking is None and not win.rail.peek.isVisible()


def test_each_peek_summarises_its_flyout(win):
    texts = {}
    for key, button in win.rail.buttons.items():
        _hover(button)
        texts[key] = win.rail.peek.text()
        _hover(button, inside=False)
    assert "Scanner:" in texts["info"] and "TOF: yes, 5 bins" in texts["info"]
    assert "Colour map: viridis" in texts["display"] and "Theme: Dark" in texts["display"]
    assert "TOF profile: shown" in texts["settings"] and "fps" in texts["settings"]


def test_the_peek_floats_beside_the_rail_without_resizing_anything(win):
    before = (win.size(), win.pane.glw.size())
    button = win.rail.buttons["info"]
    _hover(button)
    peek = win.rail.peek
    rail_right = win.rail.mapTo(win, QtCore.QPoint(win.rail.width(), 0)).x()
    assert peek.mapTo(win, QtCore.QPoint(0, 0)).x() > rail_right
    assert abs(peek.mapTo(win, QtCore.QPoint(0, 0)).y() - button.mapTo(win, QtCore.QPoint(0, 0)).y()) <= 1
    assert (win.size(), win.pane.glw.size()) == before
    _hover(button, inside=False)


def test_a_peek_follows_the_data_while_it_shows(win):
    _hover(win.rail.buttons["info"])
    win.vm.load(non_tof_source())
    QtWidgets.QApplication.processEvents()
    assert "TOF: no" in win.rail.peek.text()


def test_no_peek_for_the_pinned_flyout(win):
    win.rail.buttons["display"].click()
    _hover(win.rail.buttons["display"])
    assert win.rail.peeking is None and not win.rail.peek.isVisible()
    _hover(win.rail.buttons["data"])                      # the other buttons still peek
    assert win.rail.peeking == "data"


def test_opening_a_flyout_hides_the_peek(win):
    _hover(win.rail.buttons["data"])
    win.rail.buttons["data"].click()
    assert win.rail.open_flyout == "data" and not win.rail.peek.isVisible()


# ---- click pins; Esc or a click elsewhere closes ----
def test_esc_closes_the_open_flyout(win):
    win.rail.buttons["display"].click()
    win.cmap_control.setFocus()
    _press(win.cmap_control, Key.Key_Escape)
    assert win.rail.open_flyout is None and win.rail.flyouts.isHidden()


def test_esc_closes_the_flyout_wherever_the_focus_is(win):
    win.rail.buttons["settings"].click()
    win.play_button.setFocus()
    _press(win.play_button, Key.Key_Escape)
    assert win.rail.open_flyout is None


def test_a_click_elsewhere_closes_the_flyout(win):
    win.rail.buttons["data"].click()
    _click(win.pane.glw.viewport())
    assert win.rail.open_flyout is None


def test_clicks_inside_the_flyout_keep_it_open(win):
    win.rail.buttons["display"].click()
    _click(win.log_switch)
    assert win.rail.open_flyout == "display" and win.vm.pane.log_display
    _click(win.rail.pages["display"])                    # on the card's background
    assert win.rail.open_flyout == "display"


def test_without_an_open_flyout_esc_and_clicks_do_nothing_to_the_rail(win):
    seen = []
    win.rail.flyoutChanged.connect(seen.append)
    _click(win.pane.glw.viewport())
    _press(win.play_button, Key.Key_Escape)
    assert seen == [] and win.rail.open_flyout is None


# ---- keyboard ----
def test_every_rail_button_takes_keyboard_focus_and_has_a_tooltip(win):
    for button in win.rail.buttons.values():
        assert button.focusPolicy() & QtCore.Qt.FocusPolicy.TabFocus
        assert button.toolTip() and button.accessibleName() and button.accessibleDescription()


def test_focusing_a_rail_button_peeks(win):
    button = win.rail.buttons["info"]
    button.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    QtWidgets.QApplication.processEvents()
    assert win.rail.peeking == "info"


@pytest.mark.parametrize("key", [Key.Key_Return, Key.Key_Space])
def test_enter_or_space_on_a_focused_rail_button_opens_its_flyout_and_focuses_it(win, key):
    button = win.rail.buttons["data"]
    button.setFocus()
    _press(button, key)
    assert win.rail.open_flyout == "data"
    assert not win.vm.pane.playing                        # Space went to the button, not to Play
    assert win.rail.flyouts.isAncestorOf(QtWidgets.QApplication.focusWidget())


def test_esc_gives_the_focus_back_to_the_rail_button(win):
    button = win.rail.buttons["display"]
    button.setFocus()
    _press(button, Key.Key_Return)
    focus = QtWidgets.QApplication.focusWidget()
    _press(focus, Key.Key_Escape)
    assert win.rail.open_flyout is None and QtWidgets.QApplication.focusWidget() is button


def test_a_mouse_click_on_a_rail_button_does_not_move_the_focus_into_the_flyout(win):
    _click(win.rail.buttons["data"])
    assert win.rail.open_flyout == "data"
    assert not win.rail.flyouts.isAncestorOf(QtWidgets.QApplication.focusWidget())


# ---- the flyouts' content ----
def test_data_flyout_lists_recent_files_and_opens_them(win):
    assert win.recent_buttons == [] and not win.no_recent_label.isHidden()
    win.vm.load("/scans/first.hs")
    win.vm.load("/scans/second.npz")
    assert [b.text() for b in win.recent_buttons] == ["second.npz", "first.hs"]
    assert win.recent_buttons[1].toolTip() == "/scans/first.hs" and win.no_recent_label.isHidden()
    win.recent_buttons[1].click()
    assert win.vm.source_path == "/scans/first.hs"
    assert [b.text() for b in win.recent_buttons] == ["first.hs", "second.npz"]


def test_data_flyout_shows_the_stir_status_and_checks_it_again_when_opened(win):
    assert win.stir_state.text() == "Not available" and "Install it" in win.stir_label.text()
    win.vm._stir_probe = lambda: (True, "STIR found in /opt/stir")
    win.rail.open("data")
    assert win.stir_state.text() == "Available" and win.stir_label.text() == "STIR found in /opt/stir"


def test_display_flyout_has_colour_map_log_display_and_theme(win):
    page = win.rail.pages["display"]
    for widget in (win.cmap_control, win.log_switch, win.theme_control):
        assert page.isAncestorOf(widget)


def test_the_theme_control_and_the_view_menu_stay_in_step(win):
    win.theme_control._buttons[win.theme_control.options.index_of("light")].click()
    assert win.palette_tokens is LIGHT and win.act_light.isChecked()
    win.act_light.setChecked(False)
    assert win.palette_tokens is DARK and win.theme_control.choice() == "dark"


def test_settings_flyout_hides_and_shows_the_tof_profile(win):
    assert win.tof_profile_switch.isChecked() and not win.pane.plot_column.isHidden()
    width = win.pane.glw.width()
    win.tof_profile_switch.setChecked(False)
    QtWidgets.QApplication.processEvents()
    assert not win.vm.pane.show_tof_profile and win.pane.plot_column.isHidden()
    assert win.pane.glw.width() > width                      # the image takes the room
    win.tof_profile_switch.setChecked(True)
    assert not win.pane.plot_column.isHidden()


def test_the_tof_profile_switch_is_disabled_for_non_tof_data(win):
    win.vm.load(non_tof_source())
    assert not win.tof_profile_switch.isEnabled() and win.pane.plot_column.isHidden()


def test_settings_flyout_lists_the_keyboard_shortcuts(win):
    labels = [w.text() for w in win.shortcut_list.findChildren(QtWidgets.QLabel)]
    for keys, action in KEYBOARD_SHORTCUTS:
        assert keys in labels and action in labels
    assert win.rail.pages["settings"].isAncestorOf(win.fps_spin)


@pytest.mark.parametrize("key", ["data", "info", "display", "settings"])
def test_a_flyout_is_tall_enough_for_its_wrapped_text(win, key):
    """The size hint ignores word-wrapped labels; the shortcut list was cut off behind a scroll bar."""
    win.rail.open(key)
    QtWidgets.QApplication.processEvents()
    scroll = win.rail.flyouts.currentWidget()
    assert scroll.verticalScrollBar().maximum() == 0, key


def test_a_rail_on_its_own_peeks_only_once_placed(app):
    rail = IconRail()
    rail.add_flyout("a", "A", "Alpha", "tip", peek=lambda: "alpha")
    rail.add_flyout("b", "B", "Beta", "tip")                  # no peek
    rail.show_peek("a")
    assert rail.peeking is None                             # no window to float in yet
    host = QtWidgets.QWidget()
    QtWidgets.QHBoxLayout(host).addWidget(rail)
    host.show()
    rail.show_peek("a")
    assert rail.peeking == "a" and rail.peek.text() == "alpha"
    rail.show_peek("b")
    assert rail.peeking is None
    host.close()
