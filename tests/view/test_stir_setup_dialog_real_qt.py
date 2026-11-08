# SPDX-License-Identifier: Apache-2.0
"""The STIR setup window with real PySide6, offscreen, and stubbed Test/Save/restart."""
import os
import sys

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from pet_projection_data_visualization.model import StirCheck  # noqa: E402
from pet_projection_data_visualization.sources.loader import make_source  # noqa: E402
from pet_projection_data_visualization.view import stir_setup_dialog, window as window_module  # noqa: E402
from pet_projection_data_visualization.view.stir_setup_dialog import StirSetupDialog  # noqa: E402
from pet_projection_data_visualization.viewmodel import StirSetupViewModel, ViewerViewModel  # noqa: E402


class FakeService:
    def __init__(self, good="/good"):
        self.good = good
        self.saved, self.applied = [], []

    def initial_path(self):
        return "/start"

    def test(self, path):
        if path == self.good:
            return StirCheck(True, "STIR imports correctly")
        return StirCheck(False, "built for Python 3.9", version_mismatch=True)

    def save(self, path):
        self.saved.append(path)
        return "/cfg/config.json"

    def apply(self, path, file):
        self.applied.append((path, file))


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def dialog(app):
    svc = FakeService()
    d = StirSetupDialog(StirSetupViewModel(svc, "/data/scan.hs"))
    yield d, svc
    d.close()


def test_the_window_explains_and_shows_the_how_to(dialog):
    d, _ = dialog
    assert "scan.hs" in d.explanation.text() and "could not import" in d.explanation.text()
    assert "conda" in d.how_to.text() and "CMAKE_INSTALL_PREFIX" in d.how_to.text()
    assert d.path_edit.text() == "/start"
    assert [b.text() for b in (d.test_button, d.save_button)] == ["Test", "Save"] and d.browse_button.text()


def test_typing_and_test_show_the_result(dialog):
    d, _ = dialog
    d.path_edit.setText("/bad")
    d.path_edit.textEdited.emit("/bad")                       # what typing emits
    assert d.setup.path == "/bad"
    d.test_button.click()
    assert "built for Python 3.9" in d.result_label.text()
    d.path_edit.textEdited.emit("/good")
    assert d.result_label.text() == ""
    d.test_button.click()
    assert "imports correctly" in d.result_label.text()


def test_save_with_a_bad_path_keeps_the_window_open(dialog):
    d, svc = dialog
    d.show()
    d.setup.set_path("/bad")
    assert d.path_edit.text() == "/bad"
    d.save_button.click()
    assert d.isVisible() and svc.saved == [] and "Not saved" in d.result_label.text()


def test_save_with_a_good_path_closes_the_window(dialog):
    d, svc = dialog
    d.show()
    d.setup.set_path("/good")
    d.save_button.click()
    assert d.result() == QtWidgets.QDialog.DialogCode.Accepted and svc.saved == ["/good"]
    assert not d.save_button.isEnabled()


def test_browse_puts_the_chosen_folder_in_the_box(dialog, monkeypatch):
    d, _ = dialog
    monkeypatch.setattr(stir_setup_dialog.QtWidgets.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: "/chosen"))
    d.browse_button.click()
    assert d.path_edit.text() == "/chosen" and d.setup.path == "/chosen"
    monkeypatch.setattr(stir_setup_dialog.QtWidgets.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: ""))           # cancelled
    d.browse_button.click()
    assert d.setup.path == "/chosen"


# ---- the main window opens it ---------------------------------------------------------------
class RecordingDialog:
    """Stands in for the modal dialog: records what it was given and 'saves' a path."""
    shown = []
    save_path = None

    def __init__(self, setup, parent=None):
        self.setup = setup
        RecordingDialog.shown.append(setup.file)

    def exec(self):
        if RecordingDialog.save_path:              # saves once, then behaves like Cancel
            self.setup.set_path(RecordingDialog.save_path)
            RecordingDialog.save_path = None
            self.setup.save()
        return 0


@pytest.fixture
def harness(app, monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "stir", None)            # makes `import stir` fail
    monkeypatch.delenv("STIR_PYTHON_PATH", raising=False)
    monkeypatch.setattr(window_module, "StirSetupDialog", RecordingDialog)
    RecordingDialog.shown, RecordingDialog.save_path = [], None
    svc = FakeService()
    vm = ViewerViewModel(lambda obj: make_source(obj), stir_setup=svc)
    win = window_module.ViewerWindow(vm)
    yield win, vm, svc, tmp_path
    QtWidgets.QApplication.processEvents()                    # nothing scheduled may leak into the next test
    win.close()


def test_the_window_opens_the_setup_for_a_hs_file_without_stir(harness):
    win, vm, svc, tmp = harness
    (tmp / "scan.hs").write_text("")
    vm.load(str(tmp / "scan.hs"))
    assert RecordingDialog.shown == []                          # not from inside the load command
    QtWidgets.QApplication.processEvents()
    assert RecordingDialog.shown == [str(tmp / "scan.hs")]
    assert vm.stir_setup_file is None and svc.applied == []     # cancelled: nothing applied


def test_the_window_never_opens_the_setup_for_numpy_files(harness):
    win, vm, _, tmp = harness
    np.save(tmp / "x.npy", np.zeros((4, 3, 5), dtype=np.float32))
    vm.load(str(tmp / "x.npy"))
    QtWidgets.QApplication.processEvents()
    assert RecordingDialog.shown == [] and vm.loaded


def test_save_in_the_setup_applies_the_path_and_retries(harness):
    win, vm, svc, tmp = harness
    (tmp / "scan.hs").write_text("")
    RecordingDialog.save_path = "/good"
    vm.load(str(tmp / "scan.hs"))
    QtWidgets.QApplication.processEvents()
    assert svc.saved == ["/good"] and svc.applied == [("/good", str(tmp / "scan.hs"))]
    # the fake service does not make stir importable, so the retry fails and asks again (once per failure)
    QtWidgets.QApplication.processEvents()
    assert RecordingDialog.shown == [str(tmp / "scan.hs")] * 2
    QtWidgets.QApplication.processEvents()
    assert len(RecordingDialog.shown) == 2 and vm.stir_setup_file is None    # cancelled the second time


def test_two_failures_before_the_event_loop_open_one_window(harness):
    win, vm, _, tmp = harness
    (tmp / "scan.hs").write_text("")
    vm.load(str(tmp / "scan.hs"))
    vm.load(str(tmp / "scan.hs"))
    QtWidgets.QApplication.processEvents()
    assert len(RecordingDialog.shown) == 1
