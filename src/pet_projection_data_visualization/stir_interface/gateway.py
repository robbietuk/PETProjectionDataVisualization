# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""The narrow interface the viewer needs from STIR, expressed without any STIR types.

Two implementations are expected: ``SwigStirGateway`` (the real thing) and test fakes.
Nothing above this layer ever sees a ``stir`` object.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from ..model.stir_setup import StirNotFoundError

__all__ = ["ProjDataLayout", "StirGateway", "StirNotFoundError", "StirProjDataHandle"]


@dataclass(frozen=True)
class ProjDataLayout:
    """Index ranges (inclusive) as reported by STIR."""

    min_segment: int
    max_segment: int
    min_view: int
    max_view: int
    min_tangential: int
    max_tangential: int
    min_tof: int
    max_tof: int
    axial_ranges: dict[int, tuple[int, int]]


@runtime_checkable
class StirProjDataHandle(Protocol):
    """One opened projection data set."""

    name: str

    def layout(self) -> ProjDataLayout: ...

    def metadata(self) -> dict[str, str]:
        """Best-effort descriptive (label, value) pairs; may be empty."""
        ...

    def read_segment(self, segment: int, tof_bin: int) -> npt.NDArray[np.float32]:
        """float32 array of shape (views, axial, tangential); must be validated by the implementation."""
        ...

    def read_sinogram(self, segment: int, axial: int, tof_bin: int) -> npt.NDArray[np.float32]:
        """float32 array of shape (views, tangential): one sinogram, much cheaper than a segment."""
        ...


@runtime_checkable
class StirGateway(Protocol):
    def open(self, filename: str) -> StirProjDataHandle:
        """Read a projection data file. Raises ``OSError`` if STIR cannot read it."""
        ...

    def wrap(self, projdata: object) -> StirProjDataHandle:
        """Wrap an already-loaded ``stir.ProjData`` object (opaque at this level: no STIR types here)."""
        ...
