# SPDX-License-Identifier: Apache-2.0
"""The projection data pane's view model on its own: no window view model, no Qt (#36, phase 1)."""
import pytest

from fakes import non_tof_source, small_demo
from pet_projection_data_visualization.model import ProjDataset, SliceMode
from pet_projection_data_visualization.viewmodel import LevelMode, ProjectionPaneViewModel, ViewerViewModel


class Broken:
    """A source whose slices cannot be read."""

    def __init__(self, inner):
        self.info = inner.info

    def get_segment(self, segment, tof_bin):
        raise OSError("unreadable")


def make_pane():
    status, errors = [], []
    pane = ProjectionPaneViewModel(on_status=status.append, on_error=errors.append)
    return pane, status, errors


def test_a_pane_works_without_a_window():
    pane, _, errors = make_pane()
    assert pane.image is None and pane.dataset is None and pane.title == ""
    was_locked = pane.show_dataset(ProjDataset(small_demo()))
    assert was_locked is False and errors == []
    assert pane.image is not None and pane.levels is not None and "demo" in pane.title
    assert pane.tof_available and pane.tof_range == (0, 4)
    pane.set_slice_mode(SliceMode.VIEWGRAM)
    assert pane.slice_mode is SliceMode.VIEWGRAM


def test_default_callbacks_do_nothing():
    pane = ProjectionPaneViewModel()
    pane.show_dataset(ProjDataset(small_demo()))
    pane.set_manual_levels(2.0, 1.0)                  # rejected: a status message nobody listens to
    pane.set_level_mode(LevelMode.LOCKED)
    assert pane.level_mode is LevelMode.LOCKED


def test_status_and_errors_go_to_the_callbacks():
    pane, status, errors = make_pane()
    pane.show_dataset(ProjDataset(small_demo()))
    pane.set_level_mode(LevelMode.LOCKED)
    assert status and status[-1].startswith("Colour levels locked")
    pane.set_manual_levels(2.0, 1.0)
    assert status[-1].startswith("Ignored level range")
    pane.hover_at(0.0, 3.0)
    assert errors == []


def test_show_dataset_returns_whether_a_lock_was_dropped():
    pane, _, _ = make_pane()
    pane.show_dataset(ProjDataset(small_demo()))
    pane.set_level_mode(LevelMode.LOCKED)
    assert pane.show_dataset(ProjDataset(non_tof_source())) is True
    assert pane.level_mode is LevelMode.ADAPTIVE and not pane.tof_available and pane.tof_range is None
    assert pane.show_dataset(ProjDataset(small_demo())) is False


def test_show_dataset_that_cannot_be_read_raises_and_changes_nothing():
    pane, _, _ = make_pane()
    pane.show_dataset(ProjDataset(small_demo()))
    before = (pane.image, pane.selection, pane.title, pane.levels)
    notes = []
    pane.subscribe(notes.append)
    with pytest.raises(Exception):
        pane.show_dataset(ProjDataset(Broken(non_tof_source())))
    assert (pane.image, pane.selection, pane.title, pane.levels) == before and notes == []


def test_the_window_view_model_owns_one_pane_and_relays_its_messages():
    vm = ViewerViewModel(lambda o: o)
    assert isinstance(vm.pane, ProjectionPaneViewModel)
    assert vm.load(small_demo())
    vm.pane.set_level_mode(LevelMode.LOCKED)
    assert vm.status.startswith("Colour levels locked")
    vm.pane.lock_global_range()
    vm.pane.dataset.global_range = lambda sel: (_ for _ in ()).throw(OSError("disk"))
    vm.pane.lock_global_range()
    assert vm.error and "disk" in vm.error and vm.status == vm.error


def test_window_state_is_separate_from_the_pane():
    vm = ViewerViewModel(lambda o: o)
    vm.load(small_demo())
    assert vm.source_label == vm.pane.title and vm.loaded
    assert not hasattr(vm, "levels") and not hasattr(vm.pane, "load")
