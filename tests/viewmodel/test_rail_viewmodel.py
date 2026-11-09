# SPDX-License-Identifier: Apache-2.0
"""What the icon rail shows (#36, phase 2), without Qt: the hover summaries, recent files, the STIR
status, the profile plot switch and the shortcut list."""
import dataclasses
import os

import pytest

from fakes import non_tof_source, small_demo
from pet_projection_data_visualization.model import ProjDataset
from pet_projection_data_visualization.viewmodel import KEYBOARD_SHORTCUTS, ProjectionPaneViewModel, ViewerViewModel
from pet_projection_data_visualization.viewmodel import formatting
from pet_projection_data_visualization.viewmodel.viewer_viewmodel import MAX_RECENT_FILES, NO_STIR_PROBE


class Unreadable(Exception):
    pass


def factory(obj):
    """Paths load a small demo, except paths with 'missing' in them; anything else is a source."""
    if isinstance(obj, str):
        if "missing" in obj:
            raise Unreadable(obj)
        src = small_demo()
        src.info = dataclasses.replace(src.info, name=os.path.basename(obj), extra={})
        return src
    return obj


def make_vm(**kw):
    return ViewerViewModel(factory, demo_factory=small_demo, **kw)


# ---- the Data peek: where the data comes from and its format ----
def test_data_summary_before_and_after_loading_a_file():
    vm = make_vm()
    assert vm.data_summary == "No data loaded"
    assert vm.load("/data/scan.hs")
    assert vm.data_summary == "/data/scan.hs\nFormat: Interfile (read with STIR)"


def test_data_summary_of_demo_and_in_memory_data_names_the_data_set():
    vm = make_vm()
    vm.load_demo()
    assert vm.data_summary.splitlines() == [vm.pane.title, "Format: synthetic"]
    vm.load(non_tof_source())
    assert vm.data_summary.splitlines() == ["non-tof", "Format: in-memory data"]


def test_a_failed_load_keeps_the_data_summary():
    vm = make_vm()
    vm.load("/data/scan.npz")
    vm.load("/data/missing.hs")
    assert vm.data_summary.startswith("/data/scan.npz") and vm.error


@pytest.mark.parametrize("extra, path, expected", [
    ({"format": "numpy .npz"}, "/x/a.hs", "numpy .npz"),          # the source knows best
    ({}, "/x/a.HS", "Interfile (read with STIR)"),
    ({}, "/x/a.npy", "numpy .npy"),
    ({}, "/x/a.v", "v file"),
    ({}, "/x/noext", "file"),
    ({}, "", "in-memory data"),
])
def test_describe_format(extra, path, expected):
    info = dataclasses.replace(small_demo().info, extra=extra)
    assert formatting.describe_format(info, path) == expected


# ---- recent files ----
def test_recent_files_are_most_recent_first_and_listed_once():
    vm = make_vm()
    for path in ("/d/a.hs", "/d/b.hs", "/d/a.hs"):
        vm.load(path)
    assert vm.recent_files == ("/d/a.hs", "/d/b.hs")


def test_the_same_file_typed_differently_is_listed_once():
    vm = make_vm()
    vm.load("/d/a.hs")
    vm.load_path('  "/d/../d/a.hs"  ')
    assert len(vm.recent_files) == 1


def test_recent_files_keep_only_the_latest():
    vm = make_vm()
    for i in range(MAX_RECENT_FILES + 3):
        vm.load(f"/d/f{i}.hs")
    assert len(vm.recent_files) == MAX_RECENT_FILES
    assert vm.recent_files[0] == f"/d/f{MAX_RECENT_FILES + 2}.hs"


def test_demo_in_memory_and_failed_loads_are_not_recent_files():
    vm = make_vm()
    vm.load_demo()
    vm.load(non_tof_source())
    vm.load("/d/missing.hs")
    assert vm.recent_files == ()


def test_recent_files_notify_once_per_load():
    vm = make_vm()
    seen = []
    vm.subscribe(lambda names: seen.append("recent_files" in names))
    vm.load("/d/a.hs")
    assert seen == [True]


# ---- STIR status ----
def test_without_a_probe_the_stir_status_says_it_was_not_checked():
    vm = make_vm()
    assert vm.stir_available is False and vm.stir_status == NO_STIR_PROBE


def test_the_probe_is_asked_at_start_and_again_on_refresh():
    answers = iter([(False, "STIR not found"), (True, "STIR found in /opt/stir")])
    vm = make_vm(stir_probe=lambda: next(answers))
    assert (vm.stir_available, vm.stir_status) == (False, "STIR not found")
    vm.refresh_stir_status()
    assert (vm.stir_available, vm.stir_status) == (True, "STIR found in /opt/stir")


def test_a_failing_probe_is_a_status_not_a_crash():
    def probe():
        raise RuntimeError("boom")
    vm = make_vm(stir_probe=probe)
    assert vm.stir_available is False and "boom" in vm.stir_status and vm.error is None


# ---- the Data set peek ----
def test_dataset_summary_names_scanner_dimensions_and_tof():
    pane = ProjectionPaneViewModel()
    assert pane.summary == ""
    src = small_demo()
    src.info = dataclasses.replace(src.info, extra={"scanner": "Discovery MI"})
    pane.show_dataset(ProjDataset(src))
    lines = pane.summary.splitlines()
    info = src.info
    assert lines[0] == "Scanner: Discovery MI"
    assert f"Segments {info.num_segments}, views {info.num_views}" in lines[1]
    assert f"tangential {info.num_tangential}" in lines[1]
    assert lines[2] == f"TOF: yes, {info.num_tof_bins} bins"


def test_dataset_summary_of_non_tof_data_without_a_scanner():
    pane = ProjectionPaneViewModel()
    pane.show_dataset(ProjDataset(non_tof_source()))
    lines = pane.summary.splitlines()
    assert lines[0] == "Scanner: not recorded" and lines[2] == "TOF: no"
    assert "axial 3-4" in lines[1]                    # segments with different axial counts show the range


# ---- the Profiles and settings flyout ----
def test_the_tof_profile_can_be_hidden_and_shown():
    pane = ProjectionPaneViewModel()
    assert pane.show_tof_profile is True
    pane.set_show_tof_profile(False)
    assert pane.show_tof_profile is False
    pane.show_dataset(ProjDataset(small_demo()))      # a new data set keeps the user's choice
    assert pane.show_tof_profile is False
    pane.set_show_tof_profile(True)
    assert pane.show_tof_profile is True


def test_the_shortcut_list_names_every_window_key():
    keys = " ".join(k for k, _ in KEYBOARD_SHORTCUTS)
    for key in ("Space", "Left", "Right", "Page Up", "Page Down", "L", "Esc"):
        assert key in keys
    assert all(action for _, action in KEYBOARD_SHORTCUTS)
