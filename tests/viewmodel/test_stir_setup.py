# SPDX-License-Identifier: Apache-2.0
"""The STIR setup window's view model, and when the main view model asks for it."""
import sys

import numpy as np
import pytest

from fakes import small_demo
from pet_projection_data_visualization.model import StirCheck, StirNotFoundError
from pet_projection_data_visualization.sources import make_demo_source
from pet_projection_data_visualization.sources.loader import make_source
from pet_projection_data_visualization.viewmodel import StirSetupViewModel, ViewerViewModel


class FakeService:
    def __init__(self, ok=True, initial=""):
        self.ok = ok
        self.initial = initial
        self.tested, self.saved, self.applied = [], [], []
        self.on_apply = None

    def initial_path(self):
        return self.initial

    def test(self, path):
        self.tested.append(path)
        return StirCheck(True, "fine") if self.ok else StirCheck(False, "built for Python 3.9", True)

    def save(self, path):
        self.saved.append(path)
        return "/cfg/config.json"

    def apply(self, path, file):
        self.applied.append((path, file))
        if self.on_apply:
            self.on_apply()


# ---- StirSetupViewModel ----------------------------------------------------------------------
def test_setup_starts_with_the_initial_path_and_explains_what_is_missing():
    s = StirSetupViewModel(FakeService(initial="/opt/stir"), "/data/scan.hs")
    assert s.path == "/opt/stir" and s.result is None and s.saved_path is None
    assert "scan.hs" in s.explanation and "'stir'" in s.explanation
    assert "conda" in s.how_to and "CMAKE_INSTALL_PREFIX" in s.how_to and "python/stir" in s.how_to
    assert f"Python {sys.version_info.major}.{sys.version_info.minor}" in s.how_to


def test_test_cleans_the_path_and_reports_the_result():
    svc = FakeService()
    s = StirSetupViewModel(svc, "a.hs")
    notes = []
    s.subscribe(notes.append)
    s.set_path('  "~/stir"  ')
    assert s.test().ok and s.result.message == "fine"
    assert svc.tested[-1].endswith("stir") and not svc.tested[-1].startswith(("~", '"'))
    s.test()                                   # same result: announced again
    assert notes[-1] == frozenset({"result"})


def test_editing_the_path_clears_the_old_result():
    s = StirSetupViewModel(FakeService(), "a.hs")
    s.test()
    s.set_path("/other")
    assert s.result is None and s.path == "/other"


def test_save_refuses_a_path_that_does_not_work():
    svc = FakeService(ok=False)
    s = StirSetupViewModel(svc, "a.hs")
    s.set_path("/bad")
    assert not s.save()
    assert svc.saved == [] and s.saved_path is None
    assert not s.result.ok and s.result.version_mismatch and "Not saved" in s.result.message


def test_save_stores_a_working_path_and_apply_uses_it():
    svc = FakeService()
    s = StirSetupViewModel(svc, "a.hs")
    s.apply()                                  # nothing saved yet: nothing happens
    assert svc.applied == []
    s.set_path("/good")
    assert s.save()
    assert svc.saved == ["/good"] and s.saved_path == "/good" and "/cfg/config.json" in s.result.message
    s.apply()
    assert svc.applied == [("/good", "a.hs")]


# ---- when the viewer asks for the setup window ---------------------------------------------
@pytest.fixture
def no_stir(monkeypatch):
    monkeypatch.setitem(sys.modules, "stir", None)          # makes `import stir` fail
    monkeypatch.delenv("STIR_PYTHON_PATH", raising=False)


def real_loader_vm(service):
    return ViewerViewModel(source_factory=lambda obj: make_source(obj), demo_factory=make_demo_source,
                           stir_setup=service)


def test_opening_a_hs_file_without_stir_asks_for_setup(tmp_path, no_stir):
    (tmp_path / "scan.hs").write_text("!INTERFILE :=\n")
    vm = real_loader_vm(FakeService())
    notes = []
    vm.subscribe(notes.append)
    assert not vm.load(str(tmp_path / "scan.hs"))
    assert vm.stir_setup_file == str(tmp_path / "scan.hs") and "Could not load" in vm.error
    vm.load(tmp_path / "scan.hs")                            # a second failure asks again
    assert "stir_setup_file" in notes[-1]
    setup = vm.open_stir_setup()
    assert setup.file == str(tmp_path / "scan.hs") and vm.open_stir_setup() is setup


def test_numpy_files_and_the_demo_never_ask_for_setup(tmp_path, no_stir):
    np.save(tmp_path / "x.npy", np.zeros((4, 3, 5), dtype=np.float32))
    (tmp_path / "broken.npz").write_text("not a zip")
    vm = real_loader_vm(FakeService())
    assert vm.load(str(tmp_path / "x.npy"))
    assert not vm.load(str(tmp_path / "broken.npz"))
    assert vm.load_demo()
    assert not vm.load(str(tmp_path / "missing.hs"))          # a typo is not a missing STIR
    assert vm.stir_setup_file is None and vm.open_stir_setup() is None


def test_other_errors_and_non_path_objects_do_not_ask_for_setup():
    def factory(obj):
        raise StirNotFoundError("no stir") if not isinstance(obj, str) else OSError("bad file")
    vm = ViewerViewModel(factory, stir_setup=FakeService())
    assert not vm.load("a.hs") and not vm.load(object())
    assert vm.stir_setup_file is None


def test_without_a_setup_service_there_is_no_setup_window(tmp_path, no_stir):
    (tmp_path / "scan.hs").write_text("")
    vm = ViewerViewModel(lambda obj: make_source(obj))
    assert not vm.load(str(tmp_path / "scan.hs"))
    assert vm.stir_setup_file is None and vm.open_stir_setup() is None


def test_cancelled_setup_just_closes():
    svc = FakeService()
    vm = ViewerViewModel(lambda obj: (_ for _ in ()).throw(StirNotFoundError("x")), stir_setup=svc)
    vm.load("a.hs")
    vm.open_stir_setup()
    assert not vm.finish_stir_setup()
    assert vm.stir_setup_file is None and svc.applied == []


def test_saved_setup_applies_the_path_and_opens_the_file_again():
    svc = FakeService()
    stir_found = []
    svc.on_apply = lambda: stir_found.append(True)          # e.g. Windows: no restart, the path is now used

    def factory(obj):
        if not stir_found:
            raise StirNotFoundError("no stir")
        return small_demo()
    vm = ViewerViewModel(factory, stir_setup=svc)
    assert not vm.load("a.hs")
    setup = vm.open_stir_setup()
    setup.set_path("/good")
    assert setup.save()
    assert vm.finish_stir_setup()
    assert svc.applied == [("/good", "a.hs")] and vm.loaded and vm.error is None and vm.stir_setup_file is None
