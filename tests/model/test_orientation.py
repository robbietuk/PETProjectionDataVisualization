# SPDX-License-Identifier: Apache-2.0
"""Pins the image orientation documented in docs/ORIENTATION.md, on a small asymmetric fake.

Every bin holds ``100 * view + 10 * axial + tangential`` (bin numbers, not array indices), so a value names its
own bin. All three axes have different sizes and none starts at 0, so a transpose, a flip or an origin
slip changes what these tests see.
"""
import dataclasses

import numpy as np
import pytest

from pet_projection_data_visualization.model import ProjDataset, Selection, SliceMode
from pet_projection_data_visualization.sources import ArraySource

VIEWS = range(2, 6)         # 4 views, 2..5
AXIAL = range(5, 8)         # 3 axial positions, 5..7
TANG = range(-2, 3)         # 5 tangential positions, -2..2 (ArraySource centres them on zero)


def value(view: int, axial: int, tang: int) -> float:
    return float(100 * view + 10 * axial + tang)


@pytest.fixture
def ds() -> ProjDataset:
    arr = np.array([[[value(v, a, t) for t in TANG] for a in AXIAL] for v in VIEWS], dtype=np.float32)
    src = ArraySource({0: arr}, name="asymmetric")
    assert (src.info.min_tangential, src.info.max_tangential) == (TANG[0], TANG[-1])
    src.info = dataclasses.replace(src.info, min_view=VIEWS[0], max_view=VIEWS[-1],
                                   axial_ranges={0: (AXIAL[0], AXIAL[-1])})
    return ProjDataset(src)


def _slice(ds: ProjDataset, mode: SliceMode, **fixed: int):
    sel = Selection.initial(ds.info).with_slice_mode(mode)
    for dim, v in fixed.items():
        sel = sel.with_value(ds.info, dim, v)
    return ds.slice(sel)


def test_sinogram_rows_are_views_columns_are_tangential(ds):
    img = _slice(ds, SliceMode.SINOGRAM, axial=6)
    assert (img.row_axis, img.col_axis) == ("view", "tangential")
    assert (img.row_origin, img.col_origin) == (VIEWS[0], TANG[0])
    assert img.shape == (len(VIEWS), len(TANG))
    assert img.data[0, 0] == value(VIEWS[0], 6, TANG[0])           # first view, most negative tangential
    assert img.data[-1, 0] == value(VIEWS[-1], 6, TANG[0])          # rows go down through the views
    assert img.data[0, -1] == value(VIEWS[0], 6, TANG[-1])          # columns go right to positive tangential


def test_viewgram_rows_are_axial_columns_are_tangential(ds):
    img = _slice(ds, SliceMode.VIEWGRAM, view=3)
    assert (img.row_axis, img.col_axis) == ("axial", "tangential")
    assert (img.row_origin, img.col_origin) == (AXIAL[0], TANG[0])
    assert img.shape == (len(AXIAL), len(TANG))
    assert img.data[0, 0] == value(3, AXIAL[0], TANG[0])
    assert img.data[-1, 0] == value(3, AXIAL[-1], TANG[0])
    assert img.data[0, -1] == value(3, AXIAL[0], TANG[-1])


def test_tangential_slice_rows_are_views_columns_are_axial(ds):
    img = _slice(ds, SliceMode.TANGENTIAL, tangential=1)
    assert (img.row_axis, img.col_axis) == ("view", "axial")
    assert (img.row_origin, img.col_origin) == (VIEWS[0], AXIAL[0])
    assert img.shape == (len(VIEWS), len(AXIAL))
    assert img.data[0, 0] == value(VIEWS[0], AXIAL[0], 1)
    assert img.data[-1, 0] == value(VIEWS[-1], AXIAL[0], 1)
    assert img.data[0, -1] == value(VIEWS[0], AXIAL[-1], 1)


@pytest.mark.parametrize("mode, fixed", [(SliceMode.SINOGRAM, {"axial": 7}), (SliceMode.VIEWGRAM, {"view": 5}),
                                         (SliceMode.TANGENTIAL, {"tangential": -2})])
def test_every_pixel_maps_back_to_its_own_bin(ds, mode, fixed):
    img = _slice(ds, mode, **fixed)
    rows, cols = img.shape
    for r in range(rows):
        for c in range(cols):
            bins = {**fixed, **img.indices_at(r, c)}
            assert img.data[r, c] == value(bins["view"], bins["axial"], bins["tangential"])
