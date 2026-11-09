# SPDX-License-Identifier: Apache-2.0
"""Phase 3 of #36: the slice toolbar's rows and per-axis playback, without Qt."""
import pytest

from fakes import non_tof_source, small_demo
from pet_projection_data_visualization.model import Selection, SliceMode, TofMode
from pet_projection_data_visualization.viewmodel import (PlayMode, ViewerViewModel, next_play_value, play_blocker,
                                                         toolbar_axes)


def make_vm(source=None):
    vm = ViewerViewModel(source_factory=lambda obj: obj)
    assert vm.load(source or small_demo())
    return vm


def ticks(vm, n, dim):
    seen = []
    for _ in range(n):
        vm.pane.tick()
        seen.append(vm.pane.selection.get(dim))
    return seen


# ---- one step ------------------------------------------------------------------------------------------
def test_loop_wraps_round_in_both_directions():
    assert next_play_value(3, 0, 4, 1, PlayMode.LOOP) == (4, 1)
    assert next_play_value(4, 0, 4, 1, PlayMode.LOOP) == (0, 1)
    assert next_play_value(0, 0, 4, -1, PlayMode.LOOP) == (4, -1)
    assert next_play_value(-3, -3, 3, 1, PlayMode.LOOP) == (-2, 1)


def test_bounce_turns_round_at_each_end():
    assert next_play_value(3, 0, 4, 1, PlayMode.BOUNCE) == (4, 1)
    assert next_play_value(4, 0, 4, 1, PlayMode.BOUNCE) == (3, -1)
    assert next_play_value(0, 0, 4, -1, PlayMode.BOUNCE) == (1, 1)
    assert next_play_value(0, 0, 1, 1, PlayMode.BOUNCE) == (1, 1)
    assert next_play_value(1, 0, 1, 1, PlayMode.BOUNCE) == (0, -1)


@pytest.mark.parametrize("mode", list(PlayMode))
def test_a_single_value_stays_and_out_of_range_values_are_clamped_first(mode):
    assert next_play_value(5, 2, 2, 1, mode) == (2, 1)
    assert next_play_value(99, 0, 4, 1, mode)[0] == (0 if mode is PlayMode.LOOP else 3)


# ---- which rows, and what can play ----------------------------------------------------------------------
@pytest.mark.parametrize("mode,fixed", [(SliceMode.SINOGRAM, "axial"), (SliceMode.VIEWGRAM, "view"),
                                        (SliceMode.TANGENTIAL, "tangential")])
@pytest.mark.parametrize("source,tof", [(small_demo, True), (non_tof_source, False)], ids=["tof", "non-tof"])
def test_toolbar_axes_per_image_type(mode, fixed, source, tof):
    info = source().info
    sel = Selection.initial(info).with_slice_mode(mode)
    assert toolbar_axes(info, sel) == ("segment", fixed) + (("tof",) if tof else ())
    image_axes = {"axial", "view", "tangential"} - {fixed}
    for dim in image_axes:
        assert "axis of the image" in play_blocker(info, sel, dim)


@pytest.mark.parametrize("tof_mode", [TofMode.SUM, TofMode.MEAN, TofMode.MAX])
def test_tof_cannot_play_while_collapsed_and_the_reason_names_the_mode(tof_mode):
    info = small_demo().info
    sel = Selection.initial(info).with_tof_mode(tof_mode)
    reason = play_blocker(info, sel, "tof")
    assert reason is not None and tof_mode.name.capitalize() in reason and "Bin" in reason
    assert play_blocker(info, sel, "segment") is None and play_blocker(info, sel, "axial") is None
    assert play_blocker(info, sel.with_tof_mode(TofMode.BIN), "tof") is None


def test_collapsing_tof_keeps_the_tof_row_with_its_play_disabled():
    vm = make_vm()
    vm.pane.set_tof_mode(TofMode.MEAN)
    tof = vm.pane.dimension("tof")
    assert not tof.can_play and not tof.enabled and "Mean" in tof.play_tip
    vm.pane.toggle_play_axis("tof")
    assert not vm.pane.playing


# ---- one axis at a time ------------------------------------------------------------------------------------
def test_a_rows_play_button_plays_its_axis_and_pressing_it_again_pauses():
    vm = make_vm()
    vm.pane.toggle_play_axis("segment")
    assert vm.pane.playing and vm.pane.play_axis == "segment"
    assert [r.name for r in vm.pane.axis_rows if r.playing] == ["segment"]
    assert ticks(vm, 3, "segment") == [1, -1, 0]                    # segments -1..1, from 0, looping
    vm.pane.toggle_play_axis("segment")
    assert not vm.pane.playing and vm.pane.play_axis is None


def test_pressing_another_rows_play_switches_to_that_axis():
    vm = make_vm()
    vm.pane.toggle_play_axis("tof")
    tof = vm.pane.selection.tof
    vm.pane.toggle_play_axis("axial")
    assert vm.pane.play_axis == "axial" and [r.name for r in vm.pane.axis_rows if r.playing] == ["axial"]
    axial = vm.pane.selection.axial
    vm.pane.tick()
    assert vm.pane.selection.axial == axial + 1 and vm.pane.selection.tof == tof   # only the playing axis moves


def test_space_plays_and_pauses_the_axis_played_last():
    vm = make_vm()
    assert vm.pane.play_target == "tof"                          # TOF data: TOF first, as before
    vm.pane.toggle_play_axis("segment")
    vm.pane.toggle_play()                                        # Space pauses ...
    assert not vm.pane.playing
    vm.pane.toggle_play()                                        # ... and plays the segment again, not TOF
    assert vm.pane.play_axis == "segment"
    assert vm.pane.space_hint == "Space pauses the segment"


def test_space_falls_back_when_the_last_axis_became_an_image_axis():
    vm = make_vm()
    vm.pane.toggle_play_axis("axial")
    vm.pane.set_slice_mode(SliceMode.VIEWGRAM)                  # axial is now an axis of the image
    assert not vm.pane.playing and vm.pane.play_target == "tof"
    vm = make_vm(non_tof_source())
    vm.pane.toggle_play_axis("axial")
    vm.pane.set_slice_mode(SliceMode.TANGENTIAL)
    assert not vm.pane.playing and vm.pane.play_target == "tangential"
    assert vm.pane.space_hint == "Space plays the tangential position"


def test_changing_the_image_type_keeps_tof_and_segment_playing():
    vm = make_vm()
    vm.pane.toggle_play_axis("segment")
    vm.pane.set_slice_mode(SliceMode.TANGENTIAL)
    assert vm.pane.play_axis == "segment"
    vm.pane.toggle_play_axis("tof")
    vm.pane.set_slice_mode(SliceMode.VIEWGRAM)
    assert vm.pane.play_axis == "tof"


def test_collapsing_tof_stops_tof_but_not_another_axis():
    vm = make_vm()
    vm.pane.toggle_play_axis("tof")
    vm.pane.set_tof_mode(TofMode.SUM)
    assert not vm.pane.playing and not vm.pane.can_play           # Space would play TOF: disabled
    vm.pane.toggle_play_axis("axial")
    vm.pane.set_tof_mode(TofMode.MAX)
    assert vm.pane.play_axis == "axial" and vm.pane.can_play


def test_playing_the_segment_keeps_the_axial_position_in_range():
    vm = make_vm()
    vm.pane.set_value("axial", 7)                                 # the last axial position of segment 0
    vm.pane.toggle_play_axis("segment")
    for _ in range(6):
        vm.pane.tick()
        lo, hi = vm.pane.dimension("axial").lo, vm.pane.dimension("axial").hi
        assert lo <= vm.pane.selection.axial <= hi


def test_bounce_plays_back_and_forth():
    vm = make_vm()
    vm.pane.set_play_mode(PlayMode.BOUNCE)
    vm.pane.toggle_play_axis("tof")                               # TOF bins 0..4, from 2
    assert ticks(vm, 8, "tof") == [3, 4, 3, 2, 1, 0, 1, 2]


def test_a_new_play_starts_forwards_even_after_bouncing_back():
    vm = make_vm()
    vm.pane.set_play_mode(PlayMode.BOUNCE)
    vm.pane.toggle_play_axis("tof")
    ticks(vm, 3, "tof")                                            # 3, 4, 3: going down
    vm.pane.toggle_play_axis("tof")
    vm.pane.toggle_play_axis("tof")
    assert ticks(vm, 1, "tof") == [4]


def test_loading_a_new_data_set_stops_playback_and_forgets_the_last_axis():
    vm = make_vm()
    vm.pane.toggle_play_axis("segment")
    vm.load(small_demo())
    assert not vm.pane.playing and vm.pane.play_target == "tof"
