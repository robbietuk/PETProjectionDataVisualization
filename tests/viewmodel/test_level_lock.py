# SPDX-License-Identifier: Apache-2.0
"""Lockable colour levels: Adaptive (follow each slice) versus Locked (constant across all navigation)."""
import numpy as np
import pytest

from fakes import CountingSource, non_tof_source, small_demo
from pet_projection_data_visualization.model import SliceMode, TofMode
from pet_projection_data_visualization.viewmodel import LEVEL_MODE_OPTIONS, LevelMode, ViewerViewModel
from pet_projection_data_visualization.viewmodel.formatting import format_level_lock


def make_vm(source=None):
    vm = ViewerViewModel(source_factory=lambda obj: obj)
    assert vm.load(source if source is not None else small_demo())
    return vm


def drop_caches(vm):
    """Forget every cached read so the next slice has to come from the (failing) source."""
    for cache in (vm.pane.dataset._raw, vm.pane.dataset._reduced, vm.pane.dataset._sinograms):
        cache.clear()


def slice_range(vm):
    return float(vm.pane.image.data.min()), float(vm.pane.image.data.max())


def every_navigation(vm):
    """Each step a user can take while looking at the data, as (description, command)."""
    return [
        ("axial", lambda: vm.pane.set_value("axial", 0)),
        ("axial step", lambda: vm.pane.step("axial", 2)),
        ("segment", lambda: vm.pane.set_value("segment", 1)),
        ("segment back", lambda: vm.pane.step("segment", -2)),
        ("TOF bin", lambda: vm.pane.set_value("tof", 0)),
        ("TOF step", lambda: vm.pane.step("tof", 3)),
        ("viewgram", lambda: vm.pane.set_slice_mode(SliceMode.VIEWGRAM)),
        ("view", lambda: vm.pane.set_value("view", 0)),
        ("view step", lambda: vm.pane.step_active(5)),
        ("tangential mode", lambda: vm.pane.set_slice_mode(SliceMode.TANGENTIAL)),
        ("tangential", lambda: vm.pane.set_value("tangential", -6)),
        ("TOF sum", lambda: vm.pane.set_tof_mode(TofMode.SUM)),
        ("TOF mean", lambda: vm.pane.set_tof_mode(TofMode.MEAN)),
        ("TOF max", lambda: vm.pane.set_tof_mode(TofMode.MAX)),
        ("TOF bin mode", lambda: vm.pane.set_tof_mode(TofMode.BIN)),
        ("sinogram", lambda: vm.pane.set_slice_mode(SliceMode.SINOGRAM)),
        ("play", lambda: (vm.pane.set_playing(True), vm.pane.tick(), vm.pane.tick(), vm.pane.tick(), vm.pane.set_playing(False))),
        ("colour map", lambda: vm.pane.set_colormap("magma")),
        ("hover", lambda: vm.pane.hover_at(0.0, 3.0)),
    ]


# ---- the two choices -------------------------------------------------------------------------------
def test_two_level_modes_with_labels_from_one_choice_list():
    assert list(LevelMode) == [LevelMode.ADAPTIVE, LevelMode.LOCKED]
    assert LEVEL_MODE_OPTIONS.labels == ("Adaptive", "Locked")


def test_starts_adaptive_and_levels_follow_each_slice():
    vm = make_vm()
    assert vm.pane.level_mode is LevelMode.ADAPTIVE
    seen = set()
    for _, cmd in every_navigation(vm):
        cmd()
        assert vm.pane.levels == slice_range(vm)
        seen.add(vm.pane.levels)
    assert len(seen) > 3                     # the problem the lock solves: the window keeps moving


# ---- locking ---------------------------------------------------------------------------------------
def test_locking_freezes_the_levels_currently_shown():
    vm = make_vm()
    vm.pane.set_value("axial", 2)
    shown = vm.pane.levels
    vm.pane.set_level_mode(LevelMode.LOCKED)
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == shown


@pytest.mark.parametrize("log", [False, True], ids=["linear", "log"])
def test_locked_levels_are_constant_across_every_navigation(log):
    vm = make_vm()
    vm.pane.set_log_display(log)
    vm.pane.set_level_mode(LevelMode.LOCKED)
    locked = vm.pane.levels
    for name, cmd in every_navigation(vm):
        cmd()
        assert vm.pane.levels == locked, name
        assert vm.pane.level_mode is LevelMode.LOCKED, name
    assert vm.error is None


def test_locked_levels_do_not_change_during_playback():
    vm = make_vm()
    vm.pane.set_level_mode(LevelMode.LOCKED)
    locked = vm.pane.levels
    vm.pane.set_playing(True)
    bins = set()
    for _ in range(2 * vm.pane.dataset.info.num_tof_bins):
        vm.pane.tick()
        bins.add(vm.pane.selection.tof)
        assert vm.pane.levels == locked
    assert len(bins) == vm.pane.dataset.info.num_tof_bins


def test_toggle_flips_between_adaptive_and_locked():
    vm = make_vm()
    vm.pane.toggle_level_lock()
    assert vm.pane.level_mode is LevelMode.LOCKED
    vm.pane.set_value("axial", 0)
    vm.pane.toggle_level_lock()
    assert vm.pane.level_mode is LevelMode.ADAPTIVE and vm.pane.levels == slice_range(vm)


def test_locking_twice_keeps_the_first_lock():
    vm = make_vm()
    vm.pane.set_level_mode(LevelMode.LOCKED)
    locked = vm.pane.levels
    vm.pane.set_value("axial", 0)
    vm.pane.set_level_mode(LevelMode.LOCKED)
    assert vm.pane.levels == locked


def test_lock_commands_are_harmless_before_anything_is_loaded():
    vm = ViewerViewModel(lambda o: o)
    notes = []
    vm.subscribe(notes.append)
    vm.pane.set_level_mode(LevelMode.LOCKED)
    vm.pane.toggle_level_lock()
    vm.pane.lock_global_range()
    vm.pane.set_manual_levels(1.0, 2.0)
    assert vm.pane.level_mode is LevelMode.ADAPTIVE and vm.pane.levels is None and vm.error is None


# ---- editing while locked ---------------------------------------------------------------------------
def test_dragging_or_typing_while_locked_keeps_the_lock_at_the_new_values():
    vm = make_vm()
    vm.pane.set_level_mode(LevelMode.LOCKED)
    vm.pane.set_manual_levels(0.5, 1.5)                        # histogram drag
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == (0.5, 1.5)
    vm.pane.set_level_bounds(high=3.0)                         # typed Max
    assert vm.pane.levels == (0.5, 3.0)
    for name, cmd in every_navigation(vm):
        cmd()
        assert vm.pane.levels == (0.5, 3.0), name


def test_editing_while_adaptive_locks_at_the_edited_values():
    vm = make_vm()
    vm.pane.set_level_bounds(low=0.25)
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels[0] == 0.25
    edited = vm.pane.levels
    vm.pane.set_value("axial", 0)
    assert vm.pane.levels == edited


def test_rejected_edit_while_locked_keeps_lock_and_values():
    vm = make_vm()
    vm.pane.set_level_mode(LevelMode.LOCKED)
    locked = vm.pane.levels
    vm.pane.set_manual_levels(5.0, 1.0)
    vm.pane.set_level_bounds(low=locked[1] + 1)
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == locked


def test_lock_to_global_range_locks_and_stays_put_across_tof_modes():
    vm = make_vm()
    vm.pane.lock_global_range()
    lo, hi = vm.pane.dataset.global_range(vm.pane.selection)
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == (lo, hi)
    for name, cmd in every_navigation(vm):     # includes Sum, whose own global range is larger
        cmd()
        assert vm.pane.levels == (lo, hi), name


def test_global_range_while_locked_replaces_the_lock():
    vm = make_vm()
    vm.pane.set_manual_levels(1.0, 2.0)
    vm.pane.lock_global_range()
    assert vm.pane.levels == vm.pane.dataset.global_range(vm.pane.selection) and vm.pane.level_mode is LevelMode.LOCKED


# ---- log display -------------------------------------------------------------------------------------
def test_log_toggle_maps_locked_levels_through_the_pixel_transform():
    vm = make_vm()
    vm.pane.lock_global_range()
    lo, hi = vm.pane.levels
    vm.pane.set_log_display(True)
    assert vm.pane.level_mode is LevelMode.LOCKED
    assert vm.pane.levels == pytest.approx((np.log1p(max(lo, 0.0)), np.log1p(hi)))
    vm.pane.set_value("axial", 0)
    vm.pane.set_log_display(False)
    assert vm.pane.levels == (lo, hi)


def test_levels_locked_in_log_scale_come_back_exactly():
    vm = make_vm()
    vm.pane.set_log_display(True)
    vm.pane.set_manual_levels(0.2, 1.1)
    vm.pane.set_log_display(False)
    assert vm.pane.levels == pytest.approx((np.expm1(0.2), np.expm1(1.1)))
    vm.pane.set_log_display(True)
    assert vm.pane.levels == (0.2, 1.1)


def test_negative_locked_levels_still_give_a_valid_log_range():
    vm = make_vm()
    vm.pane.set_manual_levels(-3.0, -1.0)
    vm.pane.set_log_display(True)
    lo, hi = vm.pane.levels
    assert lo == 0.0 and hi > lo and vm.pane.level_mode is LevelMode.LOCKED


# ---- unlocking -----------------------------------------------------------------------------------------
def test_unlocking_returns_to_per_slice_levels():
    vm = make_vm()
    vm.pane.set_manual_levels(1.0, 2.0)
    vm.pane.set_level_mode(LevelMode.ADAPTIVE)
    assert vm.pane.levels == slice_range(vm)
    for _, cmd in every_navigation(vm):
        cmd()
        assert vm.pane.levels == slice_range(vm)


# ---- status ----------------------------------------------------------------------------------------------
def test_locked_state_is_visible_in_the_context_chips_and_status():
    vm = make_vm()
    assert not any(c.startswith("Levels locked") for c in vm.pane.context)
    vm.pane.set_manual_levels(0.0, 3.86)
    assert vm.pane.context[-1] == "Levels locked 0 – 3.86" and "locked" in vm.status
    vm.pane.set_value("axial", 0)
    assert vm.pane.context[-1] == "Levels locked 0 – 3.86"
    vm.pane.set_log_display(True)
    assert vm.pane.context[-1] == format_level_lock(*vm.pane.levels, True) and vm.pane.context[-1].endswith("(log)")
    vm.pane.set_level_mode(LevelMode.ADAPTIVE)
    assert not any(c.startswith("Levels locked") for c in vm.pane.context) and "follow" in vm.status


def test_lock_and_unlock_notify_once_each():
    vm = make_vm()
    notes = []
    vm.pane.subscribe(notes.append)
    for cmd in (lambda: vm.pane.set_level_mode(LevelMode.LOCKED), vm.pane.toggle_level_lock, vm.pane.lock_global_range,
                lambda: vm.pane.set_manual_levels(1, 2)):
        notes.clear()
        cmd()
        assert len(notes) == 1


# ---- failures and new data -------------------------------------------------------------------------------
def test_failed_read_while_locked_keeps_the_lock_and_the_values():
    src = CountingSource(small_demo())
    vm = make_vm(src)
    vm.pane.set_manual_levels(1.0, 2.0)
    drop_caches(vm)
    src.fail = True
    before = vm.pane.selection
    vm.pane.set_value("segment", 1)
    vm.pane.set_tof_mode(TofMode.SUM)
    assert vm.error and vm.pane.selection == before
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == (1.0, 2.0)
    src.fail = False
    vm.pane.set_value("segment", 1)
    assert vm.pane.selection.segment == 1 and vm.pane.levels == (1.0, 2.0)


def test_failed_unlock_stays_locked():
    src = CountingSource(small_demo())
    vm = make_vm(src)
    vm.pane.set_manual_levels(1.0, 2.0)
    drop_caches(vm)
    src.fail = True
    vm.pane.set_level_mode(LevelMode.ADAPTIVE)
    assert vm.error and vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == (1.0, 2.0)


def test_failed_global_range_keeps_the_previous_lock():
    src = CountingSource(small_demo())
    vm = make_vm(src)
    vm.pane.set_manual_levels(1.0, 2.0)
    src.fail = True                     # the global range must read segments that are not cached
    vm.pane.lock_global_range()
    assert "global range" in vm.error and vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == (1.0, 2.0)


def test_failed_load_keeps_the_lock_and_the_values():
    def factory(obj):
        if obj == "bad":
            raise OSError("no such file")
        return obj
    vm = ViewerViewModel(factory)
    vm.load(small_demo())
    vm.pane.set_manual_levels(1.0, 2.0)
    assert vm.load("bad") is False
    assert vm.pane.level_mode is LevelMode.LOCKED and vm.pane.levels == (1.0, 2.0)
    vm.pane.set_value("axial", 0)
    assert vm.pane.levels == (1.0, 2.0)


def test_loading_a_new_data_set_unlocks():
    vm = make_vm()
    vm.pane.set_manual_levels(1.0, 2.0)
    assert vm.load(non_tof_source())
    assert vm.pane.level_mode is LevelMode.ADAPTIVE and vm.pane.levels == slice_range(vm)
    assert "unlocked" in vm.status
    assert not any(c.startswith("Levels locked") for c in vm.pane.context)
