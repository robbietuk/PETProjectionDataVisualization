# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest

from fakes import CountingSource, non_tof_source, shifted_tof_source, small_demo
from pet_projection_data_visualization.model import SliceMode, TofMode
from pet_projection_data_visualization.viewmodel import COLORMAPS, LevelMode, ViewerViewModel
from pet_projection_data_visualization.viewmodel.pane_viewmodel import MAX_FPS, MIN_FPS


def make_vm(source=None, load=True):
    vm = ViewerViewModel(source_factory=lambda obj: obj)
    notes = []
    vm.subscribe(notes.append)          # the window's notifications ...
    vm.pane.subscribe(notes.append)     # ... and its pane's, in one list
    if load:
        assert vm.load(source or small_demo())
        notes.clear()
    return vm, notes


# ---- before anything is loaded -------------------------------------------------------------
def test_initial_state_is_empty_and_commands_are_harmless():
    vm, notes = make_vm(load=False)
    assert not vm.loaded and vm.pane.image is None and vm.pane.dimensions == () and vm.pane.selection is None
    vm.pane.set_value("axial", 3)
    vm.pane.step_active(1)
    vm.pane.set_slice_mode(SliceMode.VIEWGRAM)
    vm.pane.set_tof_mode(TofMode.SUM)
    vm.pane.tick()
    vm.pane.hover_at(0, 0)
    vm.pane.set_playing(True)
    assert notes == [] and not vm.pane.playing


# ---- loading ---------------------------------------------------------------------------------
def test_load_publishes_a_complete_state_in_one_notification():
    vm = ViewerViewModel(source_factory=lambda obj: obj)
    window_notes, pane_notes = [], []
    vm.subscribe(window_notes.append)
    vm.pane.subscribe(pane_notes.append)
    assert vm.load(small_demo())
    assert len(window_notes) == 1 and len(pane_notes) == 1          # one notification from each
    assert {"loaded", "window_title", "source_label"} <= window_notes[0]
    assert {"image", "levels", "dimensions", "info_text", "title"} <= pane_notes[0]
    assert vm.loaded and "demo" in vm.window_title and vm.error is None
    assert [d.name for d in vm.pane.dimensions] == ["segment", "axial", "view", "tangential", "tof"]
    assert vm.pane.tof_available and vm.pane.can_play and vm.pane.tof_marker == 2
    assert "Source:" in vm.pane.info_text and "Current slice" in vm.pane.info_text


def test_image_rect_is_pixel_centred_in_bin_numbers():
    vm, _ = make_vm()
    im = vm.pane.image
    assert (im.x0, im.y0, im.width, im.height) == (-7 - 0.5, 0 - 0.5, 15.0, 12.0)
    assert (im.row_label, im.col_label) == ("view", "tangential") and im.data.dtype == np.float32


def test_load_failure_reports_and_keeps_previous_data():
    def factory(obj):
        if obj == "bad":
            raise OSError("no such file")
        return obj
    vm = ViewerViewModel(factory)
    notes = []
    vm.load(small_demo())
    vm.subscribe(notes.append)
    before = vm.pane.image
    assert vm.load("bad") is False
    assert "no such file" in vm.error and vm.error in vm.status
    assert vm.loaded and vm.pane.image is before
    assert any("error" in n for n in notes)
    notes.clear()
    assert vm.load("bad") is False
    assert any("error" in n for n in notes)            # the same message is announced again


def test_load_resets_selection_playback_and_profile():
    vm, _ = make_vm()
    vm.pane.set_value("segment", 1)
    vm.pane.set_playing(True)
    vm.pane.hover_at(0, 0)
    assert vm.pane.tof_profile is not None
    vm.load(small_demo(num_views=20))
    assert vm.pane.selection.segment == 0 and not vm.pane.playing and vm.pane.tof_profile is None and vm.pane.pixel_text == ""


def test_loading_non_tof_data_disables_tof_controls():
    vm, _ = make_vm(non_tof_source())
    assert not vm.pane.tof_available and not vm.pane.can_play and vm.pane.tof_marker is None
    assert not vm.pane.dimension("tof").enabled
    vm.pane.set_playing(True)
    vm.pane.tick()
    assert not vm.pane.playing


# ---- dimensions ------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode,enabled", [
    (SliceMode.SINOGRAM, {"segment", "axial", "tof"}),
    (SliceMode.VIEWGRAM, {"segment", "view", "tof"}),
    (SliceMode.TANGENTIAL, {"segment", "tangential", "tof"}),
])
def test_only_relevant_dimensions_are_enabled(mode, enabled):
    vm, _ = make_vm()
    vm.pane.set_slice_mode(mode)
    assert {d.name for d in vm.pane.dimensions if d.enabled} == enabled
    assert vm.pane.slice_mode is mode


def test_set_value_updates_slice_and_clamps():
    vm, _ = make_vm()
    vm.pane.set_value("axial", 3)
    assert vm.pane.selection.axial == 3 and "axial 3" in vm.pane.image.title
    vm.pane.set_value("axial", 999)
    assert vm.pane.dimension("axial").value == vm.pane.dimension("axial").hi == 7


def test_changing_segment_changes_the_axial_range_shown():
    vm, _ = make_vm()
    assert vm.pane.dimension("axial").hi == 7
    vm.pane.set_value("segment", 1)
    assert vm.pane.dimension("axial").hi == 3


def test_step_and_step_active():
    vm, _ = make_vm()
    a = vm.pane.selection.axial
    vm.pane.step_active(1)
    assert vm.pane.selection.axial == a + 1
    vm.pane.set_slice_mode(SliceMode.VIEWGRAM)
    v = vm.pane.selection.view
    vm.pane.step_active(-1)
    assert vm.pane.selection.view == v - 1 and vm.pane.selection.axial == a + 1
    vm.pane.step("segment", +99)
    assert vm.pane.selection.segment == 1


def test_dimensions_with_a_single_value_are_disabled():
    vm, _ = make_vm(non_tof_source())
    assert not vm.pane.dimension("tof").enabled          # lo == hi
    assert vm.pane.dimension("segment").enabled
    one_segment, _ = make_vm(small_demo(num_segments=1))
    assert one_segment.pane.dimension("segment").lo == one_segment.pane.dimension("segment").hi
    assert not one_segment.pane.dimension("segment").enabled     # always "wanted", but nothing to scroll


# ---- slice and TOF modes ------------------------------------------------------------------------------
def test_slice_modes_change_shape_and_labels():
    vm, _ = make_vm()
    vm.pane.set_slice_mode(SliceMode.VIEWGRAM)
    assert vm.pane.image.data.shape == (8, 15) and vm.pane.image.row_label == "axial"
    vm.pane.set_slice_mode(SliceMode.TANGENTIAL)
    assert vm.pane.image.data.shape == (12, 8) and vm.pane.image.col_label == "axial"


def test_tof_collapse_disables_play_and_marker():
    vm, _ = make_vm()
    vm.pane.set_playing(True)
    assert vm.pane.playing
    vm.pane.set_tof_mode(TofMode.SUM)
    assert not vm.pane.playing and not vm.pane.can_play and vm.pane.tof_marker is None
    assert not vm.pane.dimension("tof").enabled and "sum over" in vm.pane.image.title.lower()
    vm.pane.set_tof_mode(TofMode.BIN)
    assert vm.pane.can_play and vm.pane.tof_marker == vm.pane.selection.tof and vm.pane.dimension("tof").enabled


def test_collapsed_image_equals_sum_of_bins():
    src = small_demo()
    vm, _ = make_vm(src)
    vm.pane.set_tof_mode(TofMode.SUM)
    expect = sum(src.get_segment(0, k) for k in src.info.tof_bins)[:, vm.pane.selection.axial, :]
    np.testing.assert_allclose(vm.pane.image.data, expect, rtol=1e-5)


# ---- playback -----------------------------------------------------------------------------------------
def test_play_toggle_and_tick_advance_with_wraparound():
    vm, notes = make_vm()
    vm.pane.toggle_play()
    assert vm.pane.playing
    seen = []
    for _ in range(vm.pane.dataset.info.num_tof_bins):
        vm.pane.tick()
        seen.append(vm.pane.selection.tof)
    assert seen == [3, 4, 0, 1, 2]                 # started at the centre bin 2
    vm.pane.toggle_play()
    assert not vm.pane.playing


def test_tick_changes_the_image_and_marker():
    vm, _ = make_vm()
    before = vm.pane.image
    vm.pane.set_playing(True)
    vm.pane.tick()
    assert vm.pane.image is not before and not np.array_equal(vm.pane.image.data, before.data)
    assert vm.pane.tof_marker == vm.pane.selection.tof


def test_tick_when_play_became_impossible_stops_playback():
    vm, _ = make_vm()
    vm.pane.set_playing(True)
    vm.pane._selection = vm.pane._selection.with_tof_mode(TofMode.MAX)   # simulate a stale timer firing
    vm.pane.tick()
    assert not vm.pane.playing


def test_fps_is_clamped_and_unchanged_value_is_silent():
    vm, notes = make_vm()
    vm.pane.set_fps(1000)
    assert vm.pane.fps == MAX_FPS
    vm.pane.set_fps(-5)
    assert vm.pane.fps == MIN_FPS
    notes.clear()
    vm.pane.set_fps(MIN_FPS)
    assert notes == []


# ---- display options -----------------------------------------------------------------------------------
def test_colormap_validation():
    vm, _ = make_vm()
    for name in COLORMAPS:
        vm.pane.set_colormap(name)
        assert vm.pane.colormap == name
    with pytest.raises(ValueError, match="unknown colour map"):
        vm.pane.set_colormap("jet")
    assert vm.pane.colormap == COLORMAPS[-1]


def test_auto_levels_follow_the_slice():
    vm, _ = make_vm()
    assert vm.pane.levels == (float(vm.pane.image.data.min()), float(vm.pane.image.data.max()))
    vm.pane.set_value("axial", 5)
    assert vm.pane.levels == (float(vm.pane.image.data.min()), float(vm.pane.image.data.max()))


def test_fixed_levels_are_the_global_range_and_do_not_move_between_slices():
    vm, _ = make_vm()
    vm.pane.lock_global_range()
    lo, hi = vm.pane.dataset.global_range(vm.pane.selection)
    assert vm.pane.levels == (lo, hi)
    vm.pane.set_value("axial", 0)
    vm.pane.set_value("segment", 1)
    assert vm.pane.levels == (lo, hi)


def test_log_display_transforms_values_and_levels():
    src = small_demo()
    vm, _ = make_vm(src)
    raw = vm.pane.dataset.slice(vm.pane.selection).data
    vm.pane.set_log_display(True)
    np.testing.assert_allclose(vm.pane.image.data, np.log1p(raw), rtol=1e-6)
    vm.pane.lock_global_range()
    lo, hi = vm.pane.dataset.global_range(vm.pane.selection)
    assert vm.pane.levels == pytest.approx((np.log1p(lo), np.log1p(hi)))


def test_log_display_handles_negative_values():
    arr = np.full((4, 2, 5), -3.0, dtype=np.float32)
    arr[1, 1, 1] = 7.0
    from pet_projection_data_visualization.sources import ArraySource
    vm, _ = make_vm(ArraySource({0: arr}))
    vm.pane.set_log_display(True)
    assert np.isfinite(vm.pane.image.data).all() and vm.pane.image.data.min() == 0.0


def test_manual_levels_stick_across_slices_and_switch_the_mode():
    vm, _ = make_vm()
    vm.pane.set_manual_levels(1.0, 2.0)
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == (1.0, 2.0)
    vm.pane.set_value("axial", 1)
    vm.pane.tick()
    assert vm.pane.levels == (1.0, 2.0)
    vm.pane.set_level_mode(LevelMode.ADAPTIVE)
    assert vm.pane.levels != (1.0, 2.0)


def test_manual_levels_reject_empty_range():
    vm, _ = make_vm()
    before = vm.pane.levels
    vm.pane.set_manual_levels(3.0, 3.0)
    vm.pane.set_manual_levels(5.0, 1.0)
    assert vm.pane.levels == before and vm.pane.level_mode is LevelMode.ADAPTIVE


def test_toggling_log_keeps_locked_levels_mapped_to_the_same_data_values():
    """Changed on purpose: manual levels used to be dropped on a log toggle. Locked levels now stay locked
    and are shown through the same log(1 + x) transform as the pixels."""
    vm, _ = make_vm()
    vm.pane.set_manual_levels(1.0, 2.0)
    vm.pane.set_log_display(True)
    assert vm.pane.level_mode is LevelMode.LOCKED
    assert vm.pane.levels == pytest.approx((np.log1p(1.0), np.log1p(2.0)))
    vm.pane.set_log_display(False)
    assert vm.pane.levels == (1.0, 2.0)                    # exactly: no drift from converting back and forth


def test_unlocking_after_a_scale_change_recomputes_from_the_slice():
    vm, _ = make_vm()
    vm.pane.set_manual_levels(1.0, 2.0)
    vm.pane.set_log_display(True)
    vm.pane.set_level_mode(LevelMode.ADAPTIVE)
    assert vm.pane.levels == (float(vm.pane.image.data.min()), float(vm.pane.image.data.max()))


def test_constant_slice_still_gets_a_valid_level_range():
    from pet_projection_data_visualization.sources import ArraySource
    vm, _ = make_vm(ArraySource({0: np.full((4, 2, 5), 3.0)}))
    lo, hi = vm.pane.levels
    assert hi > lo


# ---- hover --------------------------------------------------------------------------------------------------
def test_hover_reports_value_and_real_indices():
    vm, _ = make_vm()
    vm.pane.hover_at(-7, 0)                                  # first column, first row
    assert vm.pane.pixel_text.startswith("view 0, tangential -7:")
    value = float(vm.pane.dataset.slice(vm.pane.selection).data[0, 0])
    assert f"{value:.6g}" in vm.pane.pixel_text


def test_hover_rounds_to_the_pixel_under_the_cursor():
    vm, _ = make_vm()
    vm.pane.hover_at(-7 + 0.4, 0.4)
    assert vm.pane.pixel_text.startswith("view 0, tangential -7:")
    vm.pane.hover_at(-7 + 0.6, 0.6)
    assert vm.pane.pixel_text.startswith("view 1, tangential -6:")


def test_hover_outside_clears_and_leave_clears():
    vm, _ = make_vm()
    vm.pane.hover_at(0, 0)
    assert vm.pane.pixel_text
    vm.pane.hover_at(1000, 0)
    assert vm.pane.pixel_text == ""
    vm.pane.hover_at(0, 0)
    vm.pane.hover_leave()
    assert vm.pane.pixel_text == ""


def test_hover_builds_tof_profile_once_per_pixel():
    vm, _ = make_vm()
    calls = []
    real = vm.pane.dataset.tof_profile
    vm.pane.dataset.tof_profile = lambda *a: (calls.append(a), real(*a))[1]
    vm.pane.hover_at(0, 3)
    p1 = vm.pane.tof_profile
    assert p1.x == (0, 1, 2, 3, 4) and len(p1.y) == 5 and "view 3" in p1.title
    vm.pane.hover_at(0.2, 3.1)                               # same pixel
    assert len(calls) == 1 and vm.pane.tof_profile is p1
    vm.pane.hover_at(1, 3)
    assert len(calls) == 2
    assert calls[0] == (0, 3, vm.pane.selection.axial, 0)    # segment, view, axial, tangential


def test_hover_profile_uses_the_correct_lor_in_each_slice_mode():
    vm, _ = make_vm()
    vm.pane.set_slice_mode(SliceMode.VIEWGRAM)               # rows: axial, cols: tangential; fixed: view
    vm.pane.set_value("view", 4)
    vm.pane.hover_at(2, 5)
    assert "view 4, axial 5, tangential 2" in vm.pane.tof_profile.title
    vm.pane.set_slice_mode(SliceMode.TANGENTIAL)             # rows: view, cols: axial; fixed: tangential
    vm.pane.set_value("tangential", -2)
    vm.pane.hover_at(6, 3)
    assert "view 3, axial 6, tangential -2" in vm.pane.tof_profile.title


def test_hover_on_non_tof_data_has_no_profile():
    vm, _ = make_vm(non_tof_source())
    vm.pane.hover_at(0, 0)
    assert vm.pane.pixel_text and vm.pane.tof_profile is None


def test_profile_sum_equals_collapsed_pixel():
    vm, _ = make_vm()
    vm.pane.hover_at(0, 3)
    total = sum(vm.pane.tof_profile.y)
    vm.pane.set_tof_mode(TofMode.SUM)
    vm.pane.hover_at(0, 3)
    assert float(vm.pane.pixel_text.split(":")[1]) == pytest.approx(total, rel=1e-4)


# ---- failure handling ------------------------------------------------------------------------------------------
def test_read_failure_keeps_the_last_good_image_and_reports():
    src = CountingSource(small_demo())
    vm, notes = make_vm(src)
    good = vm.pane.image
    src.fail = True
    vm.pane.set_value("segment", 1)
    assert vm.pane.image is good and "disk went away" in vm.error and any("error" in n for n in notes)
    src.fail = False
    vm.pane.set_value("segment", 1)
    assert vm.pane.image is not good and vm.pane.selection.segment == 1


def test_profile_failure_is_reported_not_raised():
    src = CountingSource(small_demo())
    vm, _ = make_vm(src)
    vm.pane.dataset._raw.clear()
    src.fail = True
    vm.pane.hover_at(0, 0)
    assert "TOF profile unavailable" in vm.error


# ---- notification contract -------------------------------------------------------------------------------------
def test_every_command_notifies_at_most_once():
    vm, _ = make_vm()
    notes = []
    vm.pane.subscribe(notes.append)            # the pane's own notifications (status messages go to the window)
    commands = [lambda: vm.pane.set_value("view", 5), lambda: vm.pane.set_slice_mode(SliceMode.VIEWGRAM),
                lambda: vm.pane.set_tof_mode(TofMode.MEAN), lambda: vm.pane.set_tof_mode(TofMode.BIN),
                lambda: vm.pane.tick(), lambda: vm.pane.set_log_display(True), lambda: vm.pane.hover_at(0, 0),
                lambda: vm.pane.set_manual_levels(0, 1), lambda: vm.pane.lock_global_range()]
    for cmd in commands:
        notes.clear()
        cmd()
        assert len(notes) <= 1


def test_view_model_state_is_published_before_notification():
    """A subscriber that reads state in its callback must see the finished command, not a half-way state."""
    vm, _ = make_vm()
    vm.pane.set_playing(True)
    snapshots = []
    vm.pane.subscribe(lambda names: snapshots.append((vm.pane.selection.tof, vm.pane.tof_marker, vm.pane.image.title)))
    vm.pane.tick()
    tof, marker, title = snapshots[-1]
    assert marker == tof and f"TOF bin {tof}" in title


def test_levels_of_a_constant_zero_slice_are_python_floats():
    """``levels`` is ``(float, float)``. For an all-zero slice the minimum level width (float32 ``tiny``)
    used to turn the maximum into a numpy float32."""
    from pet_projection_data_visualization.sources.array_source import ArraySource
    vm, _ = make_vm(ArraySource({0: np.zeros((4, 3, 5), dtype=np.float32)}))
    lo, hi = vm.pane.levels
    assert lo == 0.0 < hi and type(lo) is float and type(hi) is float


# ---- TOF bin range for the profile plot -----------------------------------------------------
def test_tof_range_follows_the_loaded_dataset():
    vm, notes = make_vm(load=False)
    assert vm.pane.tof_range is None
    assert vm.load(small_demo(tof_bins=5))
    assert vm.pane.tof_range == (0, 4)


def test_tof_range_with_negative_bins_and_hover():
    vm, notes = make_vm(shifted_tof_source(-3, tof_bins=7))
    assert vm.pane.tof_range == (-3, 3)
    vm.pane.hover_at(0, 3)
    assert vm.pane.tof_range == (-3, 3)
    assert vm.pane.tof_profile is not None and vm.pane.tof_profile.x == tuple(range(-3, 4))
    assert any("tof_profile" in n for n in notes)
    assert not any("tof_range" in n for n in notes)     # hovering never changes the range


def test_tof_range_is_none_for_non_tof_data():
    vm, _ = make_vm()
    assert vm.load(non_tof_source())
    assert vm.pane.tof_range is None
