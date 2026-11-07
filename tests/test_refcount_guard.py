# SPDX-License-Identifier: Apache-2.0
"""PySide6 6.12.0 over-releases None/True/False on Linux; on Python 3.11 that aborts the viewer.

Two defences, both checked here: pip never installs PySide6 6.12 with Python < 3.12, and the application
(and this test suite) make the three objects effectively immortal at start-up on CPython < 3.12.
"""
import pathlib
import sys

import pytest
from packaging.requirements import Requirement

from pet_projection_data_visualization import _refcount_guard as guard

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pyside_requirements():
    try:
        import tomllib
    except ImportError:  # pragma: no cover - Python 3.11 has tomllib; kept for clarity
        pytest.skip("tomllib not available")
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    return [Requirement(d) for d in deps if Requirement(d).name.lower() == "pyside6"]


@pytest.mark.parametrize("python, ok, bad", [
    ("3.11", ["6.6.0", "6.11.3", "6.13.0"], ["6.12.0", "6.12.1", "6.5.3"]),
    ("3.12", ["6.6.0", "6.12.0", "6.13.0"], ["6.5.3"]),
    ("3.13", ["6.12.0"], ["6.5.3"]),
])
def test_pip_never_pairs_pyside6_6_12_with_python_before_3_12(python, ok, bad):
    env = {"python_version": python, "python_full_version": f"{python}.0"}
    active = [r for r in _pyside_requirements() if r.marker is None or r.marker.evaluate(env)]
    assert len(active) == 1, active                 # exactly one PySide6 requirement applies per Python
    spec = active[0].specifier
    assert all(spec.contains(v) for v in ok), (python, spec)
    assert not any(spec.contains(v) for v in bad), (python, spec)


def test_guard_is_needed_only_on_cpython_before_3_12():
    assert guard.needs_guard((3, 11, 9), "cpython")
    assert not guard.needs_guard((3, 12, 0), "cpython")
    assert not guard.needs_guard((3, 13, 1), "cpython")
    assert not guard.needs_guard((3, 11, 9), "pypy")


@pytest.mark.skipif(not guard.needs_guard(), reason="None/True/False are immortal from Python 3.12")
def test_guard_makes_none_true_false_effectively_immortal_and_is_idempotent():
    assert guard.protect_singletons()               # conftest already applied it once: no double count
    counts = [sys.getrefcount(o) for o in guard.SINGLETONS]
    assert all(guard.EXTRA_REFERENCES <= c < 2 * guard.EXTRA_REFERENCES for c in counts), counts
    assert guard.protect_singletons()
    after = [sys.getrefcount(o) for o in guard.SINGLETONS]
    assert all(abs(a - c) < 1000 for a, c in zip(after, counts)), (counts, after)


@pytest.mark.skipif(guard.needs_guard(), reason="only where the objects are already immortal")
def test_guard_does_nothing_where_python_already_protects_them():
    before = [sys.getrefcount(o) for o in guard.SINGLETONS]
    assert not guard.protect_singletons()
    assert [sys.getrefcount(o) for o in guard.SINGLETONS] == before


def test_launch_and_build_apply_the_guard_before_any_painting(monkeypatch):
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    from pet_projection_data_visualization import app as app_module

    calls = []
    monkeypatch.setattr(app_module, "protect_singletons", lambda: calls.append("guard"))
    real_instance = QtWidgets.QApplication.instance

    def instance():
        calls.append("qapplication")
        return real_instance() or QtWidgets.QApplication([])

    monkeypatch.setattr(app_module.QtWidgets.QApplication, "instance", staticmethod(instance))
    monkeypatch.setattr(app_module.QtWidgets.QApplication, "exec", lambda self: 0)
    windows = []
    real_build = app_module.build
    monkeypatch.setattr(app_module, "build", lambda *a, **k: windows.append(real_build(*a, **k)) or windows[-1])
    assert app_module.launch() == 0
    assert calls[:2] == ["guard", "qapplication"] and calls.count("guard") == 2     # launch, then build
    for _, window in windows:
        window._timer.stop()
        window.close()
