# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Composition root: the one place that wires model, sources, STIR interface, view model and view."""
from __future__ import annotations

import sys
from typing import cast

from PySide6 import QtCore, QtGui, QtWidgets

from .sources import make_demo_source
from .sources.loader import make_source
from .view._compat import override
from .view.styling import apply_theme
from .view.theme import DEFAULT_PALETTE, PALETTES
from .view.window import ViewerWindow
from .viewmodel import ViewerViewModel


def build(stir_path: str | None = None, theme: str = DEFAULT_PALETTE.name) -> tuple[ViewerViewModel, ViewerWindow]:
    """Create the view model (with the real loader and demo data) and its window."""
    vm = ViewerViewModel(source_factory=lambda obj: make_source(obj, stir_path), demo_factory=make_demo_source)
    return vm, ViewerWindow(vm, PALETTES[theme])


class FileOpenHandler(QtCore.QObject):
    """Loads files that macOS hands to the running app (Dock-icon drop, Finder "Open With", double-click
    on a document). Qt delivers those as ``QFileOpenEvent`` on the application object, also for the
    document that launched the app, which arrives just after ``exec()`` starts.

    Several documents dropped at once arrive as one event each; only the last one is loaded, from a
    0 ms timer, so the viewer does not read every file in turn."""

    def __init__(self, vm: ViewerViewModel, window: QtWidgets.QWidget, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._vm, self._window = vm, window
        self._pending: str | None = None

    @override
    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt override
        # An application-wide filter sees every event of every object: get out cheaply unless this is
        # a file-open event for the application itself.
        if obj is not QtCore.QCoreApplication.instance() or event.type() != QtCore.QEvent.Type.FileOpen:
            return False
        file_event = cast(QtGui.QFileOpenEvent, event)    # what a FileOpen event is
        url = file_event.url()
        path = file_event.file() or (url.toLocalFile() if url.isLocalFile() else "")
        if path:
            if self._pending is None:
                QtCore.QTimer.singleShot(0, self._load_pending)
            self._pending = path
        else:
            self._vm.report_error(f"Cannot open {url.toDisplayString() or 'the document'}: "
                                  "only local files are supported")
            self._show_window()
        return True

    def _load_pending(self) -> None:
        path, self._pending = self._pending, None
        if path:
            self._vm.load(path)   # failures are shown in the window's error banner
            self._show_window()

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()


def install_file_open_handler(app: QtWidgets.QApplication, vm: ViewerViewModel,
                              window: QtWidgets.QWidget) -> FileOpenHandler:
    # parented to the application, so the handler lives exactly as long as the application does
    handler = FileOpenHandler(vm, window, parent=app)
    app.installEventFilter(handler)
    return handler


def launch(projdata: object = None, stir_path: str | None = None, demo: bool = False,
           theme: str = DEFAULT_PALETTE.name) -> int:
    """Open the viewer. ``projdata`` may be a path, a ``stir.ProjData`` or a ``ProjDataSource``.

    Blocks until the window is closed; returns the Qt exit code. A load failure is shown in the window.
    """
    # an existing instance is the GUI application of the caller (e.g. an IPython Qt event loop)
    app = cast(QtWidgets.QApplication, QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1]))
    if theme not in PALETTES:
        raise ValueError(f"unknown theme {theme!r}; choose from {sorted(PALETTES)}")
    apply_theme(app, PALETTES[theme])
    vm, window = build(stir_path, theme)
    if sys.platform == "darwin":   # only macOS sends QFileOpenEvent
        install_file_open_handler(app, vm, window)
    if demo:
        vm.load_demo()
    elif projdata is not None:
        vm.load(projdata)
    window.show()
    return app.exec()


launch_GUI = launch  # name of the entry point of the old PyQt5 tool (stir.projdata_visualisation.launch_GUI)
