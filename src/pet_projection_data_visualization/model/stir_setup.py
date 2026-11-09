# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Plain types shared by the STIR lookup (``stir_interface``) and the setup window's view model.

They live here so the view model can tell "STIR is missing" from any other load failure without
importing ``stir_interface``.
"""
from __future__ import annotations

from dataclasses import dataclass


class StirNotFoundError(ImportError):
    """The STIR Python module could not be imported."""


@dataclass(frozen=True)
class StirCheck:
    """The result of trying to import STIR from a folder."""

    ok: bool
    message: str
    version_mismatch: bool = False   # the folder's STIR was built for another Python version
