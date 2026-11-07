# SPDX-License-Identifier: Apache-2.0
"""macOS hands documents to a running app as QFileOpenEvent (Dock drop, Finder "Open With")."""
import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtGui, QtWidgets  # noqa: E402

from pet_projection_data_visualization.app import build, install_file_open_handler  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def viewer(app):
    vm, window = build()
    handler = install_file_open_handler(app, vm, window)
    yield vm, window
    app.removeEventFilter(handler)
    handler.deleteLater()
    window._timer.stop()
    window.close()


def test_file_open_event_loads_the_file(app, viewer, tmp_path):
    vm, window = viewer
    path = tmp_path / "sino.npy"
    np.save(path, np.arange(4 * 5 * 6, dtype=np.float32).reshape(4, 5, 6))
    assert not vm.loaded
    QtWidgets.QApplication.sendEvent(app, QtGui.QFileOpenEvent(str(path)))
    assert vm.loaded and vm.error is None
    assert vm.source_path == str(path)
    assert window.isVisible()


def test_file_open_event_for_a_bad_file_shows_the_error(app, viewer, tmp_path):
    vm, _ = viewer
    bad = tmp_path / "nonsense.npy"
    bad.write_text("not an array")
    QtWidgets.QApplication.sendEvent(app, QtGui.QFileOpenEvent(str(bad)))
    assert not vm.loaded and vm.error and "Could not load" in vm.error
