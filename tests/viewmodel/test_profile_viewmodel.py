# SPDX-License-Identifier: Apache-2.0
"""What the profile plots read (#36, phase 5), in every image type and TOF mode, without Qt: the TOF
profile (and its context mode while TOF is collapsed), the Row | Column | Free line profile with its
per-TOF-bin overlay, and click to freeze, Esc to release."""
from dataclasses import replace

import numpy as np
import pytest

from fakes import non_tof_source, small_demo
from pet_projection_data_visualization.model import ProjDataset, SliceMode, TofMode
from pet_projection_data_visualization.viewmodel import LineMode, ProjectionPaneViewModel
from pet_projection_data_visualization.viewmodel.profiles import default_free_line, line_axis_names

MODES = list(SliceMode)
TOF_MODES = list(TofMode)


def _pane(source=None):
    status = []
    pane = ProjectionPaneViewModel(on_status=status.append)
    pane.show_dataset(ProjDataset(source or small_demo()))
    return pane, status


def _centre(pane):
    """Axis coordinates of a pixel inside the image, and its (row, col)."""
    im = pane.image
    rows, cols = pane.dataset.slice(pane.selection).shape
    row, col = rows // 3, cols // 2
    return (im.x0 + 0.5 + col, im.y0 + 0.5 + row), (row, col)


def _lor(pane, row, col):
    image = pane.dataset.slice(pane.selection)
    lor = {d: pane.selection.get(d) for d in ("segment", "view", "axial", "tangential")}
    lor.update(image.indices_at(row, col))
    return lor


# ---- line profile: Row and Column ------------------------------------------------------------------
@pytest.mark.parametrize("slice_mode", MODES)
@pytest.mark.parametrize("tof_mode", TOF_MODES)
def test_row_and_column_read_the_displayed_image_through_the_cursor(slice_mode, tof_mode):
    pane, _ = _pane()
    pane.set_slice_mode(slice_mode)
    pane.set_tof_mode(tof_mode)
    (x, y), (row, col) = _centre(pane)
    pane.hover_at(x, y)
    image = pane.dataset.slice(pane.selection)            # the image as displayed (bin or Sum/Mean/Max)
    prof = pane.line_profile
    assert pane.line_mode is LineMode.ROW
    assert prof.x_label == image.col_axis and np.allclose(prof.y, image.data[row, :])
    assert prof.x == tuple(float(image.col_origin + i) for i in range(image.shape[1]))
    pane.set_line_mode(LineMode.COLUMN)
    prof = pane.line_profile
    assert prof.x_label == image.row_axis and np.allclose(prof.y, image.data[:, col])
    assert prof.overlay == ()


@pytest.mark.parametrize("slice_mode, row_name, column_name", [
    (SliceMode.SINOGRAM, "along tangential", "along view"),
    (SliceMode.VIEWGRAM, "along tangential", "along axial"),
    (SliceMode.TANGENTIAL, "along axial", "along view"),
])
def test_row_and_column_are_named_for_the_image_type(slice_mode, row_name, column_name):
    pane, _ = _pane()
    pane.set_slice_mode(slice_mode)
    assert pane.line_axis_names == (row_name, column_name)
    assert line_axis_names(pane.dataset.slice(pane.selection)) == (row_name, column_name)


def test_the_default_line_profile_runs_along_tangential():
    pane, _ = _pane()
    (x, y), _ = _centre(pane)
    pane.hover_at(x, y)
    assert pane.line_mode is LineMode.ROW and pane.line_profile.x_label == "tangential"
    assert "along tangential at view" in pane.line_profile.title


@pytest.mark.parametrize("slice_mode", MODES)
def test_the_profile_says_where_its_line_lies_on_the_image(slice_mode):
    pane, _ = _pane()
    pane.set_slice_mode(slice_mode)
    (x, y), (row, col) = _centre(pane)
    pane.hover_at(x, y)
    image = pane.dataset.slice(pane.selection)
    rows, cols = image.shape
    left, top = image.col_origin - 0.5, image.row_origin - 0.5         # the image's edges, in axis coordinates
    centre_x, centre_y = float(image.col_origin + col), float(image.row_origin + row)
    assert pane.line_profile.path == (left, centre_y, left + cols, centre_y)       # Row: across, through the pixel
    pane.set_line_mode(LineMode.COLUMN)
    assert pane.line_profile.path == (centre_x, top, centre_x, top + rows)         # Column: down, through the pixel
    pane.hover_at(x + 2, y + 1)                                                    # it follows the cursor
    assert pane.line_profile.path == (centre_x + 2, top, centre_x + 2, top + rows)
    pane.click_at(x + 2, y + 1)
    pane.hover_at(x, y)                                                            # frozen: it stays
    assert pane.line_profile.path == (centre_x + 2, top, centre_x + 2, top + rows)
    pane.set_line_mode(LineMode.FREE)
    assert pane.line_profile.path == pane.free_line


def test_no_cursor_no_row_profile_and_off_image_keeps_the_last_one():
    pane, _ = _pane()
    assert pane.line_profile is None and pane.tof_profile is None
    (x, y), _ = _centre(pane)
    pane.hover_at(x, y)
    shown = pane.line_profile
    pane.hover_at(1e6, 1e6)                               # off the image (e.g. over the axes)
    assert pane.line_profile is shown


# ---- line profile: Free -------------------------------------------------------------------------------
@pytest.mark.parametrize("slice_mode", MODES)
def test_free_starts_with_a_line_across_the_image_and_reads_along_it(slice_mode):
    pane, _ = _pane()
    pane.set_slice_mode(slice_mode)
    pane.set_line_mode(LineMode.FREE)
    image = pane.dataset.slice(pane.selection)
    assert pane.free_line == default_free_line(image)
    prof = pane.line_profile                               # no cursor needed
    assert prof.x_label == "distance (bins)" and prof.x[0] == 0.0 and len(prof.x) == len(prof.y) >= 2
    x0, y0, x1, y1 = pane.free_line
    assert prof.x[-1] == pytest.approx(np.hypot(x1 - x0, y1 - y0))


def test_a_free_line_along_a_row_gives_the_row_values():
    pane, _ = _pane()
    pane.set_line_mode(LineMode.FREE)
    image = pane.dataset.slice(pane.selection)
    row = 4
    y = image.row_origin + row
    pane.set_free_line(image.col_origin, y, image.col_origin + image.shape[1] - 1, y)
    prof = pane.line_profile
    assert np.allclose(prof.y, image.data[row, :]) and np.allclose(prof.x, range(image.shape[1]))


def test_the_free_line_is_ignored_outside_free_mode_and_reset_for_another_image_type():
    pane, _ = _pane()
    pane.set_free_line(0, 0, 3, 3)
    assert pane.free_line is None                          # Row mode: no free line
    pane.set_line_mode(LineMode.FREE)
    pane.set_free_line(-5.0, 1.0, 5.0, 9.0)
    pane.set_value("axial", pane.selection.axial + 1)      # same image axes: the line stays
    assert pane.free_line == (-5.0, 1.0, 5.0, 9.0)
    pane.set_slice_mode(SliceMode.VIEWGRAM)                # other axes: a line across the new image
    assert pane.free_line == default_free_line(pane.dataset.slice(pane.selection))
    pane.set_free_line(float("nan"), 0, 1, 1)              # rejected
    assert pane.free_line == default_free_line(pane.dataset.slice(pane.selection))
    pane.set_line_mode(LineMode.ROW)
    assert pane.free_line is None


# ---- per-TOF-bin overlay --------------------------------------------------------------------------------
@pytest.mark.parametrize("slice_mode", MODES)
@pytest.mark.parametrize("line_mode", list(LineMode))
def test_the_overlay_has_one_curve_per_tof_bin_along_the_same_line(slice_mode, line_mode):
    pane, _ = _pane()
    pane.set_slice_mode(slice_mode)
    pane.set_tof_mode(TofMode.SUM)
    pane.set_line_mode(line_mode)
    (x, y), _ = _centre(pane)
    pane.hover_at(x, y)
    pane.set_show_tof_overlay(True)
    prof = pane.line_profile
    info = pane.dataset.info
    assert prof.overlay_bins == tuple(info.tof_bins) and len(prof.overlay) == info.num_tof_bins
    assert all(len(curve) == len(prof.x) for curve in prof.overlay)
    assert np.allclose(np.nansum(prof.overlay, axis=0), np.nan_to_num(prof.y), rtol=1e-4)   # the bins sum to Sum
    sel = pane.selection
    one_bin = pane.dataset.slice(replace(sel, tof_mode=TofMode.BIN, tof=info.min_tof + 1))
    if line_mode is not LineMode.FREE:
        _, (row, col) = _centre(pane)
        expected = one_bin.data[row, :] if line_mode is LineMode.ROW else one_bin.data[:, col]
        assert np.allclose(prof.overlay[1], expected)


def test_no_overlay_for_non_tof_data():
    pane, _ = _pane(non_tof_source())
    (x, y), _ = _centre(pane)
    pane.hover_at(x, y)
    pane.set_show_tof_overlay(True)
    assert pane.line_profile is not None and pane.line_profile.overlay == () and pane.tof_profile is None


# ---- TOF profile and its context mode ---------------------------------------------------------------------
@pytest.mark.parametrize("slice_mode", MODES)
def test_a_single_bin_marks_the_bin_and_has_no_context(slice_mode):
    pane, _ = _pane()
    pane.set_slice_mode(slice_mode)
    (x, y), (row, col) = _centre(pane)
    pane.hover_at(x, y)
    lor = _lor(pane, row, col)
    prof = pane.tof_profile
    expected = pane.dataset.tof_profile(lor["segment"], lor["view"], lor["axial"], lor["tangential"])
    assert np.allclose(prof.y, expected) and prof.context == "" and prof.reference is None
    assert pane.tof_marker == pane.selection.tof


@pytest.mark.parametrize("slice_mode", MODES)
@pytest.mark.parametrize("tof_mode, reduce", [(TofMode.SUM, np.sum), (TofMode.MEAN, np.mean), (TofMode.MAX, np.max)])
def test_collapsed_tof_shows_the_bins_as_context_with_the_collapsed_value(slice_mode, tof_mode, reduce):
    pane, _ = _pane()
    pane.set_slice_mode(slice_mode)
    pane.set_tof_mode(tof_mode)
    (x, y), (row, col) = _centre(pane)
    pane.hover_at(x, y)
    prof = pane.tof_profile
    assert pane.tof_marker is None
    assert prof.reference == pytest.approx(float(reduce(prof.y)))
    shown = pane.dataset.slice(pane.selection).data[row, col]
    assert prof.reference == pytest.approx(float(shown), rel=1e-5)      # the value the image shows
    how = tof_mode.name.capitalize()
    assert prof.context.startswith("TOF bins at this LOR") and f"the image shows their {how}" in prof.context


# ---- click to freeze, Esc to release -------------------------------------------------------------------------
def test_a_click_freezes_both_profiles_while_the_cursor_moves():
    pane, status = _pane()
    (x, y), (row, col) = _centre(pane)
    pane.hover_at(x, y)
    pane.click_at(x, y)
    assert pane.frozen_at == (x, y) and "frozen" in status[-1]
    tof, line = pane.tof_profile, pane.line_profile
    pane.hover_at(x + 3, y + 2)
    assert pane.tof_profile == tof and pane.line_profile == line
    assert pane.readout and dict(pane.readout)["Tangential"] == str(int(x + 3))    # the readout still follows


def test_frozen_profiles_keep_their_lor_while_the_slice_changes():
    pane, _ = _pane()
    (x, y), (row, col) = _centre(pane)
    pane.click_at(x, y)
    lor = _lor(pane, row, col)
    tof = pane.tof_profile
    pane.set_value("axial", pane.selection.axial + 1)                    # another sinogram
    assert pane.tof_profile.y == tof.y and pane.frozen_at == (x, y)      # the same LOR
    image = pane.dataset.slice(pane.selection)
    assert np.allclose(pane.line_profile.y, image.data[row, :])          # the same row, in the new slice
    pane.set_slice_mode(SliceMode.VIEWGRAM)                              # x tangential, y axial
    assert pane.frozen_at == (float(lor["tangential"]), float(lor["axial"]))
    assert pane.tof_profile.y == tof.y


def test_esc_or_another_click_releases_the_profiles():
    pane, status = _pane()
    (x, y), _ = _centre(pane)
    pane.click_at(x, y)
    pane.release_freeze()
    assert pane.frozen_at is None and "follow the cursor" in status[-1]
    pane.hover_at(x + 1, y)
    assert pane.line_profile.title != "" and pane.tof_profile is not None
    pane.click_at(x, y)
    pane.click_at(x + 5, y + 5)                                          # another click releases
    assert pane.frozen_at is None
    pane.release_freeze()                                                # nothing frozen: nothing happens


def test_a_click_off_the_image_freezes_nothing():
    pane, _ = _pane()
    pane.click_at(1e6, 1e6)
    assert pane.frozen_at is None


def test_toggle_freeze_is_the_keyboard_click():
    pane, _ = _pane()
    pane.toggle_freeze()                                                 # no cursor: the centre of the image
    im = pane.image
    assert pane.frozen_at is not None
    fx, fy = pane.frozen_at
    assert im.x0 < fx < im.x0 + im.width and im.y0 < fy < im.y0 + im.height
    assert pane.line_profile is not None
    pane.toggle_freeze()
    assert pane.frozen_at is None


def test_a_new_data_set_releases_the_freeze_and_the_free_line():
    pane, _ = _pane()
    (x, y), _ = _centre(pane)
    pane.click_at(x, y)
    pane.set_line_mode(LineMode.FREE)
    pane.set_free_line(-3.0, 0.0, 3.0, 4.0)
    pane.show_dataset(ProjDataset(small_demo()))
    assert pane.frozen_at is None and pane.line_mode is LineMode.FREE
    assert pane.free_line == default_free_line(pane.dataset.slice(pane.selection))
