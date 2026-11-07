# SPDX-License-Identifier: Apache-2.0
"""Session-wide test hooks."""
import os
import sys

import pytest

_exit_status = 0

# PySide6 6.12 on Python 3.11 loses a reference to None on calls into Python overrides from C++ (a gdb
# backtrace on the Linux CI runner showed "none_dealloc: deallocating None" under QGraphicsView::paintEvent ->
# a pyqtgraph paint() override). From Python 3.12 None is immortal, so only 3.11 is affected: there the
# test run aborts once enough items have been painted. Holding extra references to None keeps its count
# from reaching zero during the run. Test process only; see the pull request for the application side.
if sys.version_info < (3, 12):
    _NONE_REFS = [None] * 2_000_000


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
