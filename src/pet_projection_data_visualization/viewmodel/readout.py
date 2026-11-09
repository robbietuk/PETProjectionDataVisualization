# SPDX-License-Identifier: Apache-2.0
"""VIEWMODEL layer: which corner of the image the cursor readout sits in (Qt-free, no state).

The readout floats over a corner of the image. When the cursor comes close to that corner, the
readout moves to another corner so it never hides what the cursor points at. It stays where it is
until the cursor comes close again, so it does not jump about while the cursor moves.
"""
from __future__ import annotations

from enum import Enum

NEAR = 0.4      # "close to a corner": within this fraction of the image width and height of it


class Corner(Enum):
    TOP_RIGHT = "top right"
    TOP_LEFT = "top left"
    BOTTOM_RIGHT = "bottom right"
    BOTTOM_LEFT = "bottom left"

    @property
    def right(self) -> bool:
        return self in (Corner.TOP_RIGHT, Corner.BOTTOM_RIGHT)

    @property
    def bottom(self) -> bool:
        return self in (Corner.BOTTOM_RIGHT, Corner.BOTTOM_LEFT)


DEFAULT_CORNER = Corner.TOP_RIGHT
# where to go when the cursor is close: the other corner on the same edge first, then the opposite edge
_PREFERENCE = (Corner.TOP_RIGHT, Corner.TOP_LEFT, Corner.BOTTOM_RIGHT, Corner.BOTTOM_LEFT)


def near_corner(corner: Corner, fx: float, fy: float, near: float = NEAR) -> bool:
    """Is the cursor at ``(fx, fy)`` close to ``corner``? ``fx`` runs 0 (left) .. 1 (right) and ``fy``
    0 (top) .. 1 (bottom) over the image; outside that range the cursor is off the image."""
    if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
        return False
    close_x = fx >= 1.0 - near if corner.right else fx <= near
    close_y = fy >= 1.0 - near if corner.bottom else fy <= near
    return close_x and close_y


def readout_corner(current: Corner, fx: float | None, fy: float | None, near: float = NEAR) -> Corner:
    """The corner for the readout with the cursor at ``(fx, fy)`` (None: no cursor). Stays in
    ``current`` unless the cursor is close to it; then the first corner, in the order top right, top
    left, bottom right, bottom left, that the cursor is not close to."""
    if fx is None or fy is None or not near_corner(current, fx, fy, near):
        return current
    return next(c for c in _PREFERENCE if not near_corner(c, fx, fy, near))
