# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""VIEWMODEL layer: the window-level state and commands, with no widget code.

The window owns what is not about one data set: opening files and the demo, the window title, the
status line and the error banner. Everything about the data set on screen lives in its projection
data pane (``ProjectionPaneViewModel``), reached as ``pane``. The data source comes from an injected
``source_factory``, so this never imports Qt, pyqtgraph or STIR.
"""
from __future__ import annotations

import contextlib
import functools
import os
from typing import Callable, Concatenate, ParamSpec, TypeVar

from ..model import ProjDataset, ProjDataSource
from . import formatting
from .observable import Observed, ObservableObject
from .pane_viewmodel import ProjectionPaneViewModel

DEFAULT_STATUS = "Open a file, or use File > Demo data"
DEFAULT_TITLE = "STIR projection data viewer"
NO_STIR_PROBE = "STIR status not checked in this configuration"
MAX_RECENT_FILES = 8

# what ``load`` accepts: a path, a ``stir.ProjData`` or a ``ProjDataSource``; only the factory looks inside
SourceFactory = Callable[[object], ProjDataSource]
# () -> (STIR can be used, one line saying where it is or why not); the composition root supplies it
StirProbe = Callable[[], tuple[bool, str]]

_P = ParamSpec("_P")
_R = TypeVar("_R")


def clean_path(text: str) -> str:
    """Normalise a typed or pasted path: strip whitespace and one pair of surrounding quotes, expand ``~``."""
    text = (text or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return os.path.expanduser(text) if text else ""


def _command(fn: Callable[Concatenate[ViewerViewModel, _P], _R]) -> Callable[Concatenate[ViewerViewModel, _P], _R]:
    """Run a window command as one transaction of the window and its pane: subscribers of each are
    notified once at the end."""
    @functools.wraps(fn)
    def wrapper(self: ViewerViewModel, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        with contextlib.ExitStack() as stack:
            stack.enter_context(self.transaction())
            stack.enter_context(self.pane.transaction())
            return fn(self, *args, **kwargs)
    return wrapper


class ViewerViewModel(ObservableObject):
    # ---- observable state (read-only for the view) --------------------------------
    loaded: Observed[bool] = Observed(False)
    window_title: Observed[str] = Observed(DEFAULT_TITLE)
    source_label: Observed[str] = Observed("")       # name of the loaded data set (file name for files)
    source_path: Observed[str] = Observed("")        # path of the loaded file, "" for in-memory or demo data
    status: Observed[str] = Observed(DEFAULT_STATUS)
    error: Observed[str | None] = Observed(None)     # last error message; re-notified on every failure
    data_summary: Observed[str] = Observed(formatting.data_summary(None))   # where the data comes from, its format
    recent_files: Observed[tuple[str, ...]] = Observed(())   # files loaded in this session, most recent first
    stir_available: Observed[bool] = Observed(False)
    stir_status: Observed[str] = Observed(NO_STIR_PROBE)

    def __init__(self, source_factory: SourceFactory, demo_factory: Callable[[], ProjDataSource] | None = None,
                 stir_probe: StirProbe | None = None) -> None:
        """``stir_probe`` reports whether STIR can be used and where it is (see ``refresh_stir_status``)."""
        super().__init__()
        self._factory = source_factory
        self._demo_factory = demo_factory
        self._stir_probe = stir_probe
        self.pane = ProjectionPaneViewModel(on_status=self._set_status, on_error=self._report_error)
        self.refresh_stir_status()

    # ---- commands --------------------------------------------------------------------
    @_command
    def load(self, obj: object) -> bool:
        """Load a path, ``stir.ProjData`` or ``ProjDataSource`` through the injected factory into the pane.
        On failure the previous data stays, ``error`` is set and False is returned."""
        try:
            dataset = ProjDataset(self._factory(obj))
            was_locked = self.pane.show_dataset(dataset)
        except Exception as exc:  # noqa: BLE001 - any loader failure is reported, not raised
            self._report_error(f"Could not load projection data: {exc}")   # the pane stays as it was
            return False
        self.error = None
        self.loaded = True
        self.window_title = f"{DEFAULT_TITLE} - {dataset.info.name}"
        self.source_label = dataset.info.name
        self.source_path = os.fspath(obj) if isinstance(obj, (str, os.PathLike)) else ""
        self.data_summary = formatting.data_summary(dataset.info, self.source_path)
        if self.source_path:
            self._remember(self.source_path)
        self.status = f"Loaded {dataset.info.name}" + ("  (colour levels unlocked)" if was_locked else "")
        return True

    @_command
    def refresh_stir_status(self) -> None:
        """Ask the injected probe whether STIR can be used. Without a probe the status says so."""
        if self._stir_probe is None:
            self.stir_available, self.stir_status = False, NO_STIR_PROBE
            return
        try:
            self.stir_available, self.stir_status = self._stir_probe()
        except Exception as exc:  # noqa: BLE001 - a status line, never fatal
            self.stir_available, self.stir_status = False, f"Could not check for STIR: {exc}"

    @_command
    def load_path(self, text: str) -> bool:
        """Load a path typed or pasted by the user: surrounding whitespace and quotes (e.g. from Windows
        "Copy as path") are removed and ``~`` is expanded. Blank input does nothing."""
        path = clean_path(text)
        if not path:
            return False
        return self.load(path)

    @_command
    def load_demo(self) -> bool:
        """Load the injected demo data set (the view must not know where demo data comes from)."""
        if self._demo_factory is None:
            self._report_error("No demo data is available in this configuration")
            return False
        return self.load(self._demo_factory())

    @_command
    def clear_error(self) -> None:
        """The user dismissed the error banner."""
        self.error = None

    @_command
    def report_error(self, message: str) -> None:
        """Let the view report a failure it caused itself (e.g. a failed image export) through the same
        channel as every other error, so the banner state lives in one place."""
        self._report_error(message)

    # ---- internals ---------------------------------------------------------------------
    def _remember(self, path: str) -> None:
        """Put ``path`` first in ``recent_files``; the same file (also typed differently) is listed once."""
        def same(p: str) -> str:
            return os.path.normcase(os.path.abspath(p))
        key = same(path)
        self.recent_files = ((path,) + tuple(p for p in self.recent_files if same(p) != key))[:MAX_RECENT_FILES]

    def _set_status(self, message: str) -> None:
        self.status = message

    def _report_error(self, message: str) -> None:
        self.error = message
        self._mark_changed("error")      # notify even if the text repeats
        self.status = message
