# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""``override`` for Python 3.11.

``typing.override`` exists from Python 3.12 and ``typing_extensions`` is not a dependency, so type checkers
read the decorator from typeshed's stub of ``typing_extensions``; at run time it is a no-op.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import override as override
else:
    def override(method):
        return method

__all__ = ["override"]
