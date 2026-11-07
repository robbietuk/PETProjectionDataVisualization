# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly.
"""Keep ``None``, ``True`` and ``False`` alive on Python 3.11 (PySide6 6.12.0 over-releases them).

PySide6 6.12.0 on Linux gives back references to ``None``, ``True`` and ``False`` that it never took,
on calls into Python overrides from C++ (pyqtgraph's ``paint()``, for example). Measured on the
GitHub Linux runner with Python 3.11: about -64 references to ``None`` for each repaint of a
pyqtgraph ``HistogramLUTItem``, and -1 for each ``pg.mkPen``. PySide6 6.8.3, 6.9.3, 6.10.3 and 6.11.3
on Linux, and 6.12.0 on macOS and Windows, lose nothing. From Python 3.12 these objects are immortal
(PEP 683), so nothing happens there. On 3.11 the count reaches zero and Python aborts
("none_dealloc: deallocating None" or "bool_dealloc: deallocating True or False", exit status 134),
in the viewer after a few seconds of playback.

``pyproject.toml`` keeps pip from installing PySide6 6.12 with Python < 3.12. This guard covers what a
pip marker does not reach (conda environments, a later PySide6 with the same bug): it raises the
reference count of the three objects by 2**40 once, which is what immortality does in 3.12. At even
a million lost references a second that lasts for more than a week; the objects are never freed
anyway. Used by ``app.launch`` and by the test suite (``tests/conftest.py``).
"""
from __future__ import annotations

import ctypes
import sys

EXTRA_REFERENCES = 1 << 40
SINGLETONS = (None, True, False)


def needs_guard(version_info: tuple = tuple(sys.version_info),
                implementation: str = sys.implementation.name) -> bool:
    """True for CPython before 3.12, where ``None``, ``True`` and ``False`` are not immortal."""
    return implementation == "cpython" and tuple(version_info[:2]) < (3, 12)


def protect_singletons() -> bool:
    """Make ``None``, ``True`` and ``False`` effectively immortal on CPython < 3.12. Idempotent; a
    no-op (returning False) where it is not needed or not safe (debug builds that trace references)."""
    if not needs_guard() or hasattr(sys, "getobjects"):   # Py_TRACE_REFS: ob_refcnt is not first
        return False
    for obj in SINGLETONS:
        if sys.getrefcount(obj) < EXTRA_REFERENCES:
            # ob_refcnt is the first field (a Py_ssize_t) of every object in a release build
            ctypes.c_ssize_t.from_address(id(obj)).value += EXTRA_REFERENCES
    return True
