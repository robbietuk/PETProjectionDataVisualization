# SPDX-License-Identifier: Apache-2.0
"""What the viewer remembers between sessions (#36, phase 6), without Qt: the recent files and the
pane's display, profile and animation choices, and how a damaged or old settings file is handled."""
import json

from fakes import small_demo
from pet_projection_data_visualization.viewmodel import LineMode, PlayMode, ProjectionPaneViewModel, ViewerViewModel


def _changed_viewer():
    vm = ViewerViewModel(lambda o: o)
    pane = vm.pane
    pane.set_colormap("magma")
    pane.set_log_display(True)
    pane.set_fps(12)
    pane.set_play_mode(PlayMode.BOUNCE)
    pane.set_show_tof_profile(False)
    pane.set_show_line_profile(False)
    pane.set_line_mode(LineMode.COLUMN)
    pane.set_show_tof_overlay(True)
    vm.recent_files = ("/data/b.hs", "/data/a.npy")
    return vm


def test_settings_are_plain_json_and_restore_exactly():
    saved = json.loads(json.dumps(_changed_viewer().settings()))      # what QSettings keeps
    fresh = ViewerViewModel(lambda o: o)
    assert fresh.settings() != saved
    fresh.restore_settings(saved)
    assert fresh.settings() == saved
    pane = fresh.pane
    assert (pane.colormap, pane.log_display, pane.fps, pane.play_mode) == ("magma", True, 12, PlayMode.BOUNCE)
    assert (pane.show_tof_profile, pane.show_line_profile, pane.line_mode, pane.show_tof_overlay) == (
        False, False, LineMode.COLUMN, True)
    assert fresh.recent_files == ("/data/b.hs", "/data/a.npy")


def test_restored_settings_apply_to_the_next_data_set():
    vm = ViewerViewModel(lambda o: o)
    vm.restore_settings(_changed_viewer().settings())
    assert vm.load(small_demo())
    assert vm.pane.log_display and vm.pane.colormap == "magma" and vm.pane.line_mode is LineMode.COLUMN


def test_settings_say_nothing_about_the_data_set():
    vm = ViewerViewModel(lambda o: o)
    vm.load(small_demo())
    keys = set(vm.pane.settings())
    assert not keys & {"selection", "levels", "level_mode", "slice_mode", "tof_mode", "free_line", "frozen_at"}


def test_bad_values_are_skipped_one_by_one():
    pane = ProjectionPaneViewModel()
    default = pane.settings()
    pane.restore_settings({"colormap": "rainbow", "fps": "fast", "play_mode": "SIDEWAYS", "line_mode": 3,
                           "log_display": "yes", "show_tof_profile": 0, "unknown": 1, "show_line_profile": False})
    expected = dict(default, show_line_profile=False)              # the one valid entry
    assert pane.settings() == expected
    pane.restore_settings({"fps": 1000, "colormap": "grey"})
    assert pane.fps == 30 and pane.colormap == "grey"                # clamped like the spin box
    pane.restore_settings({"fps": True})                             # a bool is not a speed
    assert pane.fps == 30


def test_malformed_viewer_settings_are_ignored():
    vm = ViewerViewModel(lambda o: o)
    vm.restore_settings({"recent_files": "not a list", "pane": ["not", "a", "dict"]})
    assert vm.recent_files == () and vm.pane.settings() == ProjectionPaneViewModel().settings()
    vm.restore_settings({"recent_files": ["/a.hs", 3, "", None] + [f"/f{i}.hs" for i in range(20)]})
    assert vm.recent_files[0] == "/a.hs" and len(vm.recent_files) == 8
