# SPDX-License-Identifier: Apache-2.0
"""Regression tests for defects found by the independent code review."""
import numpy as np

from fakes import CountingSource, small_demo
from pet_projection_data_visualization.model import ProjDataset, Selection, SliceMode
from pet_projection_data_visualization.sources import ArraySource
from pet_projection_data_visualization.viewmodel import LevelMode, ViewerViewModel


def make_vm(source=None):
    vm = ViewerViewModel(lambda o: o, demo_factory=small_demo)
    vm.load(source or small_demo())
    return vm


def test_tof_profile_is_not_stale_after_the_selection_changes():
    """The cursor does not move; the slice under it does: the profile must follow without a new hover."""
    vm = make_vm()
    vm.pane.hover_at(0, 3)
    assert f"axial {vm.pane.selection.axial}," in vm.pane.tof_profile.title
    vm.pane.set_value("axial", 1)                            # no hover_at after this
    assert "axial 1," in vm.pane.tof_profile.title and "view 3," in vm.pane.tof_profile.title
    expected = vm.pane.dataset.tof_profile(vm.pane.selection.segment, 3, 1, 0)
    np.testing.assert_allclose(vm.pane.tof_profile.y, expected)


def test_tof_profile_refreshes_after_segment_mode_and_playback_changes():
    vm = make_vm()
    vm.pane.hover_at(0, 3)
    vm.pane.set_value("segment", 1)
    assert "segment 1," in vm.pane.tof_profile.title
    vm.pane.set_slice_mode(SliceMode.VIEWGRAM)               # same cursor now means (axial 3, tangential 0)
    assert "axial 3," in vm.pane.tof_profile.title and f"view {vm.pane.selection.view}," in vm.pane.tof_profile.title
    before = vm.pane.tof_profile
    vm.pane.set_playing(True)
    vm.pane.tick()                                           # TOF bin changes, the LOR does not
    assert vm.pane.tof_profile == before and vm.pane.tof_marker == vm.pane.selection.tof
    vm.pane.hover_leave()
    vm.pane.set_value("view", 0)
    assert vm.pane.tof_profile is None                       # no cursor: no profile for a LOR nobody points at


def test_a_read_error_stops_playback():
    src = CountingSource(small_demo())
    vm = make_vm(src)
    vm.pane.set_playing(True)
    src.fail = True
    vm.pane.dataset._raw.clear()
    vm.pane.tick()
    assert vm.error and not vm.pane.playing
    errors = []
    vm.subscribe(lambda n: errors.append(n) if "error" in n else None)
    vm.pane.tick()                                            # a stale timer firing must not pile up errors
    assert errors == []


def test_nan_and_inf_do_not_poison_the_levels():
    arr = np.arange(4 * 3 * 5, dtype=np.float32).reshape(4, 3, 5)
    arr[0, 0, 0] = np.nan
    arr[1, 1, 1] = np.inf
    vm = make_vm(ArraySource({0: arr}))
    lo, hi = vm.pane.levels
    assert np.isfinite([lo, hi]).all() and hi > lo
    vm.pane.lock_global_range()
    lo, hi = vm.pane.levels
    assert np.isfinite([lo, hi]).all() and hi > lo


def test_all_nan_slice_still_gets_valid_levels():
    vm = make_vm(ArraySource({0: np.full((4, 3, 5), np.nan, dtype=np.float32)}))
    lo, hi = vm.pane.levels
    assert np.isfinite([lo, hi]).all() and hi > lo


def test_global_range_ignores_non_finite_values():
    arr = np.ones((4, 3, 5), dtype=np.float32)
    arr[0, 0, 0] = np.nan
    arr[0, 0, 1] = -np.inf
    ds = ProjDataset(ArraySource({0: arr}))
    assert ds.global_range(Selection.initial(ds.info)) == (1.0, 1.0)


def test_loading_new_data_leaves_manual_mode_consistent():
    vm = make_vm()
    vm.pane.set_manual_levels(1.0, 2.0)
    vm.load(small_demo())
    assert vm.pane.level_mode is LevelMode.ADAPTIVE and vm.pane.levels != (1.0, 2.0)


def test_load_demo_command_uses_the_injected_factory():
    vm = ViewerViewModel(lambda o: o, demo_factory=small_demo)
    assert vm.load_demo() and vm.loaded
    assert not ViewerViewModel(lambda o: o).load_demo()          # no demo factory configured -> reported, not raised


def test_levels_can_be_typed_in_via_numeric_commands():
    vm = make_vm()
    vm.pane.set_level_bounds(low=0.5)
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels[0] == 0.5
    hi = vm.pane.levels[1]
    vm.pane.set_level_bounds(high=hi + 5)
    assert vm.pane.levels == (0.5, hi + 5)
    vm.pane.set_level_bounds(low=hi + 100)                           # would invert the range: ignored
    assert vm.pane.levels == (0.5, hi + 5)
