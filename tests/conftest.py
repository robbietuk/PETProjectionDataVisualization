# SPDX-License-Identifier: Apache-2.0
"""Session-wide test hooks."""
import os
import sys

import pytest

_exit_status = 0


def pytest_sessionfinish(session, exitstatus):
    global _exit_status
    _exit_status = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    # PySide6/shiboken can crash while the interpreter finalises ("bool_dealloc: deallocating True or
    # False", exit code 134), seen on Linux CI with Python 3.11 after every test had passed. By now pytest
    # has printed its summary and written the JUnit XML, so leave without finalising when Qt was loaded,
    # keeping pytest's own exit status. Only matters for the test process, not for the app.
    if "PySide6.QtCore" in sys.modules:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_exit_status)
