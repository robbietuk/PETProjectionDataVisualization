# SPDX-License-Identifier: Apache-2.0
"""Session-wide test hooks."""
import sys


def pytest_sessionfinish(session, exitstatus):
    # pyqtgraph registers an atexit cleanup that walks Qt graphics items while Qt itself is being torn down.
    # On Linux CI with Python 3.11 that aborted the interpreter (exit code 134) after every test had passed.
    # Only touch pyqtgraph if a test already imported it: the Qt-free layers must stay Qt-free.
    pg = sys.modules.get("pyqtgraph")
    if pg is not None:
        pg.setConfigOption("exitCleanup", False)
