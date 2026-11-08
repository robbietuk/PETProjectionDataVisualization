# SPDX-License-Identifier: Apache-2.0
"""STIR lookup, the saved setting, the Test import and the restart, all without real STIR (fake ``stir``
packages in ``tmp_path``)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pet_projection_data_visualization.model import StirNotFoundError
from pet_projection_data_visualization.stir_interface import swig_gateway
from pet_projection_data_visualization.stir_interface.stir_config import (
    CONFIG_DIR_ENV_VAR, ENV_VAR, RESTART_MARKER, StirLocation, StirPathSource, StirSetupActions,
    build_stir_env, can_restart, check_stir, config_dir, config_file_path, current_python,
    extension_python_versions, load_saved_path, locate_stir, resolve_stir_path, restart_command,
    restart_viewer, save_path, windows_dll_dirs)


def fake_stir(folder: Path, body: str = "MARK = 'fake'\n") -> Path:
    """A ``stir`` package in ``folder``; returns ``folder``."""
    (folder / "stir").mkdir(parents=True)
    (folder / "stir" / "__init__.py").write_text(body)
    return folder


def fake_install(root: Path, body: str = "MARK = 'fake'\n") -> Path:
    """A source-build install prefix: ``<root>/python/stir`` and ``<root>/lib``; returns ``root``."""
    fake_stir(root / "python", body)
    (root / "lib").mkdir()
    return root


# ---- config folder and file ----------------------------------------------------------------
def test_config_dir_follows_each_platform(tmp_path):
    home = tmp_path / "home"
    assert config_dir({}, "linux", home) == home / ".config" / "PETProjectionDataVisualization"
    assert config_dir({"XDG_CONFIG_HOME": "/x/cfg"}, "linux", home) == Path("/x/cfg/PETProjectionDataVisualization")
    assert config_dir({"XDG_CONFIG_HOME": "rel"}, "linux", home) == home / ".config" / "PETProjectionDataVisualization"
    assert config_dir({}, "darwin", home) == home / "Library" / "Application Support" / "PETProjectionDataVisualization"
    assert config_dir({"APPDATA": str(tmp_path / "roam")}, "win32", home) == tmp_path / "roam" / "PETProjectionDataVisualization"
    assert config_dir({}, "win32", home) == home / "AppData" / "Roaming" / "PETProjectionDataVisualization"
    assert config_dir({CONFIG_DIR_ENV_VAR: str(tmp_path / "o")}, "darwin", home) == tmp_path / "o"


def test_config_dir_checks_xdg_with_posix_rules_on_any_host(tmp_path):
    # The platform argument decides, not the host: on Windows, ntpath.isabs("/x") is False since Python 3.13
    # and ntpath.isabs("C:\\cfg") is True; XDG_CONFIG_HOME follows POSIX rules either way.
    home = tmp_path / "home"
    assert config_dir({"XDG_CONFIG_HOME": "/x/cfg"}, "linux", home) == Path("/x/cfg") / "PETProjectionDataVisualization"
    assert config_dir({"XDG_CONFIG_HOME": "C:\\cfg"}, "linux", home) == home / ".config" / "PETProjectionDataVisualization"


def test_tests_use_a_private_config_folder(tmp_path):
    assert os.environ[CONFIG_DIR_ENV_VAR] in str(config_file_path())     # conftest: never the user's real file


def test_save_then_load_round_trip_keeps_other_settings(tmp_path):
    file = tmp_path / "sub" / "config.json"
    assert load_saved_path(file) is None
    file.parent.mkdir()
    file.write_text(json.dumps({"other": 1}))
    assert save_path(str(tmp_path / "stir"), file) == file
    assert load_saved_path(file) == str(tmp_path / "stir")
    assert json.loads(file.read_text())["other"] == 1
    assert not list(file.parent.glob("*.tmp"))


def test_save_makes_the_path_absolute_and_creates_the_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file = tmp_path / "new" / "deeper" / "config.json"
    save_path("relative", file)
    assert load_saved_path(file) == str(tmp_path / "relative")


def test_default_config_file_is_used_without_an_argument():
    save_path("/opt/stir")
    assert load_saved_path() == os.path.abspath("/opt/stir")


@pytest.mark.parametrize("text, match", [("{not json", "not valid JSON"), ("[1, 2]", "not a JSON object")])
def test_a_broken_config_file_is_ignored_with_a_warning(tmp_path, text, match):
    file = tmp_path / "config.json"
    file.write_text(text)
    with pytest.warns(RuntimeWarning, match=match):
        assert load_saved_path(file) is None
    with pytest.warns(RuntimeWarning):
        save_path("/opt/stir", file)                      # overwritten with a valid file
    assert load_saved_path(file) == os.path.abspath("/opt/stir")


def test_non_string_saved_value_is_ignored(tmp_path):
    file = tmp_path / "config.json"
    file.write_text(json.dumps({"stir_path": 3}))
    assert load_saved_path(file) is None


# ---- locating stir in what the user gave -----------------------------------------------------
def test_locate_the_module_folder_itself(tmp_path):
    fake_install(tmp_path / "inst")
    assert locate_stir(str(tmp_path / "inst" / "python")) == StirLocation(str(tmp_path / "inst" / "python"),
                                                                          str(tmp_path / "inst"))


def test_locate_from_the_install_prefix(tmp_path):
    fake_install(tmp_path / "inst")
    assert locate_stir(str(tmp_path / "inst")) == StirLocation(str(tmp_path / "inst" / "python"), str(tmp_path / "inst"))


def test_locate_in_a_conda_environment(tmp_path):
    env = tmp_path / "envs" / "stir"
    site = env / "lib" / f"python{current_python()}" / "site-packages"
    fake_stir(site)
    assert locate_stir(str(env)) == StirLocation(str(site), str(env))
    assert locate_stir(str(site)) == StirLocation(str(site), str(env))         # site-packages chosen directly


def test_locate_in_a_windows_conda_environment(tmp_path):
    site = tmp_path / "env" / "Lib" / "site-packages"
    fake_stir(site)
    assert locate_stir(str(tmp_path / "env")) == StirLocation(str(site), str(tmp_path / "env"))
    assert locate_stir(str(site)).prefix == str(tmp_path / "env")


def test_locate_without_stir_takes_the_path_as_is(tmp_path):
    assert locate_stir(str(tmp_path / "x")) == StirLocation(str(tmp_path / "x"), str(tmp_path))


# ---- precedence ---------------------------------------------------------------------------
def test_precedence_cli_env_saved_then_plain_import(tmp_path):
    cli, env, saved = (fake_install(tmp_path / n) for n in ("cli", "env", "saved"))
    environ = {ENV_VAR: str(env)}
    r = resolve_stir_path(str(cli), environ, str(saved))
    assert (r.location.prefix, r.source) == (str(cli), StirPathSource.CLI)
    r = resolve_stir_path(None, environ, str(saved))
    assert (r.location.prefix, r.source) == (str(env), StirPathSource.ENV)
    r = resolve_stir_path(None, {}, str(saved))
    assert (r.location.prefix, r.source) == (str(saved), StirPathSource.CONFIG)
    assert resolve_stir_path(None, {}, None) is None


def test_blank_values_count_as_unset(tmp_path):
    saved = fake_install(tmp_path / "saved")
    r = resolve_stir_path("  ", {ENV_VAR: ""}, str(saved))
    assert r.source is StirPathSource.CONFIG
    assert resolve_stir_path("", {ENV_VAR: " "}, " ") is None


def test_a_missing_cli_path_is_returned_so_the_import_can_report_it(tmp_path):
    r = resolve_stir_path(str(tmp_path / "nope"), {}, None)
    assert r.source is StirPathSource.CLI and r.location.python_dir == str(tmp_path / "nope")


def test_missing_env_and_saved_paths_are_skipped_with_a_warning(tmp_path):
    saved = fake_install(tmp_path / "saved")
    with pytest.warns(RuntimeWarning, match=r"\$STIR_PYTHON_PATH"):
        assert resolve_stir_path(None, {ENV_VAR: str(tmp_path / "gone")}, str(saved)).source is StirPathSource.CONFIG
    with pytest.warns(RuntimeWarning, match="saved setting"):
        assert resolve_stir_path(None, {}, str(tmp_path / "gone")) is None


# ---- import_stir reads the saved setting ----------------------------------------------------
@pytest.fixture
def clean_stir(monkeypatch):
    monkeypatch.delitem(sys.modules, "stir", raising=False)
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))


def test_import_stir_uses_the_saved_path(tmp_path, clean_stir):
    save_path(str(fake_install(tmp_path / "inst", "MARK = 'saved'\n")))      # the prefix, not python/
    assert swig_gateway.import_stir().MARK == "saved"


def test_env_var_beats_the_saved_path(tmp_path, clean_stir, monkeypatch):
    save_path(str(fake_install(tmp_path / "saved", "MARK = 'saved'\n")))
    monkeypatch.setenv(ENV_VAR, str(fake_install(tmp_path / "env", "MARK = 'env'\n")))
    assert swig_gateway.import_stir().MARK == "env"


def test_import_failure_names_where_it_looked(tmp_path, clean_stir):
    save_path(str(fake_install(tmp_path / "inst", "raise ImportError('libSTIR.so: cannot open')\n")))
    with pytest.raises(StirNotFoundError, match="saved setting") as e:
        swig_gateway.import_stir()
    assert "libSTIR.so" in str(e.value)


@pytest.mark.parametrize("source", ["cli", "env", "saved"])
def test_windows_dll_folders_are_registered_for_every_source(tmp_path, clean_stir, monkeypatch, source):
    inst = fake_install(tmp_path / "inst")
    (inst / "bin").mkdir()
    added = []
    monkeypatch.setattr(swig_gateway.os, "add_dll_directory", added.append, raising=False)
    cli = None
    if source == "cli":
        cli = str(inst / "python")
    elif source == "env":
        monkeypatch.setenv(ENV_VAR, str(inst))
    else:
        save_path(str(inst))
    swig_gateway.import_stir(cli)
    assert added == [str(inst / "bin"), str(inst / "lib")]


def test_windows_dll_dirs_include_condas_library_bin(tmp_path):
    (tmp_path / "Library" / "bin").mkdir(parents=True)
    assert windows_dll_dirs(StirLocation(str(tmp_path / "Lib" / "site-packages"), str(tmp_path))) == [
        str(tmp_path / "Library" / "bin")]


# ---- environment for a new process -----------------------------------------------------------
@pytest.mark.parametrize("platform, var", [("linux", "LD_LIBRARY_PATH"), ("darwin", "DYLD_LIBRARY_PATH")])
def test_build_stir_env_sets_pythonpath_and_the_library_path(tmp_path, platform, var):
    inst = fake_install(tmp_path / "inst")
    loc = locate_stir(str(inst))
    env = build_stir_env(loc, {var: os.pathsep.join(["/old", str(inst / "lib")]), "PYTHONPATH": "/pp", "X": "1"},
                         platform)
    assert env[var] == os.pathsep.join([str(inst / "lib"), "/old"])        # first, and not twice
    assert env["PYTHONPATH"] == os.pathsep.join([loc.python_dir, "/pp"])
    assert env["X"] == "1"


def test_build_stir_env_on_windows_uses_path(tmp_path):
    inst = fake_install(tmp_path / "inst")
    (inst / "bin").mkdir()
    env = build_stir_env(locate_stir(str(inst)), {"PATH": "C:/old"}, "win32")
    assert env["PATH"] == os.pathsep.join([str(inst / "bin"), str(inst / "lib"), "C:/old"])
    assert "LD_LIBRARY_PATH" not in env


def test_build_stir_env_does_not_change_the_given_mapping(tmp_path):
    environ = {"PYTHONPATH": "/pp"}
    build_stir_env(locate_stir(str(fake_install(tmp_path / "i"))), environ, "linux")
    assert environ == {"PYTHONPATH": "/pp"}


def test_a_child_python_finds_stir_with_the_built_environment(tmp_path):
    inst = fake_install(tmp_path / "inst", "MARK = 'child'\n")
    env = build_stir_env(locate_stir(str(inst)), dict(os.environ), sys.platform)
    out = subprocess.run([sys.executable, "-c", "import stir; print(stir.MARK)"], env=env, capture_output=True,
                         text=True, check=True, cwd=tmp_path)
    assert out.stdout.strip() == "child"


# ---- the Test button -------------------------------------------------------------------------
def test_check_reports_success_with_where_stir_was_found(tmp_path):
    inst = fake_install(tmp_path / "inst")
    r = check_stir(str(inst))
    assert r.ok and not r.version_mismatch and str(inst / "python" / "stir") in r.message


@pytest.mark.parametrize("path, match", [("", "Enter the folder"), ("   ", "Enter the folder")])
def test_check_needs_a_path(path, match):
    r = check_stir(path)
    assert not r.ok and match in r.message


def test_check_reports_a_missing_folder_and_a_folder_without_stir(tmp_path):
    assert "does not exist" in check_stir(str(tmp_path / "nope")).message
    r = check_stir(str(tmp_path))
    assert not r.ok and "no 'stir' Python module" in r.message


def test_check_reports_the_import_error(tmp_path):
    inst = fake_install(tmp_path / "inst", "raise ImportError('libstir_buildblock.so: cannot open shared object')\n")
    r = check_stir(str(inst))
    assert not r.ok and not r.version_mismatch and "libstir_buildblock.so" in r.message


def test_check_detects_a_python_version_mismatch_from_the_extension_name(tmp_path):
    inst = fake_install(tmp_path / "inst")
    other = "3.9" if current_python() != "3.9" else "3.10"
    (inst / "python" / "stir" / f"_stir.cpython-{other.replace('.', '')}-x86_64-linux-gnu.so").write_bytes(b"")
    assert extension_python_versions(str(inst / "python")) == {other}
    r = check_stir(str(inst))
    assert not r.ok and r.version_mismatch and f"Python {other}" in r.message and current_python() in r.message


def test_a_matching_extension_tag_is_not_a_mismatch(tmp_path):
    inst = fake_install(tmp_path / "inst")
    tag = current_python().replace(".", "")
    (inst / "python" / f"_stir.cp{tag}-win_amd64.pyd").write_bytes(b"")
    assert check_stir(str(inst)).ok


def test_check_detects_a_python_version_mismatch_from_the_error(tmp_path):
    inst = fake_install(tmp_path / "inst",
                        "raise ImportError('Module use of python39.dll conflicts with this version of Python.')\n")
    r = check_stir(str(inst))
    assert not r.ok and r.version_mismatch and "does not match this Python" in r.message


def test_check_reports_a_test_that_cannot_run(tmp_path):
    r = check_stir(str(fake_install(tmp_path / "inst")), python=str(tmp_path / "no-python"))
    assert not r.ok and "Could not run" in r.message


def test_check_does_not_import_stir_here(tmp_path, clean_stir):
    check_stir(str(fake_install(tmp_path / "inst")))
    assert "stir" not in sys.modules


# ---- restart ---------------------------------------------------------------------------------
def test_restart_only_on_linux_and_macos_and_only_once():
    assert can_restart({}, "linux") and can_restart({}, "darwin")
    assert not can_restart({}, "win32")
    assert not can_restart({RESTART_MARKER: "1"}, "linux")


def test_restart_command():
    assert restart_command(["--", "a.hs"], "/py", frozen=False) == ["/py", "-m", "pet_projection_data_visualization",
                                                                    "--", "a.hs"]
    assert restart_command(["a.hs"], "/app/Viewer", frozen=True) == ["/app/Viewer", "a.hs"]


@pytest.mark.parametrize("platform, var", [("linux", "LD_LIBRARY_PATH"), ("darwin", "DYLD_LIBRARY_PATH")])
def test_restart_execs_once_with_the_library_path(tmp_path, platform, var):
    inst = fake_install(tmp_path / "inst")
    calls = []
    environ = {"HOME": "/h"}
    assert restart_viewer(locate_stir(str(inst)), ["--", "a.hs"], environ, platform, python="/py",
                          exec_fn=lambda exe, argv, env: calls.append((exe, argv, env)))
    (exe, argv, env), = calls
    assert exe == "/py" and argv == ["/py", "-m", "pet_projection_data_visualization", "--", "a.hs"]
    assert env[var] == str(inst / "lib") and env["PYTHONPATH"] == str(inst / "python") and env[RESTART_MARKER] == "1"
    # the restarted viewer has the marker: it never restarts again
    assert not restart_viewer(locate_stir(str(inst)), ["a.hs"], env, platform, exec_fn=lambda *a: calls.append(a))
    assert len(calls) == 1


def test_no_restart_on_windows(tmp_path):
    calls = []
    assert not restart_viewer(StirLocation(str(tmp_path), str(tmp_path)), [], {}, "win32",
                              exec_fn=lambda *a: calls.append(a))
    assert calls == []


def test_the_restarted_environment_imports_the_fake_stir(tmp_path):
    """What the restart would exec, run as a child process that only imports stir."""
    inst = fake_install(tmp_path / "inst", "MARK = 'restarted'\n")
    seen = []
    restart_viewer(locate_stir(str(inst)), [], dict(os.environ), "linux", exec_fn=lambda e, a, env: seen.append(env))
    out = subprocess.run([sys.executable, "-c", "import os, stir; print(stir.MARK, os.environ['PET_PDV_STIR_RESTARTED'])"],
                         env=seen[0], capture_output=True, text=True, check=True, cwd=tmp_path)
    assert out.stdout.split() == ["restarted", "1"]


# ---- the actions behind the setup window ---------------------------------------------------
def test_actions_initial_path_follows_the_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    file = tmp_path / "c.json"
    assert StirSetupActions(config_file=file).initial_path() == ""
    save_path("/saved", file)
    assert StirSetupActions(config_file=file).initial_path() == os.path.abspath("/saved")
    monkeypatch.setenv(ENV_VAR, "/env")
    assert StirSetupActions(config_file=file).initial_path() == "/env"
    assert StirSetupActions("/cli", config_file=file).initial_path() == "/cli"


def test_actions_test_save_and_apply_with_restart(tmp_path):
    inst = fake_install(tmp_path / "inst")
    restarts = []
    actions = StirSetupActions("/wrong", theme="light", restartable=True, config_file=tmp_path / "c.json",
                               restart=lambda loc, args: restarts.append((loc, args)) or True)
    assert actions.test(str(inst)).ok
    assert actions.save(str(inst)) == str(tmp_path / "c.json")
    assert load_saved_path(tmp_path / "c.json") == str(inst)
    actions.apply(str(inst), "-odd name.hs")
    assert actions.stir_path == str(inst)                 # used from now on, above the wrong --stir-path
    (loc, args), = restarts
    assert loc == locate_stir(str(inst))
    assert args == ["--stir-path", str(inst), "--theme", "light", "--", "-odd name.hs"]


def test_actions_apply_without_restart_only_switches_the_path(tmp_path):
    restarts = []
    actions = StirSetupActions(None, restartable=False, restart=lambda *a: restarts.append(a) or True)
    actions.apply(str(tmp_path), "a.hs")
    assert actions.stir_path == str(tmp_path) and restarts == []


def test_restarted_args_parse_back_to_the_same_launch(tmp_path):
    from pet_projection_data_visualization.cli import build_parser
    a = build_parser().parse_args(["--stir-path", "/s", "--theme", "light", "--", "-odd.hs"])
    assert (a.path, a.stir_path, a.theme) == ("-odd.hs", "/s", "light")
