# SPDX-License-Identifier: Apache-2.0
"""Seeded random command sequences: invariants must hold after every single command."""
import random

import numpy as np
import pytest

from fakes import non_tof_source, small_demo
from pet_projection_data_visualization.model import DIMENSIONS, SliceMode, TofMode
from pet_projection_data_visualization.viewmodel import COLORMAPS, LevelMode, PlayMode, ViewerViewModel


def named_random_command(vm, rng):
    """(name of the view-model command, a call of it with random arguments)."""
    dim = rng.choice(DIMENSIONS)
    return rng.choice([
        ("set_value", lambda: vm.pane.set_value(dim, rng.randint(-50, 50))),
        ("step", lambda: vm.pane.step(dim, rng.choice([-3, -1, 1, 3]))),
        ("step_active", lambda: vm.pane.step_active(rng.choice([-1, 1]))),
        ("set_slice_mode", lambda: vm.pane.set_slice_mode(rng.choice(list(SliceMode)))),
        ("set_tof_mode", lambda: vm.pane.set_tof_mode(rng.choice(list(TofMode)))),
        ("set_playing", lambda: vm.pane.set_playing(rng.random() < 0.5)),
        ("toggle_play", lambda: vm.pane.toggle_play()),
        ("toggle_play_axis", lambda: vm.pane.toggle_play_axis(dim)),
        ("set_play_mode", lambda: vm.pane.set_play_mode(rng.choice(list(PlayMode)))),
        ("tick", lambda: vm.pane.tick()),
        ("set_fps", lambda: vm.pane.set_fps(rng.randint(-5, 60))),
        ("set_colormap", lambda: vm.pane.set_colormap(rng.choice(COLORMAPS))),
        ("set_level_mode", lambda: vm.pane.set_level_mode(rng.choice(list(LevelMode)))),
        ("set_log_display", lambda: vm.pane.set_log_display(rng.random() < 0.5)),
        ("set_manual_levels", lambda: vm.pane.set_manual_levels(rng.uniform(-1, 3), rng.uniform(-1, 3))),
        ("set_level_bounds", lambda: vm.pane.set_level_bounds(**{rng.choice(["low", "high"]): rng.uniform(-1, 3)})),
        ("toggle_level_lock", lambda: vm.pane.toggle_level_lock()),
        ("lock_global_range", lambda: vm.pane.lock_global_range()),
        ("hover_at", lambda: vm.pane.hover_at(rng.uniform(-20, 20), rng.uniform(-5, 20))),
        ("hover_leave", lambda: vm.pane.hover_leave()),
    ])


def random_command(vm, rng):
    return named_random_command(vm, rng)[1]


def check_invariants(vm):
    sel, info = vm.pane.selection, vm.pane.dataset.info
    assert sel.is_valid_for(info)
    rows = vm.pane.axis_rows
    assert [d.name for d in rows] == ["segment", sel.slice_mode.fixed_dimension] + (["tof"] if info.is_tof else [])
    for d in rows:
        assert d.lo <= d.value <= d.hi and d.value == sel.get(d.name)
        assert not d.enabled or d.hi > d.lo
        assert d.can_play == (d.hi > d.lo and (d.name != "tof" or sel.tof_mode is TofMode.BIN))
        assert d.playing == (vm.pane.play_axis == d.name)
    assert vm.pane.playing == (vm.pane.play_axis is not None)
    assert not vm.pane.playing or vm.pane.dimension(vm.pane.play_axis).can_play     # one axis, and a playable one
    assert vm.pane.can_play == vm.pane.dimension(vm.pane.play_target).can_play
    assert (vm.pane.tof_marker is not None) == (info.is_tof and sel.tof_mode is TofMode.BIN)
    assert 1 <= vm.pane.fps <= 30
    lo, hi = vm.pane.levels
    assert hi > lo
    assert vm.pane.image.data.shape == (int(vm.pane.image.height), int(vm.pane.image.width))
    assert vm.pane.image.data.dtype.name == "float32" and vm.pane.image.data.size > 0
    assert vm.pane.slice_mode is sel.slice_mode and vm.pane.tof_mode is sel.tof_mode
    assert vm.error is None


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("source", [small_demo, non_tof_source], ids=["tof", "non-tof"])
def test_invariants_hold_under_random_commands(seed, source):
    rng = random.Random(seed)
    vm = ViewerViewModel(lambda o: o)
    vm.load(source())
    for _ in range(250):
        random_command(vm, rng)()
        check_invariants(vm)


LEVEL_EDITS = ("set_level_mode", "toggle_level_lock", "lock_global_range", "set_manual_levels", "set_level_bounds")


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("source", [small_demo, non_tof_source], ids=["tof", "non-tof"])
def test_locked_levels_change_only_through_explicit_level_edits(seed, source):
    """While locked, no navigation (indices, slice/TOF mode, playback, hover, colour map) moves the levels;
    a log toggle maps them, and toggling back restores them exactly."""
    rng = random.Random(1000 + seed)
    vm = ViewerViewModel(lambda o: o)
    vm.load(source())
    vm.pane.set_level_mode(LevelMode.LOCKED)
    checked = 0
    for _ in range(300):
        name, cmd = named_random_command(vm, rng)
        before_mode, before_levels, before_log = vm.pane.level_mode, vm.pane.levels, vm.pane.log_display
        cmd()
        check_invariants(vm)
        if before_mode is LevelMode.LOCKED and name not in LEVEL_EDITS:
            assert vm.pane.level_mode is LevelMode.LOCKED, name
            if vm.pane.log_display == before_log:
                assert vm.pane.levels == before_levels, name
                checked += 1
        if vm.pane.level_mode is LevelMode.ADAPTIVE:
            assert vm.pane.levels == pytest.approx(_adaptive_levels(vm))
    assert checked > 50


def _adaptive_levels(vm):
    finite = vm.pane.image.data[np.isfinite(vm.pane.image.data)]
    lo, hi = float(finite.min()), float(finite.max())
    return (lo, hi) if hi > lo else vm.pane.levels
