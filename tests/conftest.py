# SPDX-License-Identifier: Apache-2.0
"""Session-wide test hooks."""
import os
import sys

import pytest

from pet_projection_data_visualization._refcount_guard import protect_singletons

_exit_status = 0

# a hung test fails with a traceback instead of running into the CI job's timeout (see the module)
pytest_plugins = ["_test_watchdog"]

# PySide6 6.12.0 on Linux over-releases None/True/False; on Python 3.11 (not immortal yet) that aborts the
# run with exit status 134. Same guard as the application uses in app.launch; see _refcount_guard.
protect_singletons()


@pytest.fixture(autouse=True)
def _private_config_dir(tmp_path_factory, monkeypatch):
    """Never read or write the real per-user settings (the saved STIR path) from a test."""
    monkeypatch.setenv("PET_PDV_CONFIG_DIR", str(tmp_path_factory.mktemp("config")))
    monkeypatch.delenv("PET_PDV_STIR_RESTARTED", raising=False)


def pytest_sessionfinish(session, exitstatus):
    global _exit_status
    _exit_status = int(exitstatus)


def _skip_interpreter_shutdown(config) -> bool:
    """Only for a command-line pytest run on Linux CI with Qt loaded.

    PySide6/shiboken can crash while the interpreter finalises ("bool_dealloc: deallocating True or False",
    exit code 134), seen on Linux CI with Python 3.11 after every test had passed. That was most likely the
    PySide6 6.12.0 reference-count bug that ``protect_singletons`` above now guards against; this stays as a
    second line of defence for interpreter shutdown. Locally, in IDE runners,
    under ``coverage``, or when pytest is called in-process (``pytest.main``), normal shutdown is kept.
    """
    return (
        bool(os.environ.get("CI"))
        and sys.platform.startswith("linux")
        and "PySide6.QtCore" in sys.modules
        and os.path.basename(sys.argv[0] or "") in ("pytest", "py.test", "__main__.py")
    )


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    # By now pytest has printed its summary and written the JUnit XML; leave without finalising, keeping
    # pytest's own exit status.
    if _skip_interpreter_shutdown(config):
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_exit_status)
