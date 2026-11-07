# SPDX-License-Identifier: Apache-2.0
"""macOS hands documents to a running app as QFileOpenEvent (Dock drop, Finder "Open With")."""
import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from pet_projection_data_visualization.app import build, install_file_open_handler  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def viewer(app):
    vm, window = build()
    handler = install_file_open_handler(app, vm, window)
    yield vm, window, handler
    app.removeEventFilter(handler)
    handler.deleteLater()
    window._timer.stop()
    window.close()


def _array_file(tmp_path, name, n=4):
    path = tmp_path / name
    np.save(path, np.arange(n * 5 * 6, dtype=np.float32).reshape(n, 5, 6))
    return path


def _open(app, what):
    QtWidgets.QApplication.sendEvent(app, QtGui.QFileOpenEvent(what))


def test_file_open_event_loads_the_file(app, viewer, tmp_path):
    vm, window, _ = viewer
    path = _array_file(tmp_path, "sino.npy")
    assert not vm.loaded
    _open(app, str(path))
    app.processEvents()                       # loading happens on a 0 ms timer
    assert vm.loaded and vm.error is None
    assert vm.source_path == str(path)
    assert window.isVisible()


def test_several_files_at_once_load_only_the_last(app, viewer, tmp_path, monkeypatch):
    vm, _, _ = viewer
    first, last = _array_file(tmp_path, "a.npy"), _array_file(tmp_path, "b.npy", n=3)
    loaded = []
    real_load = vm.load
    monkeypatch.setattr(vm, "load", lambda obj: loaded.append(obj) or real_load(obj))
    _open(app, str(first))
    _open(app, str(last))
    app.processEvents()
    assert loaded == [str(last)]
    assert vm.source_path == str(last)


def test_file_open_event_for_a_bad_file_shows_the_error(app, viewer, tmp_path):
    vm, _, _ = viewer
    bad = tmp_path / "nonsense.npy"
    bad.write_text("not an array")
    _open(app, str(bad))
    app.processEvents()
    assert not vm.loaded and vm.error and "Could not load" in vm.error


def test_a_non_local_url_is_reported_not_dropped(app, viewer):
    vm, _, _ = viewer
    _open(app, QtCore.QUrl("https://example.org/data.hs"))
    app.processEvents()
    assert not vm.loaded
    assert vm.error and "only local files" in vm.error and "example.org" in vm.error


def test_events_for_other_objects_are_ignored(app, viewer, tmp_path):
    vm, _, handler = viewer
    other = QtCore.QObject()
    event = QtGui.QFileOpenEvent(str(_array_file(tmp_path, "c.npy")))
    assert handler.eventFilter(other, event) is False
    assert handler.eventFilter(app, QtCore.QEvent(QtCore.QEvent.Type.User)) is False
    app.processEvents()
    assert not vm.loaded and vm.error is None
