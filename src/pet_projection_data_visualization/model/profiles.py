# SPDX-License-Identifier: Apache-2.0
"""Line profiles through a 2D slice: exact rows and columns, or samples along a free line.

Positions are in *axis coordinates*: bin numbers of the image's column axis (x) and row axis (y), where
an integer is a pixel centre (as in ``SliceImage.pixel_from_axes``).
"""
from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from .slices import SliceImage

FloatArray = npt.NDArray[np.float64]


def axis_profile(image: SliceImage, along: str, row: int, col: int) -> tuple[FloatArray, FloatArray]:
    """The exact bins of ``image`` through pixel ``(row, col)`` along the axis named ``along`` (the
    image's column axis: the row through the pixel; its row axis: the column). Returns (bin numbers
    along that axis, values). Raises if the pixel is outside the image or ``along`` is not an axis of it."""
    rows, cols = image.shape
    if not (0 <= row < rows and 0 <= col < cols):
        raise ValueError(f"pixel ({row}, {col}) is outside the {rows} x {cols} image")
    data = np.asarray(image.data, dtype=np.float64)
    if along == image.col_axis:
        return np.arange(cols, dtype=np.float64) + image.col_origin, data[row, :].copy()
    if along == image.row_axis:
        return np.arange(rows, dtype=np.float64) + image.row_origin, data[:, col].copy()
    raise KeyError(f"{along!r} is not an axis of the image ({image.row_axis} x {image.col_axis})")


def line_positions(start: tuple[float, float], end: tuple[float, float]) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Sample points along the line ``start`` -> ``end`` (each ``(x, y)`` in axis coordinates), about one
    per bin of length and at least two. Returns (distance from ``start`` in bins, x, y)."""
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0)
    t = np.linspace(0.0, 1.0, max(2, math.ceil(length) + 1))
    return t * length, x0 + t * (x1 - x0), y0 + t * (y1 - y0)


def sample_bilinear(image: SliceImage, x: npt.ArrayLike, y: npt.ArrayLike) -> FloatArray:
    """Values of ``image`` at axis coordinates ``(x, y)``, interpolated bilinearly between pixel centres.
    Points within half a pixel outside the outer centres take the edge values; points further out are NaN."""
    data = np.asarray(image.data, dtype=np.float64)
    rows, cols = image.shape
    r = np.asarray(y, dtype=np.float64) - image.row_origin
    c = np.asarray(x, dtype=np.float64) - image.col_origin
    inside = (r >= -0.5) & (r <= rows - 0.5) & (c >= -0.5) & (c <= cols - 0.5)
    r = np.clip(r, 0.0, rows - 1.0)
    c = np.clip(c, 0.0, cols - 1.0)
    r0 = np.minimum(np.floor(r).astype(np.intp), rows - 1)
    c0 = np.minimum(np.floor(c).astype(np.intp), cols - 1)
    r1 = np.minimum(r0 + 1, rows - 1)
    c1 = np.minimum(c0 + 1, cols - 1)
    fr, fc = r - r0, c - c0
    top = data[r0, c0] * (1 - fc) + data[r0, c1] * fc
    bottom = data[r1, c0] * (1 - fc) + data[r1, c1] * fc
    values = top * (1 - fr) + bottom * fr
    return np.where(inside, values, np.nan)


def line_profile(image: SliceImage, start: tuple[float, float], end: tuple[float, float]) -> tuple[FloatArray, FloatArray]:
    """Values along the line ``start`` -> ``end`` (axis coordinates), interpolated (``sample_bilinear``).
    Returns (distance from ``start`` in bins, values); NaN where the line leaves the image."""
    distance, x, y = line_positions(start, end)
    return distance, sample_bilinear(image, x, y)
