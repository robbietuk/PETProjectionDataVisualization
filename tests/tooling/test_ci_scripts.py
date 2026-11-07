# SPDX-License-Identifier: Apache-2.0
"""The CI helper scripts: scripts/ci_annotate.py, scripts/ci_stir_env.sh, scripts/ci_smoke.py."""
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- ci_annotate: pytest log -> GitHub error annotations ---------------------------------------------------
def test_annotate_reports_each_failure_and_the_log_tail(tmp_path, capsys):
    ann = _load("ci_annotate")
    log = tmp_path / "pytest.log"
    log.write_text("collected 3\nFAILED tests/a.py::t1 - assert 1 == 2\nERROR tests/b.py - ImportError\n100% done\n")
    assert ann.main(str(log)) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "::error title=pytest::FAILED tests/a.py::t1 - assert 1 == 2"
    assert out[1] == "::error title=pytest::ERROR tests/b.py - ImportError"
    assert out[2].startswith("::error title=pytest log tail::collected 3%0AFAILED")
    assert "\n" not in "".join(out)                                  # one annotation per line


def test_annotate_escapes_workflow_command_characters():
    ann = _load("ci_annotate")
    assert ann._escape("50% done\r\nnext") == "50%25 done%0D%0Anext"


def test_annotate_never_fails_the_step_without_a_log(tmp_path, capsys):
    ann = _load("ci_annotate")
    assert ann.main(str(tmp_path / "missing.log")) == 0
    assert capsys.readouterr().out.startswith("::error title=pytest::no log")


# ---- ci_stir_env.sh: keep a working STIR_CONFIG_DIR, else use the recorded folder ----------------------------
needs_bash = pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32",
                                reason="sourced by bash steps in CI")


def _stir_env(cwd, config_dir):
    env = {k: v for k, v in os.environ.items() if k != "STIR_CONFIG_DIR"}
    if config_dir is not None:
        env["STIR_CONFIG_DIR"] = str(config_dir)
    r = subprocess.run(["bash", "-c", f'source "{SCRIPTS / "ci_stir_env.sh"}" >/dev/null; printf %s "$STIR_CONFIG_DIR"'],
                       cwd=cwd, env=env, capture_output=True, text=True, check=True)
    return r.stdout


@needs_bash
def test_stir_env_replaces_a_config_dir_without_stirs_tables(tmp_path):
    real = tmp_path / "Library" / "share" / "STIR-6.4" / "config"
    real.mkdir(parents=True)
    (real / "radionuclide_info.json").write_text("{}")
    (tmp_path / ".stir_config_dir").write_text(f"{real}\n")
    assert _stir_env(tmp_path, tmp_path / "share" / "STIR-6.3" / "config") == str(real)   # the win-64 case
    assert _stir_env(tmp_path, None) == str(real)


@needs_bash
def test_stir_env_keeps_a_config_dir_that_works(tmp_path):
    good = tmp_path / "good"
    good.mkdir()
    (good / "radionuclide_info.json").write_text("{}")
    (tmp_path / ".stir_config_dir").write_text(str(tmp_path / "other"))
    assert _stir_env(tmp_path, good) == str(good)


@needs_bash
def test_stir_env_leaves_things_alone_when_nothing_was_recorded(tmp_path):
    assert _stir_env(tmp_path, None) == ""


# ---- ci_smoke: the real window, headless -----------------------------------------------------------------------
def test_smoke_runs_the_real_window_on_the_demo_and_rejects_a_bad_path(tmp_path):
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               PYTHONPATH=os.pathsep.join([str(ROOT / "src"), os.environ.get("PYTHONPATH", "")]))
    shot = tmp_path / "shot.png"
    ok = subprocess.run([sys.executable, str(SCRIPTS / "ci_smoke.py"), "--demo", "--out", str(shot)],
                        env=env, capture_output=True, text=True, timeout=120)
    assert ok.returncode == 0, ok.stderr
    assert shot.stat().st_size > 0 and "ok: demo" in ok.stdout
    bad = subprocess.run([sys.executable, str(SCRIPTS / "ci_smoke.py"), str(tmp_path / "nope.hs")],
                         env=env, capture_output=True, text=True, timeout=120)
    assert bad.returncode == 1 and "No such file" in bad.stderr
