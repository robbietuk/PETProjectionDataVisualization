# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""VIEW layer: the main window, bound to a ``ViewerViewModel``.

The window only arranges things: the icon rail with its flyouts on the left, the projection data
pane (``ProjectionDataPane``: image, colour bar, readout, profile plots) in the middle, and the slice
toolbar under it. The flyouts and the toolbar drive the pane's view model (``vm.pane``).

Rules of this file: widgets send user input to view-model commands, and redraw from view-model
properties when told they changed (declaratively, through a ``BindingRegistry``). No selection
logic, no data access, no formatting; colours come from the active ``Palette``.
"""
from __future__ import annotations

import contextlib
from typing import Callable, Generator, ParamSpec, TypeVar, cast

from PySide6 import QtCore, QtGui, QtWidgets

from ..viewmodel import (COLORMAP_OPTIONS, LEVEL_MODE_OPTIONS, SLICE_MODE_OPTIONS, TOF_MODE_OPTIONS,
                         BindingRegistry, ViewerViewModel)
from . import components as ui
from .pane import ProjectionDataPane
from .rail import IconRail
from .styling import apply_theme
from .theme import DARK, LIGHT, Palette

LEVEL_LOCK_TIP = ("Colour levels (L): Adaptive recomputes Min/Max for every slice; Locked keeps Min/Max and the "
                  "colour bar constant while you change view, axial position, segment, TOF bin, slice mode or "
                  "log display. Typing a level or dragging the histogram locks at the new values.")
DIMENSION_WIDTH = 210         # minimum width of one slider + spin box in the toolbar

_P = ParamSpec("_P")
_T = TypeVar("_T")


def _uses_key(widget: QtWidgets.QWidget, key: QtCore.Qt.Key) -> bool:
    """Does ``widget`` (the focused one) have its own meaning for ``key``?"""
    Key = QtCore.Qt.Key
    text_entry = (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)
    if key == Key.Key_Space:
        return isinstance(widget, text_entry)
    if key == Key.Key_L:                   # a letter: typed into text fields, type-ahead in combo boxes
        return isinstance(widget, (QtWidgets.QComboBox,) + text_entry)
    return isinstance(widget, (QtWidgets.QAbstractSlider, QtWidgets.QComboBox) + text_entry)


@contextlib.contextmanager
def _wait_cursor() -> Generator[None, None, None]:
    QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
    try:
        yield
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


class ViewerWindow(QtWidgets.QMainWindow):
    PAGE_EMPTY, PAGE_VIEWER = 0, 1

    def __init__(self, vm: ViewerViewModel, palette: Palette = DARK) -> None:
        super().__init__()
        self.vm = vm
        self.palette_tokens = palette
        self.resize(1320, 840)
        self._build_menu()
        self._build_layout()
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._install_shortcuts()
        self.bindings = BindingRegistry(vm)                 # window state
        self.pane_bindings = BindingRegistry(vm.pane)       # the rail's and toolbar's controls of the pane
        self._declare_bindings()
        self.bindings.start()
        self.pane_bindings.start()

    # ------------------------------------------------------------------ construction
    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")
        act_open = menu.addAction("&Open...")
        act_open.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_file)
        act_demo = menu.addAction("&Demo data (synthetic TOF)")
        act_demo.triggered.connect(lambda: self._run(self.vm.load_demo))
        self.act_save = menu.addAction("&Save image...")
        self.act_save.triggered.connect(self._save_image)
        menu.addSeparator()
        act_quit = menu.addAction("&Quit")
        act_quit.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        view_menu = self.menuBar().addMenu("&View")
        self.act_light = view_menu.addAction("&Light theme")
        self.act_light.setCheckable(True)
        self.act_light.setChecked(self.palette_tokens.name == "light")
        self.act_light.toggled.connect(self._on_light_toggled)

    def _build_layout(self) -> None:
        root = QtWidgets.QWidget()
        root.setObjectName("Root")
        row = QtWidgets.QHBoxLayout(root)
        row.setContentsMargins(12, 6, 12, 12)
        row.setSpacing(12)
        row.addWidget(self._build_rail())
        self.pages = QtWidgets.QStackedWidget()
        self.empty = ui.EmptyState("No projection data loaded",
                                   "Open an Interfile header (.hs), a .npy/.npz array, or try the synthetic TOF demo.")
        self.empty.add_action("Open file...", self._open_file, primary=True)
        self.empty.add_action("Load demo data", lambda: self._run(self.vm.load_demo))
        self.pages.addWidget(self.empty)
        self.pages.addWidget(self._build_viewer_page())
        main = QtWidgets.QVBoxLayout()
        main.setSpacing(12)
        self.banner = ui.Banner()          # outside the pages: visible even if the first load fails
        self.banner.dismissed.connect(lambda: self.vm.clear_error())
        main.addWidget(self.banner)
        main.addWidget(self.pages, 1)
        row.addLayout(main, 1)
        self.setCentralWidget(root)

    def _build_rail(self) -> IconRail:
        self.rail = IconRail()
        self._build_data_flyout(self.rail.add_flyout(
            "data", "Data", "Data", "Data: open a file or the demo data"))
        self._build_info_flyout(self.rail.add_flyout(
            "info", "Info", "Data set", "Data set: scanner, dimensions and metadata"))
        self.display_card = self.rail.add_flyout(
            "display", "Display", "Display", "Display: colour map, colour levels and log display")
        self._build_display_flyout(self.display_card)
        self._build_settings_flyout(self.rail.add_flyout(
            "settings", "Settings", "Profiles and settings", "Profiles and settings: animation speed"))
        return self.rail

    def _build_data_flyout(self, card: ui.Card) -> None:
        self.loaded_label = QtWidgets.QLabel("")          # name of the loaded data set
        self.loaded_label.setObjectName("Muted")
        self.loaded_label.setWordWrap(True)
        card.body.addWidget(self.loaded_label)
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("path to .hs / .npy / .npz")
        self.path_edit.returnPressed.connect(self._load_typed_path)
        buttons = QtWidgets.QHBoxLayout()
        browse = QtWidgets.QPushButton("Browse...")
        browse.clicked.connect(self._open_file)
        load = QtWidgets.QPushButton("Load")
        load.setProperty("variant", "primary")
        load.clicked.connect(self._load_typed_path)
        buttons.addWidget(browse)
        buttons.addWidget(load)
        demo = QtWidgets.QPushButton("Load demo data")
        demo.clicked.connect(lambda: self._run(self.vm.load_demo))
        card.body.addWidget(self.path_edit)
        card.body.addLayout(buttons)
        card.body.addWidget(demo)

    def _build_info_flyout(self, card: ui.Card) -> None:
        self.info_view = QtWidgets.QPlainTextEdit()
        self.info_view.setReadOnly(True)
        self.info_view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.info_view.setObjectName("Mono")             # monospace comes from the stylesheet
        self.info_view.setMinimumHeight(360)
        card.body.addWidget(self.info_view)

    def _build_display_flyout(self, display: ui.Card) -> None:
        self.cmap_control = ui.ChoiceCombo(COLORMAP_OPTIONS)
        self.cmap_control.choiceChanged.connect(self._slot(lambda: self.vm.pane.set_colormap))
        self.level_control = ui.SegmentedControl(LEVEL_MODE_OPTIONS)      # Adaptive | Locked
        self.level_control.setAccessibleName("Colour levels: adaptive or locked")
        self.level_control.setToolTip(LEVEL_LOCK_TIP)
        self.level_control.choiceChanged.connect(self._slot(lambda: self.vm.pane.set_level_mode))
        self.global_button = QtWidgets.QPushButton("Lock to global range")
        self.global_button.setAccessibleName("Lock colour levels to the global range of the data set")
        self.global_button.setToolTip("Lock Min/Max at the range of the whole data set in the current TOF mode "
                                      "(reads every segment once).")
        self.global_button.clicked.connect(lambda: self._run(self.vm.pane.lock_global_range))
        display.body.addWidget(ui.LabeledRow("Colour map", self.cmap_control))
        display.body.addWidget(self.level_control)          # full width, like the other mode controls
        display.body.addWidget(self.global_button)
        self.level_edits: dict[str, ui.NumberEdit] = {}
        for key, label in (("low", "Min level"), ("high", "Max level")):
            edit = ui.NumberEdit()                   # any magnitude, e.g. 1e-8; commits on Enter/focus-out
            edit.setFixedWidth(130)
            edit.valueEdited.connect(self._level_bound_slot(key))
            self.level_edits[key] = edit
            display.body.addWidget(ui.LabeledRow(label, edit))
        self.log_switch = QtWidgets.QCheckBox("log(1 + x) display")
        self.log_switch.toggled.connect(self._slot(lambda: self.vm.pane.set_log_display))
        display.body.addWidget(self.log_switch)

    def _build_settings_flyout(self, card: ui.Card) -> None:
        self.fps_spin = QtWidgets.QSpinBox()
        self.fps_spin.setRange(1, 30)
        self.fps_spin.setSuffix(" fps")
        self.fps_spin.setAccessibleName("Animation speed")
        self.fps_spin.valueChanged.connect(self._slot(lambda: self.vm.pane.set_fps))
        card.body.addWidget(ui.LabeledRow("Animation speed", self.fps_spin))

    def _build_viewer_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        self.pane = ProjectionDataPane(self.vm.pane, self.palette_tokens)
        col.addWidget(self.pane, 1)
        col.addWidget(self._build_toolbar())
        return page

    def _build_toolbar(self) -> QtWidgets.QWidget:
        """The slice toolbar under the image: the image type, the indices, and time of flight."""
        self.toolbar = QtWidgets.QWidget()
        self.toolbar.setObjectName("SliceToolbar")
        row = QtWidgets.QHBoxLayout(self.toolbar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        self.slice_card = ui.Card("Slice")
        slice_row = QtWidgets.QHBoxLayout()
        slice_row.setSpacing(16)
        self.mode_control = ui.SegmentedControl(SLICE_MODE_OPTIONS)
        self.mode_control.choiceChanged.connect(self._slot(lambda: self.vm.pane.set_slice_mode))
        self.mode_control.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum,    # never clip its labels
                                        QtWidgets.QSizePolicy.Policy.Preferred)
        slice_row.addWidget(self.mode_control, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        self.dim_controls: dict[str, ui.DimensionControl] = {}
        for i, dim in enumerate(("segment", "axial", "view", "tangential")):
            self.dim_controls[dim] = ctrl = self._dimension_control(dim)
            grid.addWidget(ctrl, i // 2, i % 2)
        slice_row.addLayout(grid, 1)
        self.slice_card.body.addLayout(slice_row)
        row.addWidget(self.slice_card, 2)

        self.tof_box = ui.Card("Time of flight")
        self.tof_mode_control = ui.SegmentedControl(TOF_MODE_OPTIONS)
        self.tof_mode_control.choiceChanged.connect(self._slot(lambda: self.vm.pane.set_tof_mode))
        self.tof_box.body.addWidget(self.tof_mode_control)
        self.dim_controls["tof"] = tof_ctrl = self._dimension_control("tof")
        tof_row = QtWidgets.QHBoxLayout()
        tof_row.addWidget(tof_ctrl, 1)
        self.play_button = QtWidgets.QPushButton("Play  (Space)")
        self.play_button.setCheckable(True)
        self.play_button.toggled.connect(self._slot(lambda: self.vm.pane.set_playing))
        tof_row.addWidget(self.play_button, 0, QtCore.Qt.AlignmentFlag.AlignBottom)
        self.tof_box.body.addLayout(tof_row)
        row.addWidget(self.tof_box, 1)
        return self.toolbar

    def _dimension_control(self, dim: str) -> ui.DimensionControl:
        ctrl = ui.DimensionControl()
        ctrl.setMinimumWidth(DIMENSION_WIDTH)

        def on_change(value: int) -> None:
            self._run(self.vm.pane.set_value, dim, value)
        ctrl.userChanged.connect(on_change)
        return ctrl

    def _install_shortcuts(self) -> None:
        """Window-wide keys. A QShortcut pre-empts the focused widget, so when the focus is on a widget that
        uses the key itself (a slider or spin box for arrows/PgUp/PgDn, a text field for Space), the key
        is passed on to that widget instead of running the shortcut: Right on a focused segment slider
        moves the segment, not the axial position."""
        Key = QtCore.Qt.Key
        pane = self.vm.pane
        self._shortcut_commands: dict[QtCore.Qt.Key, Callable[[], None]] = {
            Key.Key_Space: lambda: self._run(pane.toggle_play),
            Key.Key_Left: lambda: self._run(pane.step_active, -1),
            Key.Key_Right: lambda: self._run(pane.step_active, +1),
            Key.Key_PageUp: lambda: self._run(pane.step, "segment", +1),
            Key.Key_PageDown: lambda: self._run(pane.step, "segment", -1),
            Key.Key_L: lambda: self._run(pane.toggle_level_lock),
        }
        self._shortcuts: dict[QtCore.Qt.Key, QtGui.QShortcut] = {}
        for key in self._shortcut_commands:
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.activated.connect(lambda k=key: self._on_shortcut(k))
            self._shortcuts[key] = sc

    def _on_shortcut(self, key: QtCore.Qt.Key) -> None:
        focus = self.focusWidget()       # this window's focus child (also right when the window is not active)
        if focus is not None and _uses_key(focus, key):
            sc = self._shortcuts[key]
            sc.setEnabled(False)          # or the re-sent key would trigger this shortcut again
            code = int(getattr(key, "value", key))
            text = chr(code).lower() if 0x20 <= code < 0x7F else ""    # Space, letters: what the key types
            try:
                for kind in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
                    QtWidgets.QApplication.sendEvent(
                        focus, QtGui.QKeyEvent(kind, key, QtCore.Qt.KeyboardModifier.NoModifier, text))
            finally:
                sc.setEnabled(True)
            return
        self._shortcut_commands[key]()

    # ------------------------------------------------------------------ theming
    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        # the window exists, so the GUI application does too
        apply_theme(cast(QtWidgets.QApplication, QtWidgets.QApplication.instance()), palette)
        self.pane.set_palette(palette)

    # ------------------------------------------------------------------ user input -> commands
    def _run(self, command: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs) -> None:
        with _wait_cursor():
            command(*args, **kwargs)

    def _slot(self, command: Callable[[], Callable[[_T], object]]) -> Callable[[_T], None]:
        """A slot for a one-argument signal: runs ``command()(value)`` like every other user command.
        ``command`` returns the view-model method, so it is looked up on every signal, not once."""
        return lambda value: self._run(command(), value)

    def _level_bound_slot(self, key: str) -> Callable[[float], None]:
        """A slot for one level box: ``key`` is ``low`` or ``high`` (the keyword of ``set_level_bounds``)."""
        return lambda value: self._run(self.vm.pane.set_level_bounds, **{key: value})

    def _on_light_toggled(self, on: bool) -> None:
        self.set_palette(LIGHT if on else DARK)

    def _open_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open projection data", "", "Projection data (*.hs *.npy *.npz);;All files (*)")
        if path:
            self._run(self.vm.load, path)

    def _load_typed_path(self) -> None:
        if self.path_edit.text().strip():
            self._run(self.vm.load_path, self.path_edit.text())

    def _save_image(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save image", "slice.png",
                                                        "PNG image (*.png);;All files (*)")
        if not path:
            return
        try:
            from pyqtgraph.exporters import ImageExporter
            ImageExporter(self.pane.plot).export(path)
        except Exception as exc:  # noqa: BLE001 - show it in the banner, don't crash the viewer
            self.vm.report_error(f"Could not save the image: {exc}")

    def _on_timer(self) -> None:
        self.vm.pane.tick()

    # ------------------------------------------------------------------ view-model -> widgets
    def _declare_bindings(self) -> None:
        b = self.bindings.bind
        b("window_title", lambda: self.setWindowTitle(self.vm.window_title))
        b("status", lambda: self.statusBar().showMessage(self.vm.status))
        b("source_path", lambda: self.path_edit.setText(self.vm.source_path))   # a real path or empty
        b("source_label", lambda: self.loaded_label.setText(self.vm.source_label))
        b("loaded", self._show_page)
        b("loaded", lambda: self.act_save.setEnabled(self.vm.loaded))
        b("loaded", self._enable_controls)
        b("error", lambda: self.banner.show_message(self.vm.error))

        pane = self.vm.pane
        p = self.pane_bindings.bind
        p("tof_available", lambda: self.tof_box.setVisible(pane.tof_available))
        p("dimensions", self._paint_dimensions)
        p("slice_mode", lambda: self.mode_control.set_choice(pane.slice_mode))
        p("tof_mode", lambda: self.tof_mode_control.set_choice(pane.tof_mode))
        p("can_play", lambda: self.play_button.setEnabled(pane.can_play))
        p("fps", self._paint_fps)
        p("playing", self._paint_playing)
        p("colormap", lambda: self.cmap_control.set_choice(pane.colormap))
        p("level_mode", lambda: self.level_control.set_choice(pane.level_mode))
        p("log_display", lambda: ui.silently(self.log_switch, lambda: self.log_switch.setChecked(pane.log_display)))
        p("levels", self._paint_level_edits)
        p("info_text", lambda: self.info_view.setPlainText(pane.info_text))

    def _show_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_VIEWER if self.vm.loaded else self.PAGE_EMPTY)

    def _enable_controls(self) -> None:
        for card in (self.slice_card, self.display_card):
            card.setEnabled(self.vm.loaded)

    def _paint_dimensions(self) -> None:
        for state in self.vm.pane.dimensions:
            self.dim_controls[state.name].show_state(state.label, state.lo, state.hi, state.value, state.enabled)

    def _paint_fps(self) -> None:
        ui.silently(self.fps_spin, lambda: self.fps_spin.setValue(self.vm.pane.fps))
        if self._timer.isActive():
            self._timer.start(int(1000 / self.vm.pane.fps))

    def _paint_playing(self) -> None:
        playing = self.vm.pane.playing
        ui.silently(self.play_button, lambda: self.play_button.setChecked(playing))
        self.play_button.setText("Pause  (Space)" if playing else "Play  (Space)")
        if playing:
            self._timer.start(int(1000 / self.vm.pane.fps))
        else:
            self._timer.stop()

    def _paint_level_edits(self) -> None:
        levels = self.vm.pane.levels
        if levels is None:
            return
        for key, value in zip(("low", "high"), levels):
            self.level_edits[key].set_value(value)
