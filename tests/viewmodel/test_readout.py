# SPDX-License-Identifier: Apache-2.0
"""The cursor readout of #36 (phase 4): its lines and the corner it floats in, without Qt."""
import pytest

from fakes import non_tof_source, small_demo
from pet_projection_data_visualization.model import ProjDataset, SliceMode, TofMode
from pet_projection_data_visualization.viewmodel import Corner, ProjectionPaneViewModel, readout_corner
from pet_projection_data_visualization.viewmodel.readout import DEFAULT_CORNER, near_corner


@pytest.mark.parametrize("corner, fx, fy, near", [
    (Corner.TOP_RIGHT, 0.9, 0.1, True), (Corner.TOP_RIGHT, 0.1, 0.1, False), (Corner.TOP_RIGHT, 0.9, 0.9, False),
    (Corner.TOP_LEFT, 0.1, 0.1, True), (Corner.BOTTOM_LEFT, 0.0, 1.0, True), (Corner.BOTTOM_RIGHT, 1.0, 1.0, True),
    (Corner.BOTTOM_RIGHT, 0.5, 0.9, False), (Corner.TOP_RIGHT, 1.2, 0.1, False),   # off the image: never near
])
def test_near_corner(corner, fx, fy, near):
    assert near_corner(corner, fx, fy) is near


def test_the_readout_stays_put_until_the_cursor_comes_close():
    assert readout_corner(Corner.TOP_RIGHT, 0.5, 0.5) is Corner.TOP_RIGHT
    assert readout_corner(Corner.TOP_RIGHT, None, None) is Corner.TOP_RIGHT
    assert readout_corner(Corner.TOP_RIGHT, 0.95, 0.05) is Corner.TOP_LEFT       # same edge, other side
    assert readout_corner(Corner.TOP_LEFT, 0.95, 0.05) is Corner.TOP_LEFT        # not close to where it is now
    assert readout_corner(Corner.TOP_LEFT, 0.05, 0.05) is Corner.TOP_RIGHT
    assert readout_corner(Corner.BOTTOM_LEFT, 0.1, 0.9) is Corner.TOP_RIGHT


@pytest.mark.parametrize("fx, fy", [(x / 10, y / 10) for x in range(11) for y in range(11)])
def test_the_new_corner_is_never_near_the_cursor(fx, fy):
    for corner in Corner:
        assert not near_corner(readout_corner(corner, fx, fy), fx, fy)


def _pane(source):
    pane = ProjectionPaneViewModel()
    pane.show_dataset(ProjDataset(source))
    return pane


def test_the_readout_names_every_index_of_the_bin_and_its_value():
    pane = _pane(small_demo())
    assert pane.readout == () and pane.readout_corner is DEFAULT_CORNER
    pane.hover_at(-7.0, 3.0)                                  # sinogram: x tangential, y view
    lines = dict(pane.readout)
    sel = pane.selection
    assert list(lines) == ["Segment", "View", "Axial", "Tangential", "TOF bin", "Value"]
    assert (lines["Segment"], lines["View"], lines["Axial"], lines["Tangential"]) == (
        str(sel.segment), "3", str(sel.axial), "-7")
    assert lines["TOF bin"] == str(sel.tof)
    value = pane.dataset.slice(sel).data[3, 0]
    assert lines["Value"] == f"{value:.6g}"
    pane.set_tof_mode(TofMode.SUM)
    assert dict(pane.readout)["TOF"] == "Sum of 5 bins"
    pane.hover_leave()
    assert pane.readout == ()


def test_the_readout_follows_the_image_type():
    pane = _pane(small_demo())
    pane.set_slice_mode(SliceMode.TANGENTIAL)                 # x axial, y view
    pane.hover_at(2.0, 5.0)
    lines = dict(pane.readout)
    assert lines["Axial"] == "2" and lines["View"] == "5" and lines["Tangential"] == str(pane.selection.tangential)


def test_non_tof_data_has_no_tof_line_and_off_image_clears_it():
    pane = _pane(non_tof_source())
    pane.hover_at(0.0, 0.0)
    assert "TOF bin" not in dict(pane.readout) and "TOF" not in dict(pane.readout)
    pane.hover_at(1000.0, 1000.0)
    assert pane.readout == ()


def test_the_readout_moves_away_from_the_cursor():
    pane = _pane(small_demo())
    im = pane.image
    pane.hover_at(im.x0 + 0.95 * im.width, im.y0 + 0.05 * im.height)   # top right of the image
    assert pane.readout_corner is Corner.TOP_LEFT
    pane.hover_at(im.x0 + 0.5 * im.width, im.y0 + 0.5 * im.height)
    assert pane.readout_corner is Corner.TOP_LEFT
    pane.show_dataset(ProjDataset(small_demo()))                       # a new data set starts afresh
    assert pane.readout_corner is DEFAULT_CORNER
