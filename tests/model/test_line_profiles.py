# SPDX-License-Identifier: Apache-2.0
"""Line profiles through a slice (#36, phase 5): exact rows and columns, and interpolated free lines."""
import math

import numpy as np
import pytest

from pet_projection_data_visualization.model import SliceImage, axis_profile, line_profile, sample_bilinear
from pet_projection_data_visualization.model.profiles import line_positions


def _image(rows=4, cols=5, row_origin=-2, col_origin=3):
    data = np.arange(rows * cols, dtype=np.float32).reshape(rows, cols)
    return SliceImage(data, "t", "view", "tangential", row_origin, col_origin)


def test_a_row_profile_reads_the_exact_bins_along_the_column_axis():
    image = _image()
    x, y = axis_profile(image, "tangential", row=1, col=2)
    assert x.tolist() == [3, 4, 5, 6, 7] and y.tolist() == [5, 6, 7, 8, 9]


def test_a_column_profile_reads_the_exact_bins_along_the_row_axis():
    image = _image()
    x, y = axis_profile(image, "view", row=1, col=2)
    assert x.tolist() == [-2, -1, 0, 1] and y.tolist() == [2, 7, 12, 17]


def test_axis_profile_rejects_pixels_off_the_image_and_unknown_axes():
    image = _image()
    with pytest.raises(ValueError):
        axis_profile(image, "view", row=4, col=0)
    with pytest.raises(ValueError):
        axis_profile(image, "view", row=0, col=-1)        # no silent wrap-around
    with pytest.raises(KeyError):
        axis_profile(image, "axial", row=0, col=0)


def test_bilinear_samples_are_exact_at_pixel_centres_and_linear_between():
    image = _image()
    assert sample_bilinear(image, [3.0, 7.0], [-2.0, 1.0]).tolist() == [0.0, 19.0]
    assert sample_bilinear(image, [3.5], [-2.0])[0] == pytest.approx(0.5)
    assert sample_bilinear(image, [3.5], [-1.5])[0] == pytest.approx((0 + 1 + 5 + 6) / 4)


def test_bilinear_takes_edge_values_half_a_pixel_out_and_nan_beyond():
    image = _image()
    edge = sample_bilinear(image, [2.5, 7.5, 3.0, 3.0], [-2.0, 1.0, -2.5, 1.5])
    assert edge.tolist() == [0.0, 19.0, 0.0, 15.0]
    outside = sample_bilinear(image, [2.4, 7.6, 3.0, 3.0], [-2.0, 1.0, -2.6, 1.6])
    assert np.isnan(outside).all()


def test_line_positions_sample_about_once_per_bin():
    distance, x, y = line_positions((0.0, 0.0), (3.0, 4.0))
    assert len(distance) == 6 and distance[0] == 0 and distance[-1] == pytest.approx(5.0)
    assert (x[-1], y[-1]) == (3.0, 4.0)
    distance, _, _ = line_positions((1.0, 1.0), (1.0, 1.0))
    assert len(distance) == 2                       # a point still gives a (flat) profile


def test_a_free_line_along_a_row_matches_the_row_profile():
    image = _image()
    distance, values = line_profile(image, (3.0, 0.0), (7.0, 0.0))
    _, row = axis_profile(image, "tangential", row=2, col=0)
    assert distance.tolist() == [0, 1, 2, 3, 4] and values.tolist() == row.tolist()


def test_a_diagonal_free_line_interpolates_and_leaves_the_image_as_nan():
    image = _image()
    distance, values = line_profile(image, (3.0, -2.0), (6.0, 1.0))     # pixel centres (0,0) -> (3,3)
    assert distance[-1] == pytest.approx(3 * math.sqrt(2))
    assert values[0] == 0.0 and values[-1] == pytest.approx(18.0)
    _, values = line_profile(image, (3.0, -2.0), (20.0, -2.0))
    assert values[0] == 0.0 and np.isnan(values[-1])
