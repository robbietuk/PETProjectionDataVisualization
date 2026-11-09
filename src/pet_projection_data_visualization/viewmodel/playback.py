# SPDX-License-Identifier: Apache-2.0
"""VIEWMODEL layer: what one playback step does (Qt-free, no state).

Playback steps one axis (segment, axial, view, tangential or TOF bin) through its range. At an end
it either wraps to the other end (``LOOP``) or turns round (``BOUNCE``).
"""
from __future__ import annotations

from enum import Enum


class PlayMode(Enum):
    LOOP = "Loop"        # ... hi-1, hi, lo, lo+1 ...
    BOUNCE = "Bounce"    # ... hi-1, hi, hi-1 ...


def next_play_value(value: int, lo: int, hi: int, direction: int, mode: PlayMode) -> tuple[int, int]:
    """The value after ``value`` in ``lo..hi`` (inclusive) and the direction (+1 or -1) to go on in.

    ``value`` outside the range is clamped first. A range of one value stays put."""
    direction = 1 if direction >= 0 else -1
    value = min(max(value, lo), hi)
    if hi <= lo:
        return lo, direction
    if mode is PlayMode.LOOP:
        return lo + (value - lo + direction) % (hi - lo + 1), direction
    nxt = value + direction
    if nxt > hi or nxt < lo:            # turn round at an end
        direction = -direction
        nxt = value + direction
    return nxt, direction
