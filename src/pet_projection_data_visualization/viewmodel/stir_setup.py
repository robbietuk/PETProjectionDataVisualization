# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""View model of the STIR setup window, shown when a STIR file is opened and ``stir`` cannot be imported.

The real work (testing an import, writing the config file, restarting) is injected as a
``StirSetupService``, so this file knows nothing about STIR, the file system or Qt.
"""
from __future__ import annotations

import os
import sys
from typing import Protocol

from ..model import StirCheck
from .formatting import clean_path
from .observable import Observed, ObservableObject


class StirSetupService(Protocol):
    def initial_path(self) -> str:
        """The path to show first (the one tried, if any), or ""."""
        ...

    def test(self, path: str) -> StirCheck:
        """Try to import STIR from ``path`` without affecting this process."""
        ...

    def save(self, path: str) -> str:
        """Store ``path`` for every later start; returns where it was stored."""
        ...

    def apply(self, path: str, file: str) -> None:
        """Use ``path`` from now on. May restart the viewer with ``file`` (then it does not return)."""
        ...


PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"

EXPLANATION = (
    "Opening {name} needs STIR's Python module ('stir'), and this viewer could not import it. STIR is not "
    "installed together with the viewer from PyPI: tell it where your STIR installation is. The path is "
    "saved for every later start.")

HOW_TO = (
    "Where to find STIR:\n"
    "  \N{BULLET} conda: the environment folder, e.g. ~/miniforge3/envs/stir (list them with "
    "'conda env list'). STIR comes from 'conda install -c conda-forge stir'.\n"
    "  \N{BULLET} source build: the CMAKE_INSTALL_PREFIX you installed STIR to (the folder containing "
    "python/stir), or that python folder itself.\n"
    f"STIR must be built for Python {PYTHON_VERSION}, the one running this viewer.")


class StirSetupViewModel(ObservableObject):
    path: Observed[str] = Observed("")
    result: Observed[StirCheck | None] = Observed(None)     # the last Test (or failed Save) result
    saved_path: Observed[str | None] = Observed(None)       # set by a successful Save

    def __init__(self, service: StirSetupService, file: str) -> None:
        super().__init__()
        self._service = service
        self.file = file
        self.explanation = EXPLANATION.format(name=os.path.basename(file) or file)
        self.how_to = HOW_TO
        self.path = service.initial_path()

    def set_path(self, text: str) -> None:
        """The user typed or browsed; an old Test result no longer applies."""
        with self.transaction():
            self.path = text
            self.result = None

    def test(self) -> StirCheck:
        path = clean_path(self.path)
        check = self._service.test(path)
        with self.transaction():
            self.result = check
            self._mark_changed("result")  # re-announced even if unchanged: the view showed "Testing..." meanwhile
        return check

    def save(self) -> bool:
        """Test, then store the path if STIR imports from it. Returns True when saved (the window closes)."""
        path = clean_path(self.path)
        with self.transaction():
            self._mark_changed("result")
            check = self._service.test(path)
            if not check.ok:
                self.result = StirCheck(False, f"Not saved: {check.message}", check.version_mismatch)
                return False
            where = self._service.save(path)
            self.result = StirCheck(True, f"Saved to {where}.")
            self.saved_path = path
        return True

    def apply(self) -> None:
        """After a successful Save: make the path take effect (may restart the viewer)."""
        if self.saved_path is not None:
            self._service.apply(self.saved_path, self.file)
