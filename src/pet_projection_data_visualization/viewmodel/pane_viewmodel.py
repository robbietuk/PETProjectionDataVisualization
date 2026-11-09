# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""VIEWMODEL layer: one projection data pane, the self-contained display of one data set.

A pane owns everything about the data set it shows: the selection (slice mode, indices, TOF mode),
the display (colour map, log display, colour levels and their lock), the hover readout (and the corner
it floats in), the profiles (the TOF profile and the Row | Column | Free line profile, see ``profiles``;
a click freezes them at one LOR, ``release_freeze`` lets them follow the cursor again) and playback.

The slice toolbar has one row (``axis_rows``) per axis not shown in the image: the segment, the fixed
axis of the image type and, for TOF data, the TOF bin. Each row can play its axis; only one plays at a
time (``play_axis``), and Space (``toggle_play``) plays or pauses the axis played last. It knows nothing about files or the window; the window-level view model
hands it a ``ProjDataset`` with ``show_dataset`` and receives its status and error messages through
the ``on_status``/``on_error`` callbacks. Several panes can later share one window (#20).
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Callable, Concatenate, ParamSpec, TypeVar

import numpy as np
import numpy.typing as npt

from ..model import (ProjDataInfo, ProjDataset, Selection, SliceImage, SliceMode, SliceStats, TofMode,
                     finite_range)
from . import formatting
from .observable import Observed, ObservableObject
from .options import COLORMAPS, LevelMode
from .playback import PlayMode, next_play_value
from .profiles import (FreeLine, LineMode, LineProfile, Lor, TofProfile, default_free_line, image_position,
                       line_axis_names, line_profile_for, lor_at, tof_profile)
from .readout import DEFAULT_CORNER, Corner, readout_corner

DIM_LABELS = {
    "segment": "Segment",
    "axial": "Axial position",
    "view": "View",
    "tangential": "Tangential position",
    "tof": "TOF bin",
}
DIM_NOUNS = {dim: label if label.startswith("TOF") else label.lower() for dim, label in DIM_LABELS.items()}
MIN_FPS, MAX_FPS = 1, 30

MessageSink = Callable[[str], None]

_P = ParamSpec("_P")
_R = TypeVar("_R")


@dataclass(frozen=True)
class AxisRow:
    """One row of the slice toolbar: an axis that is not shown in the image (the segment, the fixed axis
    of the image type and, for TOF data, the TOF bin)."""
    name: str
    label: str
    lo: int
    hi: int
    value: int
    enabled: bool        # the value can be changed: more than one value and, for TOF, a single bin shown
    can_play: bool
    play_tip: str        # what the play button plays, or why it cannot
    playing: bool        # this axis is the one playing


def toolbar_axes(info: ProjDataInfo, sel: Selection) -> tuple[str, ...]:
    """The axes with a toolbar row, in order: segment, the fixed axis of the image type, then TOF."""
    return ("segment", sel.slice_mode.fixed_dimension) + (("tof",) if info.is_tof else ())


def play_blocker(info: ProjDataInfo, sel: Selection, dim: str) -> str | None:
    """Why ``dim`` cannot be played in ``sel``, or None if it can."""
    if dim not in toolbar_axes(info, sel):
        return f"{DIM_LABELS.get(dim, dim)} is an axis of the image"
    lo, hi = sel.range(info, dim)
    if hi <= lo:
        return f"Only one {DIM_NOUNS[dim]}: nothing to play"
    if dim == "tof" and sel.tof_mode is not TofMode.BIN:
        how = sel.tof_mode.name.capitalize()
        return f"The image shows the {how} over all TOF bins: choose Bin to play through the TOF bins"
    return None


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
    axis_rows: Observed[tuple[AxisRow, ...]] = Observed(())   # the slice toolbar's rows, in order
    slice_mode: Observed[SliceMode] = Observed(SliceMode.SINOGRAM)
    tof_mode: Observed[TofMode] = Observed(TofMode.BIN)
    tof_available: Observed[bool] = Observed(False)
    tof_range: Observed[tuple[int, int] | None] = Observed(None)   # (first, last) TOF bin; None for non-TOF data
    can_play: Observed[bool] = Observed(False)       # Space (``toggle_play``) can play the axis played last
    playing: Observed[bool] = Observed(False)
    play_axis: Observed[str | None] = Observed(None)   # the axis playing; only one plays at a time
    play_mode: Observed[PlayMode] = Observed(PlayMode.LOOP)
    space_hint: Observed[str] = Observed("")          # what Space does now, e.g. "Space plays TOF bin"
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
    readout: Observed[tuple[tuple[str, str], ...]] = Observed(())   # (label, value) of the bin under the cursor
    readout_corner: Observed[Corner] = Observed(DEFAULT_CORNER)     # where the readout floats over the image
    tof_profile: Observed[TofProfile | None] = Observed(None)
    show_line_profile: Observed[bool] = Observed(True)
    line_mode: Observed[LineMode] = Observed(LineMode.ROW)    # the default reads along tangential (sinogram, viewgram)
    line_axis_names: Observed[tuple[str, str]] = Observed(("", ""))   # what ROW and COLUMN read, e.g. "along tangential"
    free_line: Observed[FreeLine | None] = Observed(None)      # the FREE line on the image; None in other modes
    show_tof_overlay: Observed[bool] = Observed(False)         # one faint line-profile curve per TOF bin
    line_profile: Observed[LineProfile | None] = Observed(None)
    frozen_at: Observed[tuple[float, float] | None] = Observed(None)   # where the frozen LOR is on the image
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
        self._frozen: Lor | None = None           # the LOR the profiles keep while frozen (a click)
        self._free_line_axes: tuple[str, str] | None = None   # the image axes the free line was drawn on
        self._last_play_axis: str | None = None   # the axis whose play button was pressed last
        self._play_direction = 1                  # +1 or -1; turns round at the ends in BOUNCE mode

    # ---- read access for tests and views --------------------------------------------
    @property
    def selection(self) -> Selection | None:
        return self._selection

    @property
    def dataset(self) -> ProjDataset | None:
        return self._dataset

    def dimension(self, name: str) -> AxisRow:
        """The toolbar row of axis ``name``; KeyError if it has none (an axis of the image, or no TOF)."""
        for row in self.axis_rows:
            if row.name == name:
                return row
        raise KeyError(name)

    @property
    def play_target(self) -> str | None:
        """The axis Space plays: the one played last while it still has a toolbar row; otherwise TOF for
        TOF data, else the fixed axis of the image type. None before data is loaded."""
        current = self._current()
        if current is None:
            return None
        dataset, sel = current
        axes = toolbar_axes(dataset.info, sel)
        if self._last_play_axis in axes:
            return self._last_play_axis
        return "tof" if "tof" in axes else sel.active_dimension

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
        self._set_play_axis(None)
        self._last_play_axis = None
        self.title = dataset.info.name
        self.summary = formatting.dataset_summary(dataset.info)
        self.tof_available = dataset.info.is_tof
        self.tof_range = (dataset.info.min_tof, dataset.info.max_tof) if dataset.info.is_tof else None
        self.tof_profile = None
        self.pixel_text = ""
        self.readout = ()
        self.readout_corner = DEFAULT_CORNER
        self._cursor = None
        self._frozen = None
        self._free_line_axes = None
        self.free_line = None
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
        """Play the axis Space plays (``play_target``), or pause whatever plays."""
        if not playing:
            self._set_play_axis(None)
        elif (target := self.play_target) is not None:
            self._start_playing(target)

    @_command
    def toggle_play(self) -> None:
        """Space: pause, or play the axis played last."""
        self.set_playing(not self.playing)

    @_command
    def toggle_play_axis(self, dim: str) -> None:
        """A row's play button: pause ``dim`` if it plays, otherwise play it instead of any other axis."""
        if self.play_axis == dim:
            self._set_play_axis(None)
        else:
            self._start_playing(dim)

    @_command
    def set_play_mode(self, mode: PlayMode) -> None:
        """LOOP wraps round at the ends of the axis, BOUNCE turns round."""
        self.play_mode = PlayMode(mode)

    @_command
    def set_show_tof_profile(self, shown: bool) -> None:
        """Show or hide the TOF profile plot (it is never shown for non-TOF data)."""
        self.show_tof_profile = bool(shown)

    @_command
    def set_show_line_profile(self, shown: bool) -> None:
        """Show or hide the line profile plot."""
        self.show_line_profile = bool(shown)

    @_command
    def set_line_mode(self, mode: LineMode) -> None:
        """ROW or COLUMN through the cursor (or the frozen LOR), or FREE along a line drawn on the image."""
        self.line_mode = LineMode(mode)
        if self._ready():
            self._update_free_line()
            self._update_line_profile()

    @_command
    def set_free_line(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """The user moved the free line (axis coordinates of the image)."""
        line = (float(x0), float(y0), float(x1), float(y1))
        if self.line_mode is not LineMode.FREE or not all(np.isfinite(line)) or not self._ready():
            return
        self.free_line = line
        self._update_line_profile()

    @_command
    def set_show_tof_overlay(self, shown: bool) -> None:
        """Add one faint curve per TOF bin to the line profile (TOF data only)."""
        self.show_tof_overlay = bool(shown)
        if self._ready():
            self._update_line_profile()

    @_command
    def click_at(self, x: float, y: float) -> None:
        """A click on the image: freeze the profiles at the LOR there, or release them if they are frozen."""
        if self._frozen is not None:
            self.release_freeze()
        elif self._slice is not None and self._ready():
            row, col = self._slice.pixel_from_axes(x, y)
            if self._slice.value_at(row, col) is not None:
                self._freeze(lor_at(self._loaded()[1], self._slice, row, col))

    @_command
    def toggle_freeze(self) -> None:
        """The keyboard's click: release, or freeze at the cursor (the centre of the image without one)."""
        if self._frozen is not None:
            self.release_freeze()
        elif (im := self.image) is not None:
            x, y = self._cursor if self._cursor is not None else (im.x0 + im.width / 2, im.y0 + im.height / 2)
            self.click_at(x, y)

    @_command
    def release_freeze(self) -> None:
        """Esc: the profiles follow the cursor again."""
        if self._frozen is None:
            return
        self._frozen = None
        self.frozen_at = None
        self._on_status("Profiles follow the cursor")
        if self._ready():
            self._update_profiles()

    @_command
    def set_fps(self, fps: int) -> None:
        self.fps = int(min(max(fps, MIN_FPS), MAX_FPS))

    @_command
    def tick(self) -> None:
        """One playback step; the view calls this from its timer. Ignored unless ``playing``,
        so a stale timer event after pause/error/collapse does nothing."""
        current = self._current()
        dim = self.play_axis
        if current is None or dim is None:
            return
        dataset, sel = current
        info = dataset.info
        if play_blocker(info, sel, dim) is not None:
            self._set_play_axis(None)
            return
        lo, hi = sel.range(info, dim)
        value, direction = next_play_value(sel.get(dim), lo, hi, self._play_direction, self.play_mode)
        if self._show(sel.with_value(info, dim, value)):
            self._play_direction = direction

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
        if (im := self.image) is not None:     # move the readout out of the cursor's way
            self.readout_corner = readout_corner(self.readout_corner, (x - im.x0) / im.width, (y - im.y0) / im.height)
        self._hover(x, y)

    @_command
    def hover_leave(self) -> None:
        self._cursor = None
        self.pixel_text = ""
        self.readout = ()

    def _hover(self, x: float, y: float) -> None:
        image, (dataset, sel) = self._slice, self._loaded()
        assert image is not None, "a slice is shown whenever data is loaded"
        row, col = image.pixel_from_axes(x, y)
        value = image.value_at(row, col)
        if value is None:
            self.pixel_text = ""
            self.readout = ()
            return
        self.pixel_text = formatting.format_pixel(image, row, col, value)
        self.readout = formatting.format_readout(dataset.info, sel, image, row, col, value)
        if (row, col) != self._last_pixel:
            self._last_pixel = (row, col)
            if self._frozen is None:          # frozen profiles keep their LOR while the cursor moves
                self._update_profiles()

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
            self._set_play_axis(None)    # never keep playing into a stream of identical errors
            self._report_error(f"Could not read the slice: {exc}")
            self._mark_changed("axis_rows", "slice_mode", "tof_mode", "level_mode", "log_display")  # snap back
            return False
        self._commit(dataset, selection, rendered)
        return True

    def _commit(self, dataset: ProjDataset, sel: Selection, rendered: "_Rendered") -> None:
        """Make ``dataset``/``sel`` current and publish everything derived from them (cannot fail)."""
        self._dataset, self._selection = dataset, sel
        info = dataset.info
        self.slice_mode = sel.slice_mode
        self.tof_mode = sel.tof_mode
        self.tof_marker = sel.tof if info.is_tof and sel.tof_mode is TofMode.BIN else None
        if self.play_axis is not None and play_blocker(info, sel, self.play_axis) is not None:
            self._set_play_axis(None)     # e.g. TOF collapsed, or the playing axis is now an image axis
        self._refresh_rows()
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
        self.line_axis_names = line_axis_names(image)
        self._update_free_line()
        self.frozen_at = image_position(image, self._frozen) if self._frozen is not None else None
        # the LOR under a resting cursor changes with the selection: recompute readout and profiles
        self._last_pixel = None
        if self._cursor is not None:
            self._hover(*self._cursor)
        if self._last_pixel is None:          # no cursor on the image, or frozen: not updated by _hover
            self._update_profiles()

    def _set_play_axis(self, dim: str | None) -> None:
        self.play_axis = dim
        self.playing = dim is not None
        if self._current() is not None:
            self._refresh_rows()          # each row shows whether it plays

    def _start_playing(self, dim: str) -> None:
        """Play ``dim`` (instead of any other axis) if it can be played; remember it for Space."""
        current = self._current()
        if current is None or play_blocker(current[0].info, current[1], dim) is not None:
            return
        self._last_play_axis = dim
        self._play_direction = 1
        self._set_play_axis(dim)

    def _refresh_rows(self) -> None:
        dataset, sel = self._loaded()
        info = dataset.info
        rows: list[AxisRow] = []
        for dim in toolbar_axes(info, sel):
            lo, hi = sel.range(info, dim)
            blocker = play_blocker(info, sel, dim)
            enabled = hi > lo and (dim != "tof" or sel.tof_mode is TofMode.BIN)
            tip = blocker if blocker is not None else f"Play through {DIM_NOUNS[dim]} {lo} to {hi}"
            rows.append(AxisRow(dim, DIM_LABELS[dim], lo, hi, sel.get(dim), enabled, blocker is None, tip,
                                self.play_axis == dim))
        self.axis_rows = tuple(rows)
        target = self.play_target
        self.can_play = target is not None and play_blocker(info, sel, target) is None
        if self.play_axis is not None:
            self.space_hint = f"Space pauses the {DIM_NOUNS[self.play_axis]}"
        elif target is not None:
            self.space_hint = f"Space plays the {DIM_NOUNS[target]}"

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

    def _probe(self) -> Lor | None:
        """The LOR the profiles read: the frozen one, else the one under the cursor (None if off the image)."""
        if self._frozen is not None:
            return self._frozen
        image, (_, sel) = self._slice, self._loaded()
        if image is None or self._cursor is None:
            return None
        row, col = image.pixel_from_axes(*self._cursor)
        return lor_at(sel, image, row, col) if image.value_at(row, col) is not None else None

    def _update_profiles(self) -> None:
        dataset, sel = self._loaded()
        lor = self._probe()
        if not dataset.info.is_tof or lor is None:
            self.tof_profile = None
        else:
            try:
                self.tof_profile = tof_profile(dataset, sel, lor)
            except Exception as exc:  # noqa: BLE001
                self._report_error(f"TOF profile unavailable: {exc}")
        self._update_line_profile(lor)

    def _update_line_profile(self, lor: Lor | None = None) -> None:
        dataset, sel = self._loaded()
        image = self._slice
        assert image is not None, "a slice is shown whenever data is loaded"
        try:
            self.line_profile = line_profile_for(dataset, sel, image, self.line_mode, lor or self._probe(),
                                                 self.free_line, self.show_tof_overlay)
        except Exception as exc:  # noqa: BLE001
            self.line_profile = None
            self._report_error(f"Line profile unavailable: {exc}")

    def _update_free_line(self) -> None:
        """A free line exists in FREE mode only; it starts across the image, and again when the image
        axes change (a line drawn on a sinogram means nothing on a viewgram)."""
        image = self._slice
        if self.line_mode is not LineMode.FREE or image is None:
            self.free_line = None
            self._free_line_axes = None
            return
        axes = (image.row_axis, image.col_axis)
        if self.free_line is None or self._free_line_axes != axes:
            self.free_line = default_free_line(image)
            self._free_line_axes = axes

    def _freeze(self, lor: Lor) -> None:
        image = self._slice
        assert image is not None, "a slice is shown whenever data is loaded"
        self._frozen = lor
        self.frozen_at = image_position(image, lor)
        self._on_status("Profiles frozen at segment {segment}, view {view}, axial {axial}, tangential {tangential}"
                        " (click again or press Esc to release)".format(**lor))
        self._update_profiles()
