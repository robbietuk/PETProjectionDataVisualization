# SPDX-License-Identifier: Apache-2.0
"""The per-test watchdog of tests/_test_watchdog.py, run in a child pytest so it can end that process."""
import os
import pathlib
import subprocess
import sys

import pytest
from _test_watchdog import DEFAULT_TIMEOUT_S, ENV_VAR, timeout_seconds

TESTS_DIR = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("raw", "expected"), [
    (None, DEFAULT_TIMEOUT_S), ("", DEFAULT_TIMEOUT_S), ("12.5", 12.5), ("0", 0.0), ("-3", 0.0),
    ("soon", DEFAULT_TIMEOUT_S),
])
def test_timeout_seconds(raw, expected):
    assert timeout_seconds({} if raw is None else {ENV_VAR: raw}) == expected


def _run_child_pytest(tmp_path: pathlib.Path, body: str, timeout: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "test_child.py").write_text(f"import time\n\n\ndef test_child():\n    {body}\n")
    env = {**os.environ, ENV_VAR: timeout,
           "PYTHONPATH": os.pathsep.join([str(TESTS_DIR), os.environ.get("PYTHONPATH", "")])}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "_test_watchdog", "-p", "no:cacheprovider",
         "--rootdir", str(tmp_path), "-c", os.devnull, str(tmp_path / "test_child.py")],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120, check=False)


def test_a_hung_test_ends_the_run_with_its_traceback(tmp_path):
    result = _run_child_pytest(tmp_path, "time.sleep(60)", timeout="1")
    assert result.returncode != 0
    assert "Timeout" in result.stderr and "test_child" in result.stderr, result.stderr


def test_a_quick_test_is_not_affected(tmp_path):
    result = _run_child_pytest(tmp_path, "time.sleep(0.01)", timeout="5")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
