# SPDX-License-Identifier: Apache-2.0
"""Per-test watchdog: a test that runs longer than ``PET_PDV_TEST_TIMEOUT`` seconds (default 300, 0 turns
it off) prints the traceback of every thread and ends the pytest process with a failure.

A stuck test otherwise runs until the CI job's timeout, and GitHub keeps no log of a cancelled step, so
nobody can see where it hung (the real-STIR Windows jobs did this). This uses only the standard library
(``faulthandler``), so it adds no dependency.
"""
from __future__ import annotations

import faulthandler
import os
from collections.abc import Generator, Mapping

import pytest

ENV_VAR = "PET_PDV_TEST_TIMEOUT"
DEFAULT_TIMEOUT_S = 300.0

_stderr_fd: int | None = None


def timeout_seconds(environ: Mapping[str, str] = os.environ) -> float:
    """The per-test limit in seconds; 0 when the watchdog is off."""
    raw = environ.get(ENV_VAR, "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_S
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_TIMEOUT_S


def pytest_configure(config: pytest.Config) -> None:
    # Output capturing is suspended here, so fd 2 is the real stderr. Keep a copy: during a test fd 2 is
    # redirected into pytest's capture file, which is lost when the watchdog ends the process.
    global _stderr_fd
    if _stderr_fd is None:
        _stderr_fd = os.dup(2)


def pytest_unconfigure(config: pytest.Config) -> None:
    global _stderr_fd
    faulthandler.cancel_dump_traceback_later()
    if _stderr_fd is not None:
        os.close(_stderr_fd)
        _stderr_fd = None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None) -> Generator[None, None, None]:
    limit = timeout_seconds()
    if limit > 0 and _stderr_fd is not None:
        faulthandler.dump_traceback_later(limit, exit=True, file=_stderr_fd)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()
