# SPDX-License-Identifier: Apache-2.0
"""Session-wide test hooks."""
import os
import sys

import pytest

_exit_status = 0


def pytest_sessionfinish(session, exitstatus):
    global _exit_status
    _exit_status = int(exitstatus)


def _skip_interpreter_shutdown(config) -> bool:
    """Only for a command-line pytest run on Linux CI with Qt loaded.

    PySide6/shiboken can crash while the interpreter finalises ("bool_dealloc: deallocating True or False",
    exit code 134), seen on Linux CI with Python 3.11 after every test had passed. Locally, in IDE runners,
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
