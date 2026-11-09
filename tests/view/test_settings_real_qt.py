# SPDX-License-Identifier: Apache-2.0
"""The window remembers its settings between sessions (#36, phase 6): window and panel sizes, theme,
recent files and the pane's choices, in a QSettings INI file. Real PySide6, offscreen."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets  # noqa: E402

from fakes import small_demo  # noqa: E402
from pet_projection_data_visualization.view.theme import DARK, LIGHT  # noqa: E402
from pet_projection_data_visualization.view.window import KEY_STATE, ViewerWindow, saved_theme  # noqa: E402
from pet_projection_data_visualization.viewmodel import LineMode, ViewerViewModel  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def ini(tmp_path):
    return str(tmp_path / "viewer.ini")


def _window(ini_path, palette=DARK):
    vm = ViewerViewModel(lambda o: o)
    settings = QtCore.QSettings(ini_path, QtCore.QSettings.Format.IniFormat)
    win = ViewerWindow(vm, palette, settings)
    vm.load(small_demo())
    win.show()
    QtWidgets.QApplication.processEvents()
    return win


def test_a_new_window_starts_where_the_last_one_closed(app, ini, monkeypatch):
    win = _window(ini)
    win.vm.pane.set_colormap("inferno")
    win.vm.pane.set_line_mode(LineMode.FREE)
    win.line_profile_switch.setChecked(False)
    win.set_palette(LIGHT)
    win.vm.recent_files = ("/data/x.hs",)
    win.pane.splitter.setSizes([700, 420])
    QtWidgets.QApplication.processEvents()
    geometry = bytes(win.saveGeometry())
    panels = [bytes(splitter.saveState()) for splitter in (win.pane.splitter, win.pane.plot_column)]
    win.close()                                         # saves
    settings = QtCore.QSettings(ini, QtCore.QSettings.Format.IniFormat)
    assert saved_theme(settings) == "light"

    # Qt fits a restored window to the screen (the offscreen one is small), so check what Qt is given
    restored = []
    monkeypatch.setattr(ViewerWindow, "restoreGeometry", lambda self, g: restored.append(bytes(g)) or True)
    monkeypatch.setattr(QtWidgets.QSplitter, "restoreState", lambda self, s: restored.append(bytes(s)) or True)
    again = ViewerWindow(ViewerViewModel(lambda o: o), LIGHT, QtCore.QSettings(ini, QtCore.QSettings.Format.IniFormat))
    try:
        assert restored == [geometry]
        pane = again.vm.pane
        assert pane.colormap == "inferno" and pane.line_mode is LineMode.FREE and not pane.show_line_profile
        assert again.cmap_control.choice() == "inferno" and not again.line_profile_switch.isChecked()
        assert again.vm.recent_files == ("/data/x.hs",) and again.recent_buttons
        again.vm.load(small_demo())                     # the panel sizes come back with the first data set
        QtWidgets.QApplication.processEvents()
        assert restored == [geometry] + panels
        again.vm.load(small_demo())                     # ... once
        QtWidgets.QApplication.processEvents()
        assert len(restored) == 3
    finally:
        again.close()


def test_without_settings_nothing_is_saved(app, ini):
    vm = ViewerViewModel(lambda o: o)
    win = ViewerWindow(vm)
    win.save_settings()                                 # no QSettings: a no-op
    win.close()
    assert not os.path.exists(ini)


def test_a_damaged_settings_file_starts_from_the_defaults(app, ini):
    settings = QtCore.QSettings(ini, QtCore.QSettings.Format.IniFormat)
    settings.setValue(KEY_STATE, "{not json")
    settings.setValue("window/theme", "neon")
    settings.setValue("window/geometry", "not bytes")
    settings.sync()
    assert saved_theme(settings) is None
    win = _window(ini)
    try:
        assert win.vm.pane.colormap == "viridis" and win.vm.recent_files == ()
    finally:
        win.close()


def test_launch_uses_the_saved_theme_unless_one_is_given(app, monkeypatch):
    from pet_projection_data_visualization import app as app_module
    settings = app_module.open_settings()               # in the tests' private folder (conftest)
    settings.setValue("window/theme", "light")
    settings.sync()
    themes = []
    real_build = app_module.build

    def build(stir_path, theme, settings):
        themes.append(theme)
        return real_build(stir_path, theme)             # no settings: the test leaves nothing behind

    monkeypatch.setattr(app_module, "build", build)
    monkeypatch.setattr(app_module.QtWidgets.QApplication, "exec", lambda self: 0)
    try:
        assert app_module.launch() == 0 and app_module.launch(theme="dark") == 0
    finally:
        settings.remove("window/theme")
        settings.sync()
        for window in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(window, ViewerWindow):
                window._timer.stop()
                window.close()
    assert themes == ["light", "dark"]
