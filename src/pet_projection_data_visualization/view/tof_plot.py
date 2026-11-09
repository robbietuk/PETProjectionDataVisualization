# SPDX-License-Identifier: Apache-2.0
"""VIEW layer: the ViewBox of the TOF profile plot.

The x-axis (TOF bin) is fixed to every bin of the data set; the mouse wheel, drag, double-click and
pyqtgraph's "A" (auto-range) button act on the y-axis (counts) only.
"""
from __future__ import annotations

from collections.abc import Sequence

import pyqtgraph as pg
from PySide6 import QtCore

from ._compat import override

X_MARGIN_BINS = 0.5          # margin on each side of the first and last TOF bin, in bins
X_MARGIN_FRACTION = 0.05     # ... or this fraction of the bin span, if larger


def tof_x_limits(first: int, last: int) -> tuple[float, float]:
    """The fixed x-range for TOF bins ``first..last``: all of them, with a small margin."""
    margin = max(X_MARGIN_BINS, X_MARGIN_FRACTION * (last - first))
    return first - margin, last + margin


class TofViewBox(pg.ViewBox):
    """A ViewBox whose x-range is set only by ``set_tof_range``; mouse and auto-range work on y."""

    def __init__(self) -> None:
        super().__init__()
        self.setMouseEnabled(x=False, y=True)
        self._auto_range(pg.ViewBox.XAxis, False)
        self._auto_range(pg.ViewBox.YAxis, True)

    def _auto_range(self, axis: int, enable: bool | float) -> None:
        pg.ViewBox.enableAutoRange(self, axis, enable)      # pyqtgraph's own, bypassing the y-only override

    @override
    def enableAutoRange(self, axis: int | str | None = None, enable: bool | float = True,
                        x: bool | float | None = None, y: bool | float | None = None) -> None:
        """Auto-range applies to y only: the "A" button and ``enableAutoRange()`` refit the counts and
        never move the TOF bins."""
        if x is not None or y is not None:
            if y is not None:
                self._auto_range(pg.ViewBox.YAxis, y)
            return
        if axis in (pg.ViewBox.XAxis, "x"):
            return
        self._auto_range(pg.ViewBox.YAxis, enable)

    @override
    def mouseClickEvent(self, ev: pg.MouseClickEvent) -> None:
        if ev.double() and ev.button() == QtCore.Qt.MouseButton.LeftButton:
            ev.accept()
            self.enableAutoRange(y=True)          # double-click: fit the y-axis to the profile again
            return
        super().mouseClickEvent(ev)

    def set_tof_range(self, first: int, last: int) -> None:
        """Show TOF bins ``first..last`` and stop the x-axis from moving away from them."""
        lo, hi = tof_x_limits(first, last)
        self.setLimits(xMin=lo, xMax=hi)
        self.setXRange(lo, hi, padding=0)

    def set_counts(self, counts: Sequence[float]) -> None:
        """Keep y from being panned below 0 when every count is ≥ 0 (lifted again for other data)."""
        self.setLimits(yMin=0.0 if counts and min(counts) >= 0 else None)
