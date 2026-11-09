# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""MODEL layer: pure domain logic. Imports only the standard library and numpy: no Qt, no STIR,
no view-model code (enforced by tests/test_architecture.py)."""
from .dataset import ProjDataset
from .info import ProjDataInfo, ProjDataSource
from .selection import DIMENSIONS, Selection, SliceMode, TofMode
from .slices import SliceImage, SliceStats, compute_stats, finite_range
from .stir_setup import StirCheck, StirNotFoundError

__all__ = ["DIMENSIONS", "ProjDataInfo", "ProjDataSource", "ProjDataset", "Selection",
           "SliceImage", "SliceMode", "SliceStats", "StirCheck", "StirNotFoundError", "TofMode",
           "compute_stats", "finite_range"]
