# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Composition root: the one place that wires model, sources, STIR interface, view model and view."""
from __future__ import annotations

import sys
from typing import Any

from PySide6 import QtCore, QtWidgets

from .sources import make_demo_source
from .sources.loader import make_source
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
    document that launched the app, which arrives just after ``exec()`` starts."""

    def __init__(self, vm: ViewerViewModel, window: QtWidgets.QWidget, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self._vm, self._window = vm, window

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QtCore.QEvent.Type.FileOpen:
            path = event.file() or event.url().toLocalFile()
            if path:
                self._vm.load(path)   # failures are shown in the window's error banner
                self._window.show()
                self._window.raise_()
                self._window.activateWindow()
                return True
        return super().eventFilter(obj, event)


def install_file_open_handler(app: QtWidgets.QApplication, vm: ViewerViewModel,
                              window: QtWidgets.QWidget) -> FileOpenHandler:
    handler = FileOpenHandler(vm, window, parent=app)   # parented to the app so it lives as long as it
    app.installEventFilter(handler)
    return handler


def launch(projdata: Any = None, stir_path: str | None = None, demo: bool = False,
           theme: str = DEFAULT_PALETTE.name) -> int:
    """Open the viewer. ``projdata`` may be a path, a ``stir.ProjData`` or a ``ProjDataSource``.

    Blocks until the window is closed; returns the Qt exit code. A load failure is shown in the window.
    """
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    if theme not in PALETTES:
        raise ValueError(f"unknown theme {theme!r}; choose from {sorted(PALETTES)}")
    apply_theme(app, PALETTES[theme])
    vm, window = build(stir_path, theme)
    install_file_open_handler(app, vm, window)
    if demo:
        vm.load_demo()
    elif projdata is not None:
        vm.load(projdata)
    window.show()
    return app.exec()


launch_GUI = launch  # name of the entry point of the old PyQt5 tool (stir.projdata_visualisation.launch_GUI)
