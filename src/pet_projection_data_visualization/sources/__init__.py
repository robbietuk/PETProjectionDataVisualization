# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Data providers that implement the model's ``ProjDataSource`` without STIR."""
from .array_source import ArraySource
from .demo import make_demo_source

__all__ = ["ArraySource", "make_demo_source"]
