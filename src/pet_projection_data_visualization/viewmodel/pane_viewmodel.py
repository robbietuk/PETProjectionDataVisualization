# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""VIEWMODEL layer: one projection data pane, the self-contained display of one data set.

A pane owns everything about the data set it shows: the selection (slice mode, indices, TOF mode),
the display (colour map, log display, colour levels and their lock), the hover readout, the TOF
profile and playback. It knows nothing about files or the window; the window-level view model
hands it a ``ProjDataset`` with ``show_dataset`` and receives its status and error messages through
the ``on_status``/``on_error`` callbacks. Several panes can later share one window (#20).
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Callable, Concatenate, ParamSpec, TypeVar

import numpy as np
import numpy.typing as npt

from ..model import (ProjDataset, Selection, SliceImage, SliceMode, SliceStats, TofMode,
                     finite_range)
from ..model.selection import DIMENSIONS
from . import formatting
from .observable import Observed, ObservableObject
from .options import COLORMAPS, LevelMode

DIM_LABELS = {
    "segment": "Segment",
    "axial": "Axial position",
    "view": "View",
    "tangential": "Tangential position",
    "tof": "TOF bin",
}
MIN_FPS, MAX_FPS = 1, 30

MessageSink = Callable[[str], None]

_P = ParamSpec("_P")
_R = TypeVar("_R")


@dataclass(frozen=True)
class DimensionState:
    """What one slider/spin-box pair should show."""
    name: str
    label: str
    lo: int
    hi: int
    value: int
    enabled: bool


@dataclass(frozen=True)
class DisplayImage:
    """A ready-to-draw image: values (log-transformed if requested) and its rectangle in axis
    coordinates, where integer positions are pixel centres."""
    data: npt.NDArray[np.float32]
    x0: float
    y0: float
    width: float
    height: float
    row_label: str
    col_label: str
    title: str


@dataclass(frozen=True)
class TofProfile:
    x: tuple[int, ...]
    y: tuple[float, ...]
    title: str


@dataclass(frozen=True)
class _Rendered:
    image: SliceImage
    display: npt.NDArray[np.float32]
    levels: tuple[float, float]
    stats: SliceStats


@dataclass(frozen=True)
class _LevelLock:
    """Locked colour levels, kept in the display scale they were set in (``log`` = log(1 + x) display).

    Shown in the same scale they are returned exactly, so toggling the log display back and forth never
    drifts them; shown in the other scale they are mapped through the same transform as the pixel values
    (``x -> log(1 + max(x, 0))``, or its inverse ``expm1``), so they mark the same data values."""
    lo: float
    hi: float
    log: bool

    def shown(self, log_display: bool) -> tuple[float, float]:
        if log_display == self.log:
            return self.lo, self.hi
        if log_display:
            return float(np.log1p(max(self.lo, 0.0))), float(np.log1p(max(self.hi, 0.0)))
        return float(np.expm1(self.lo)), float(np.expm1(self.hi))


def _min_span(value: float) -> float:
    """Smallest usable width of a level range starting at ``value`` (for constant data)."""
    return max(abs(value) * 1e-6, float(np.finfo(np.float32).tiny))


def _command(fn: Callable[Concatenate[ProjectionPaneViewModel, _P], _R]) -> Callable[Concatenate[ProjectionPaneViewModel, _P], _R]:
    """Run a view-model method as one transaction: subscribers are notified once at the end."""
    @functools.wraps(fn)
    def wrapper(self: ProjectionPaneViewModel, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        with self.transaction():
            return fn(self, *args, **kwargs)
    return wrapper


class ProjectionPaneViewModel(ObservableObject):
    # ---- observable state (read-only for the view) --------------------------------
    title: Observed[str] = Observed("")              # name of the data set shown in this pane
    dimensions: Observed[tuple[DimensionState, ...]] = Observed(())
    slice_mode: Observed[SliceMode] = Observed(SliceMode.SINOGRAM)
    tof_mode: Observed[TofMode] = Observed(TofMode.BIN)
    tof_available: Observed[bool] = Observed(False)
    tof_range: Observed[tuple[int, int] | None] = Observed(None)   # (first, last) TOF bin; None for non-TOF data
    can_play: Observed[bool] = Observed(False)
    playing: Observed[bool] = Observed(False)
    fps: Observed[int] = Observed(4)
    tof_marker: Observed[int | None] = Observed(None)   # TOF bin to mark in the profile plot, or None
    colormap: Observed[str] = Observed(COLORMAPS[0])
    level_mode: Observed[LevelMode] = Observed(LevelMode.ADAPTIVE)  # LOCKED: ``levels`` stay constant while navigating
    log_display: Observed[bool] = Observed(False)
    image: Observed[DisplayImage | None] = Observed(None)
    levels: Observed[tuple[float, float] | None] = Observed(None)   # (lo, hi)
    info_text: Observed[str] = Observed("")
    summary: Observed[str] = Observed("")            # scanner, dimensions and TOF yes/no, in a few lines
    show_tof_profile: Observed[bool] = Observed(True)   # the user's choice; shown only for TOF data
    pixel_text: Observed[str] = Observed("")
    tof_profile: Observed[TofProfile | None] = Observed(None)
    metrics: Observed[tuple[tuple[str, str], ...]] = Observed(())   # (label, value) for the current slice
    context: Observed[tuple[str, ...]] = Observed(())   # chips describing the current selection

    def __init__(self, on_status: MessageSink | None = None, on_error: MessageSink | None = None) -> None:
        """``on_status`` receives status-bar messages, ``on_error`` failures to show to the user (once per
        failure, also when the text repeats). Both default to doing nothing."""
        super().__init__()
        self._on_status: MessageSink = on_status or (lambda _message: None)
        self._on_error: MessageSink = on_error or (lambda _message: None)
        self._dataset: ProjDataset | None = None
        self._selection: Selection | None = None
        self._slice: SliceImage | None = None
        self._lock: _LevelLock | None = None      # set exactly when level_mode is LOCKED
        self._last_pixel: tuple[int, int] | None = None
        self._cursor: tuple[float, float] | None = None     # last hover position in axis coordinates

    # ---- read access for tests and views --------------------------------------------
    @property
    def selection(self) -> Selection | None:
        return self._selection

    @property
    def dataset(self) -> ProjDataset | None:
        return self._dataset

    def dimension(self, name: str) -> DimensionState:
        return next(d for d in self.dimensions if d.name == name)

    # ---- commands --------------------------------------------------------------------
    @_command
    def show_dataset(self, dataset: ProjDataset) -> bool:
        """Show ``dataset`` from its initial selection. Raises if its first slice cannot be read, and then
        nothing changes. Returns True if colour levels locked on the previous data set were unlocked."""
        selection = Selection.initial(dataset.info)
        rendered = self._render(dataset, selection, None)   # first slice must be readable
        # A new data set starts adaptive: limits locked on another data set (other units, other scale)
        # would show it saturated or black without saying why.
        was_locked = self._lock is not None
        self._lock = None
        self.level_mode = LevelMode.ADAPTIVE
        self.playing = False
        self.title = dataset.info.name
        self.summary = formatting.dataset_summary(dataset.info)
        self.tof_available = dataset.info.is_tof
        self.tof_range = (dataset.info.min_tof, dataset.info.max_tof) if dataset.info.is_tof else None
        self.tof_profile = None
        self.pixel_text = ""
        self._cursor = None
        self._commit(dataset, selection, rendered)
        return was_locked

    @_command
    def set_value(self, dim: str, value: int) -> None:
        if (current := self._current()) is not None:
            dataset, sel = current
            self._show(sel.with_value(dataset.info, dim, value))

    @_command
    def step(self, dim: str, delta: int) -> None:
        if (current := self._current()) is not None:
            _, sel = current
            self.set_value(dim, sel.get(dim) + delta)

    @_command
    def step_active(self, delta: int) -> None:
        if (current := self._current()) is not None:
            _, sel = current
            self.step(sel.active_dimension, delta)

    @_command
    def set_slice_mode(self, mode: SliceMode) -> None:
        if (current := self._current()) is not None:
            _, sel = current
            self._show(sel.with_slice_mode(mode))

    @_command
    def set_tof_mode(self, mode: TofMode) -> None:
        if (current := self._current()) is not None:
            _, sel = current
            self._show(sel.with_tof_mode(mode))

    @_command
    def set_playing(self, playing: bool) -> None:
        self.playing = bool(playing) and self.can_play

    @_command
    def toggle_play(self) -> None:
        self.set_playing(not self.playing)

    @_command
    def set_show_tof_profile(self, shown: bool) -> None:
        """Show or hide the TOF profile plot (it is never shown for non-TOF data)."""
        self.show_tof_profile = bool(shown)

    @_command
    def set_fps(self, fps: int) -> None:
        self.fps = int(min(max(fps, MIN_FPS), MAX_FPS))

    @_command
    def tick(self) -> None:
        """One playback step; the view calls this from its timer. Ignored unless ``playing``,
        so a stale timer event after pause/error/collapse does nothing."""
        current = self._current()
        if current is None or not self.playing:
            return
        if not self.can_play:
            self.playing = False
            return
        dataset, sel = current
        self._show(sel.step_tof(dataset.info, 1))

    @_command
    def set_colormap(self, name: str) -> None:
        if name not in COLORMAPS:
            raise ValueError(f"unknown colour map {name!r}; choose from {COLORMAPS}")
        self.colormap = name

    @_command
    def set_level_mode(self, mode: LevelMode) -> None:
        """ADAPTIVE: levels follow every slice. LOCKED: freeze the levels shown now, so they stay constant
        across every navigation (index, slice mode, TOF bin or reduction, playback, log toggle) until
        edited or unlocked. Ignored while nothing is loaded."""
        mode = LevelMode(mode)
        if not self._ready() or mode is self.level_mode:
            return
        if mode is LevelMode.LOCKED:
            lo, hi = self._shown_levels()
            self._lock_at(_LevelLock(lo, hi, self.log_display))
        else:
            self._apply_lock(None)

    @_command
    def toggle_level_lock(self) -> None:
        """Adaptive <-> Locked (the view's keyboard shortcut)."""
        self.set_level_mode(LevelMode.ADAPTIVE if self.level_mode is LevelMode.LOCKED else LevelMode.LOCKED)

    @_command
    def lock_global_range(self) -> None:
        """Lock the levels at the range of the whole data set as displayed in the current TOF mode
        (every segment and, for single bins, every TOF bin). Reads everything once; on failure nothing changes."""
        current = self._current()
        if current is None:
            return
        dataset, sel = current
        try:
            lo, hi = dataset.global_range(sel)
        except Exception as exc:  # noqa: BLE001 - keep the current levels, tell the user why
            self._report_error(f"Could not compute the global range: {exc}")
            self._mark_changed("level_mode", "levels")       # snap the widgets back
            return
        if hi <= lo:
            hi = lo + _min_span(lo)
        self._lock_at(_LevelLock(float(lo), float(hi), False))   # data units; mapped if log display is on

    @_command
    def set_log_display(self, enabled: bool) -> None:
        """Adaptive levels are recomputed in the new scale; locked levels stay locked and are mapped
        through the same transform as the pixels (see ``_LevelLock``)."""
        old = self.log_display
        self.log_display = bool(enabled)
        if (current := self._current()) is not None and not self._show(current[1]):
            self.log_display = old

    @_command
    def set_manual_levels(self, lo: float, hi: float) -> None:
        """The user dragged the histogram region or typed a limit: lock the levels at (lo, hi) in the
        displayed scale (this locks them if they were adaptive). An empty, inverted or non-finite range is
        rejected; ``levels`` is then re-announced so the view puts its widgets back."""
        if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
            self._on_status(f"Ignored level range {lo:g} .. {hi:g}: the minimum must be below the maximum")
            self._mark_changed("levels")
            return
        if self._ready():
            self._lock_at(_LevelLock(float(lo), float(hi), self.log_display))

    @_command
    def set_level_bounds(self, low: float | None = None, high: float | None = None) -> None:
        """Type in one or both colour-scale limits (locks the levels). Ignored if it would
        make the range empty or inverted."""
        cur_lo, cur_hi = self.levels if self.levels is not None else (0.0, 1.0)
        lo = cur_lo if low is None else float(low)
        hi = cur_hi if high is None else float(high)
        self.set_manual_levels(lo, hi)

    @_command
    def hover_at(self, x: float, y: float) -> None:
        """Cursor at axis coordinates (x = column axis, y = row axis) of the displayed image."""
        if self._slice is None or self._dataset is None:
            return
        self._cursor = (x, y)
        self._hover(x, y)

    @_command
    def hover_leave(self) -> None:
        self._cursor = None
        self.pixel_text = ""

    def _hover(self, x: float, y: float) -> None:
        image, (dataset, _) = self._slice, self._loaded()
        assert image is not None, "a slice is shown whenever data is loaded"
        row, col = image.pixel_from_axes(x, y)
        value = image.value_at(row, col)
        if value is None:
            self.pixel_text = ""
            return
        self.pixel_text = formatting.format_pixel(image, row, col, value)
        if dataset.info.is_tof and (row, col) != self._last_pixel:
            self._last_pixel = (row, col)
            self._update_tof_profile(image.indices_at(row, col))

    # ---- internals ---------------------------------------------------------------------
    def _ready(self) -> bool:
        return self._current() is not None

    def _current(self) -> tuple[ProjDataset, Selection] | None:
        """The loaded data set and the current selection, or None before the first successful load."""
        if self._dataset is None or self._selection is None:
            return None
        return self._dataset, self._selection

    def _loaded(self) -> tuple[ProjDataset, Selection]:
        """``_current()`` for the internals that only run once data is loaded."""
        current = self._current()
        assert current is not None, "no data loaded"
        return current

    def _shown_levels(self) -> tuple[float, float]:
        """The levels on screen; there always are some once data is loaded."""
        levels = self.levels
        assert levels is not None, "no data loaded"
        return levels

    def _report_error(self, message: str) -> None:
        self._on_error(message)

    def _lock_at(self, lock: _LevelLock) -> None:
        if self._apply_lock(lock):
            lo, hi = self._shown_levels()
            self._on_status(f"Colour levels locked at {formatting.format_number(lo)} .. {formatting.format_number(hi)}")

    def _apply_lock(self, lock: _LevelLock | None) -> bool:
        """Switch to ``lock`` (None: adaptive) and redraw the current slice. All or nothing, like ``_show``."""
        old = self._lock
        self._lock = lock
        self.level_mode = LevelMode.ADAPTIVE if lock is None else LevelMode.LOCKED
        if self._show(self._loaded()[1]):
            if lock is None:
                self._on_status("Colour levels follow each slice")
            return True
        self._lock = old
        self.level_mode = LevelMode.ADAPTIVE if old is None else LevelMode.LOCKED
        return False

    def _show(self, selection: Selection) -> bool:
        """Display ``selection`` of the current data set. All or nothing: if the slice cannot be read the
        previous selection, picture and controls stay (the view is told to repaint the controls)."""
        try:
            dataset, _ = self._loaded()
            rendered = self._render(dataset, selection, self._lock)
        except Exception as exc:  # noqa: BLE001 - keep the previous picture, tell the user why
            self.playing = False         # never keep playing into a stream of identical errors
            self._report_error(f"Could not read the slice: {exc}")
            self._mark_changed("dimensions", "slice_mode", "tof_mode", "level_mode", "log_display")  # snap back
            return False
        self._commit(dataset, selection, rendered)
        return True

    def _commit(self, dataset: ProjDataset, sel: Selection, rendered: "_Rendered") -> None:
        """Make ``dataset``/``sel`` current and publish everything derived from them (cannot fail)."""
        self._dataset, self._selection = dataset, sel
        info = dataset.info
        self.slice_mode = sel.slice_mode
        self.tof_mode = sel.tof_mode
        self.can_play = info.is_tof and sel.tof_mode is TofMode.BIN
        if not self.can_play:
            self.playing = False
        self.tof_marker = sel.tof if self.can_play else None
        self._refresh_dimensions()
        image = rendered.image
        self._slice = image
        rows, cols = image.shape
        self.image = DisplayImage(rendered.display, image.col_origin - 0.5, image.row_origin - 0.5,
                                  float(cols), float(rows), image.row_axis, image.col_axis, image.title)
        self.levels = rendered.levels
        self.metrics = formatting.format_metrics(rendered.stats)
        self.context = formatting.context_chips(info, sel) + (
            (formatting.format_level_lock(*rendered.levels, self.log_display),) if self._lock is not None else ())
        self.info_text = (formatting.describe_dataset(info) + "\n\n"
                          + formatting.describe_slice(image, rendered.stats))
        # the LOR under a resting cursor changes with the selection: recompute readout and profile
        self._last_pixel = None
        if self._cursor is not None:
            self._hover(*self._cursor)
        else:
            self.tof_profile = None

    def _refresh_dimensions(self) -> None:
        dataset, sel = self._loaded()
        info = dataset.info
        active = sel.active_dimension
        states: list[DimensionState] = []
        for dim in DIMENSIONS:
            lo, hi = sel.range(info, dim)
            wanted = dim in ("segment", active) or (dim == "tof" and info.is_tof and sel.tof_mode is TofMode.BIN)
            states.append(DimensionState(dim, DIM_LABELS[dim], lo, hi, sel.get(dim), wanted and hi > lo))
        self.dimensions = tuple(states)

    def _display_values(self, data: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
        if self.log_display:
            return np.log1p(np.clip(data, 0, None)).astype(np.float32)
        return np.ascontiguousarray(data, dtype=np.float32)

    def _render(self, dataset: ProjDataset, sel: Selection, lock: _LevelLock | None) -> "_Rendered":
        """Everything needed to show ``sel``, computed without touching any observable state (may raise).
        Locked levels depend only on ``lock`` and the display scale, never on the slice."""
        image = dataset.slice(sel)
        disp = self._display_values(image.data)
        lo, hi = lock.shown(self.log_display) if lock is not None else (finite_range(disp) or (0.0, 1.0))
        if hi <= lo:
            hi = lo + _min_span(lo)
        return _Rendered(image, disp, (float(lo), float(hi)), dataset.stats(image))

    def _update_tof_profile(self, indices: dict[str, int]) -> None:
        dataset, sel = self._loaded()
        lor = {d: sel.get(d) for d in ("view", "axial", "tangential")}
        lor.update(indices)
        try:
            prof = dataset.tof_profile(sel.segment, lor["view"], lor["axial"], lor["tangential"])
        except Exception as exc:  # noqa: BLE001
            self._report_error(f"TOF profile unavailable: {exc}")
            return
        self.tof_profile = TofProfile(
            tuple(dataset.info.tof_bins), tuple(float(v) for v in prof),
            formatting.format_profile_title(sel.segment, lor["view"], lor["axial"], lor["tangential"],
                                            float(prof.sum())))
