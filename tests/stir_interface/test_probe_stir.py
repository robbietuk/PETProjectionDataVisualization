# SPDX-License-Identifier: Apache-2.0
"""``probe_stir``: the STIR status shown in the Data flyout (#36, phase 2). It finds ``stir`` the way
``import_stir`` would, without importing it."""
import importlib.util
import sys
import types

import pytest

from pet_projection_data_visualization.stir_interface import probe_stir
from pet_projection_data_visualization.stir_interface.swig_gateway import ENV_VAR


@pytest.fixture
def no_stir(monkeypatch):
    """No ``stir`` imported, none in the environment and no environment variable."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.delitem(sys.modules, "stir", raising=False)
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "stir" else real(name, *a))


def fake_stir_install(tmp_path):
    (tmp_path / "stir").mkdir()
    (tmp_path / "stir" / "__init__.py").write_text("raise RuntimeError('must not be imported')\n")
    return tmp_path


def test_not_found_says_how_to_install(no_stir):
    ok, text = probe_stir()
    assert not ok and "not found" in text and "conda" in text and "--stir-path" in text


def test_found_in_the_explicit_path_without_importing_it(no_stir, tmp_path):
    ok, text = probe_stir(str(fake_stir_install(tmp_path)))
    assert ok and str(tmp_path) in text and "--stir-path" in text
    assert "stir" not in sys.modules


def test_found_through_the_environment_variable(no_stir, tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_VAR, str(fake_stir_install(tmp_path)))
    ok, text = probe_stir()
    assert ok and f"${ENV_VAR}" in text


def test_a_missing_explicit_path_is_reported(no_stir, tmp_path):
    ok, text = probe_stir(str(tmp_path / "nowhere"))
    assert not ok and "does not exist" in text


def test_a_missing_environment_path_falls_back_like_import_stir(no_stir, tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_VAR, str(tmp_path / "nowhere"))
    ok, text = probe_stir()
    assert not ok and "not found" in text


def test_an_explicit_path_without_stir_falls_back_to_the_environment(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.delitem(sys.modules, "stir", raising=False)
    package = tmp_path / "env" / "stir"
    spec = types.SimpleNamespace(origin=str(package / "__init__.py"), submodule_search_locations=None)
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: spec if name == "stir" else real(name, *a))
    ok, text = probe_stir(str(tmp_path))
    assert ok and str(package) in text


def test_an_imported_stir_is_reported_where_it_was_loaded_from(monkeypatch, tmp_path):
    module = types.ModuleType("stir")
    module.__file__ = str(tmp_path / "python" / "stir" / "__init__.py")
    monkeypatch.setitem(sys.modules, "stir", module)
    ok, text = probe_stir(str(tmp_path / "other"))
    assert ok and f"loaded from {tmp_path / 'python'}" in text
