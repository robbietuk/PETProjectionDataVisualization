# SPDX-License-Identifier: Apache-2.0
"""VIEWMODEL layer: what the profile plots of a pane show (Qt-free, no state).

* The **TOF profile** is the counts in every TOF bin of one LOR. With a single bin shown the plot marks
  that bin; with TOF collapsed (Sum, Mean or Max) it is shown as context, and the collapsed value the
  image shows is drawn as a reference line.
* The **line profile** reads the image as displayed (a single TOF bin, or Sum/Mean/Max), in data units:
  ``ROW`` and ``COLUMN`` take the exact bins of the image row or column through a pixel, ``FREE`` samples
  a line drawn anywhere on the image (interpolated, against the distance in bins). For TOF data it can
  add one curve per TOF bin along the same line (``overlay``).

An LOR is a dict with the ``segment``, ``view``, ``axial`` and ``tangential`` bin numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

import numpy as np
import numpy.typing as npt

from ..model import ProjDataset, Selection, SliceImage, TofMode, axis_profile, line_profile
from . import formatting

Lor = dict[str, int]
FreeLine = tuple[float, float, float, float]      # x0, y0, x1, y1 in axis coordinates of the image
LOR_AXES = ("segment", "view", "axial", "tangential")
FREE_LINE_INSET = 0.15        # the default free line runs corner to corner, this fraction in from the edges


class LineMode(Enum):
    ROW = "Row"            # along the image's column axis, through the pixel's row
    COLUMN = "Column"      # along the image's row axis, through the pixel's column
    FREE = "Free"          # along a line drawn on the image


@dataclass(frozen=True)
class TofProfile:
    x: tuple[int, ...]
    y: tuple[float, ...]
    title: str
    context: str = ""                    # set while TOF is collapsed: what the plot shows next to the image
    reference: float | None = None       # the collapsed value the image shows for this LOR (Sum, Mean or Max)


@dataclass(frozen=True)
class LineProfile:
    x: tuple[float, ...]
    y: tuple[float, ...]                 # NaN where a free line leaves the image
    x_label: str
    title: str
    overlay: tuple[tuple[float, ...], ...] = ()   # one curve per TOF bin, at the same x
    overlay_bins: tuple[int, ...] = ()


def lor_at(sel: Selection, image: SliceImage, row: int, col: int) -> Lor:
    """The LOR of pixel ``(row, col)`` of ``image``, the current slice of ``sel``."""
    lor = {d: sel.get(d) for d in LOR_AXES}
    lor.update(image.indices_at(row, col))
    return lor


def image_position(image: SliceImage, lor: Lor) -> tuple[float, float]:
    """Where ``lor`` lies on ``image`` in axis coordinates ``(x, y)``: its bins on the column and row axes."""
    return float(lor[image.col_axis]), float(lor[image.row_axis])


def pixel_of(image: SliceImage, lor: Lor) -> tuple[int, int] | None:
    """``(row, col)`` of ``lor`` on ``image``, or None if it lies outside it."""
    row, col = lor[image.row_axis] - image.row_origin, lor[image.col_axis] - image.col_origin
    rows, cols = image.shape
    return (row, col) if 0 <= row < rows and 0 <= col < cols else None


def line_axis_names(image: SliceImage) -> tuple[str, str]:
    """What ``ROW`` and ``COLUMN`` read on ``image``, e.g. ("along tangential", "along view") on a sinogram."""
    return f"along {image.col_axis}", f"along {image.row_axis}"


def default_free_line(image: SliceImage) -> FreeLine:
    """A free line across ``image`` from near its top-left corner to near its bottom-right one."""
    rows, cols = image.shape
    x0, y0 = image.col_origin - 0.5, image.row_origin - 0.5
    dx, dy = FREE_LINE_INSET * cols, FREE_LINE_INSET * rows
    return x0 + dx, y0 + dy, x0 + cols - dx, y0 + rows - dy


def collapsed_value(values: npt.NDArray[np.float64], mode: TofMode) -> float | None:
    """What the image shows for an LOR whose TOF bins hold ``values``, when TOF is collapsed by ``mode``."""
    if mode is TofMode.SUM:
        return float(values.sum())
    if mode is TofMode.MEAN:
        return float(values.mean())
    if mode is TofMode.MAX:
        return float(values.max())
    return None


def tof_profile(dataset: ProjDataset, sel: Selection, lor: Lor) -> TofProfile:
    """The counts in every TOF bin of ``lor`` (raises if it cannot be read). While ``sel`` collapses TOF it
    says so (``context``) and gives the collapsed value the image shows (``reference``)."""
    values = dataset.tof_profile(lor["segment"], lor["view"], lor["axial"], lor["tangential"])
    title = formatting.format_profile_title(lor["segment"], lor["view"], lor["axial"], lor["tangential"],
                                            float(values.sum()))
    reference = collapsed_value(values, sel.tof_mode)
    context = ""
    if reference is not None:
        how = sel.tof_mode.name.capitalize()
        context = f"TOF bins at this LOR (the image shows their {how}: {reference:.6g})"
    return TofProfile(tuple(dataset.info.tof_bins), tuple(float(v) for v in values), title, context, reference)


def line_profile_for(dataset: ProjDataset, sel: Selection, image: SliceImage, mode: LineMode, lor: Lor | None,
                     free_line: FreeLine | None, overlay: bool) -> LineProfile | None:
    """The line profile of ``image`` (the current slice of ``sel``): ``ROW``/``COLUMN`` through ``lor``
    (None if there is no LOR or it lies outside the image), ``FREE`` along ``free_line``. With ``overlay``
    (TOF data only) also one curve per TOF bin, read from that bin's slice along the same line."""
    def read(img: SliceImage) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        if mode is LineMode.FREE:
            assert free_line is not None
            x0, y0, x1, y1 = free_line
            return line_profile(img, (x0, y0), (x1, y1))
        assert pixel is not None
        along = img.col_axis if mode is LineMode.ROW else img.row_axis
        return axis_profile(img, along, *pixel)

    pixel: tuple[int, int] | None = None
    if mode is LineMode.FREE:
        if free_line is None:
            return None
        x_label = "distance (bins)"
        x0, y0, x1, y1 = free_line
        title = f"({image.col_axis}, {image.row_axis}) from ({x0:.1f}, {y0:.1f}) to ({x1:.1f}, {y1:.1f})"
    else:
        if lor is None or (pixel := pixel_of(image, lor)) is None:
            return None
        if mode is LineMode.ROW:
            x_label, fixed = image.col_axis, image.row_axis
        else:
            x_label, fixed = image.row_axis, image.col_axis
        title = f"along {x_label} at {fixed} {lor[fixed]}"
    x, y = read(image)
    curves: list[tuple[float, ...]] = []
    bins: tuple[int, ...] = ()
    if overlay and dataset.info.is_tof:
        bins = tuple(dataset.info.tof_bins)
        for k in bins:
            _, values = read(dataset.slice(replace(sel, tof_mode=TofMode.BIN, tof=k)))
            curves.append(tuple(float(v) for v in values))
    return LineProfile(tuple(float(v) for v in x), tuple(float(v) for v in y), x_label, title, tuple(curves), bins)
