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

import os
from typing import Callable, ParamSpec, TypeVar, cast

from PySide6 import QtCore, QtGui, QtWidgets

from ..model import DIMENSIONS
from ..viewmodel import (COLORMAP_OPTIONS, KEYBOARD_SHORTCUTS, PLAY_MODE_OPTIONS,
                         SLICE_MODE_OPTIONS, TOF_MODE_OPTIONS, BindingRegistry, ChoiceOptions, ViewerViewModel)
from . import components as ui
from .pane import ProjectionDataPane
from .rail import IconRail, is_rail_button
from .styling import apply_theme
from .theme import DARK, GAP, LIGHT, PALETTES, Palette

THEME_OPTIONS = ChoiceOptions.from_values(tuple(PALETTES), tuple(name.capitalize() for name in PALETTES))

_P = ParamSpec("_P")
_T = TypeVar("_T")


def _uses_key(widget: QtWidgets.QWidget, key: QtCore.Qt.Key) -> bool:
    """Does ``widget`` (the focused one) have its own meaning for ``key``?"""
    Key = QtCore.Qt.Key
    text_entry = (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)
    if key == Key.Key_Space:                # a focused rail button opens its flyout, like any push button
        return isinstance(widget, text_entry) or is_rail_button(widget)
    if key == Key.Key_Escape:              # closes the flyout or releases the profiles, wherever the focus is
        return False
    if key in (Key.Key_L, Key.Key_F):      # a letter: typed into text fields, type-ahead in combo boxes
        return isinstance(widget, (QtWidgets.QComboBox,) + text_entry)
    return isinstance(widget, (QtWidgets.QAbstractSlider, QtWidgets.QComboBox) + text_entry)


def _section(title: str) -> QtWidgets.QLabel:
    """A small heading inside a flyout."""
    label = QtWidgets.QLabel(title)
    label.setObjectName("Section")
    return label


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
        row.setContentsMargins(GAP, GAP, GAP, GAP)
        row.setSpacing(GAP)
        row.addWidget(self._build_rail())
        self.pages = QtWidgets.QStackedWidget()
        self.empty = ui.EmptyState("No projection data loaded",
                                   "Open an Interfile header (.hs), a .npy/.npz array, or try the synthetic TOF demo.")
        self.empty.add_action("Open file...", self._open_file, primary=True)
        self.empty.add_action("Load demo data", lambda: self._run(self.vm.load_demo))
        self.pages.addWidget(self.empty)
        self.pages.addWidget(self._build_viewer_page())
        main = QtWidgets.QVBoxLayout()
        main.setSpacing(GAP)
        self.banner = ui.Banner()          # outside the pages: visible even if the first load fails
        self.banner.dismissed.connect(lambda: self.vm.clear_error())
        main.addWidget(self.banner)
        main.addWidget(self.pages, 1)
        row.addLayout(main, 1)
        self.setCentralWidget(root)

    def _build_rail(self) -> IconRail:
        self.rail = IconRail()
        self._build_data_flyout(self.rail.add_flyout(
            "data", "Data", "Data", "Data: open a file, a recent file or the demo data; STIR status",
            peek=lambda: self.vm.data_summary))
        self._build_info_flyout(self.rail.add_flyout(
            "info", "Info", "Data set", "Data set: scanner, dimensions and all metadata",
            peek=lambda: self.vm.pane.summary if self.vm.loaded else "No data loaded"))
        self.display_card = self.rail.add_flyout(
            "display", "Display", "Display", "Display: colour map, log display and theme",
            peek=self._display_peek)
        self._build_display_flyout(self.display_card)
        self._build_settings_flyout(self.rail.add_flyout(
            "settings", "Settings", "Profiles and settings",
            "Profiles and settings: profile plots, animation speed and keyboard shortcuts",
            peek=self._settings_peek))
        # STIR may have been installed meanwhile: check again whenever the Data flyout opens (cheap: no import)
        self.rail.flyoutChanged.connect(self._on_flyout_changed)
        return self.rail

    def _display_peek(self) -> str:
        pane = self.vm.pane
        return (f"Colour map: {pane.colormap}\nLog display: {'on' if pane.log_display else 'off'}\n"
                f"Theme: {THEME_OPTIONS.label_of(self.palette_tokens.name)}")

    def _settings_peek(self) -> str:
        pane = self.vm.pane
        return (f"TOF profile: {'shown' if pane.show_tof_profile else 'hidden'}\n"
                f"Line profile: {'shown' if pane.show_line_profile else 'hidden'}\n"
                f"Animation: {pane.fps} fps, {PLAY_MODE_OPTIONS.label_of(pane.play_mode).lower()}")

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
        card.body.addWidget(_section("Recent files"))
        self.recent_list = QtWidgets.QVBoxLayout()           # one button per file, rebuilt when the list changes
        self.recent_list.setSpacing(2)
        self.recent_buttons: list[QtWidgets.QPushButton] = []
        self.no_recent_label = QtWidgets.QLabel("No files opened yet")
        self.no_recent_label.setObjectName("Muted")
        self.recent_list.addWidget(self.no_recent_label)
        card.body.addLayout(self.recent_list)
        card.body.addWidget(_section("STIR"))
        self.stir_state = QtWidgets.QLabel("")
        self.stir_state.setObjectName("StirState")
        card.body.addWidget(self.stir_state)
        self.stir_label = QtWidgets.QLabel("")
        self.stir_label.setWordWrap(True)
        self.stir_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        card.body.addWidget(self.stir_label)

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
        self.log_switch = QtWidgets.QCheckBox("log(1 + x) display")
        self.log_switch.toggled.connect(self._slot(lambda: self.vm.pane.set_log_display))
        self.theme_control = ui.SegmentedControl(THEME_OPTIONS)
        self.theme_control.setAccessibleName("Theme")
        self.theme_control.set_choice(self.palette_tokens.name)
        self.theme_control.choiceChanged.connect(self._on_theme_chosen)
        display.body.addWidget(ui.LabeledRow("Colour map", self.cmap_control))
        display.body.addWidget(self.log_switch)
        display.body.addWidget(ui.LabeledRow("Theme", self.theme_control))

    def _build_settings_flyout(self, card: ui.Card) -> None:
        card.body.addWidget(_section("Profile plots"))
        self.tof_profile_switch = QtWidgets.QCheckBox("TOF profile")
        self.tof_profile_switch.setToolTip("Show the TOF profile of the LOR under the cursor (TOF data only)")
        self.tof_profile_switch.toggled.connect(self._slot(lambda: self.vm.pane.set_show_tof_profile))
        card.body.addWidget(self.tof_profile_switch)
        self.line_profile_switch = QtWidgets.QCheckBox("Line profile")
        self.line_profile_switch.setToolTip("Show the line profile: the row or column through the cursor, or a free line")
        self.line_profile_switch.toggled.connect(self._slot(lambda: self.vm.pane.set_show_line_profile))
        card.body.addWidget(self.line_profile_switch)
        card.body.addWidget(_section("Animation"))
        self.fps_spin = QtWidgets.QSpinBox()
        self.fps_spin.setRange(1, 30)
        self.fps_spin.setSuffix(" fps")
        self.fps_spin.setAccessibleName("Animation speed")
        self.fps_spin.valueChanged.connect(self._slot(lambda: self.vm.pane.set_fps))
        card.body.addWidget(ui.LabeledRow("Speed", self.fps_spin))
        self.play_mode_control = ui.SegmentedControl(PLAY_MODE_OPTIONS)
        self.play_mode_control.setAccessibleName("At the end of an axis: loop round or bounce back")
        self.play_mode_control.setToolTip("At the end of the axis, Loop starts again from the other end; "
                                          "Bounce turns round and plays back")
        self.play_mode_control.choiceChanged.connect(self._slot(lambda: self.vm.pane.set_play_mode))
        card.body.addWidget(ui.LabeledRow("At the end", self.play_mode_control))
        card.body.addWidget(_section("Keyboard shortcuts"))
        self.shortcut_list = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(self.shortcut_list)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        for i, (keys, action) in enumerate(KEYBOARD_SHORTCUTS):
            key_label = QtWidgets.QLabel(keys)
            key_label.setObjectName("Key")
            action_label = QtWidgets.QLabel(action)
            action_label.setObjectName("Muted")
            action_label.setWordWrap(True)
            grid.addWidget(key_label, i, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            grid.addWidget(action_label, i, 1)
        grid.setColumnStretch(1, 1)
        card.body.addWidget(self.shortcut_list)

    def _build_viewer_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(GAP)
        self.pane = ProjectionDataPane(self.vm.pane, self.palette_tokens)
        # the colour level controls are the pane's, beside its colour bar
        self.level_control = self.pane.level_control
        self.level_edits = self.pane.level_edits
        self.global_button = self.pane.global_button
        col.addWidget(self.pane, 1)
        col.addWidget(self._build_toolbar())
        return page

    def _build_toolbar(self) -> QtWidgets.QWidget:
        """The slice toolbar under the image: the image type tabs on the left, and on the right one row
        per axis not shown in the image (which rows, and their state, come from ``vm.pane.axis_rows``)."""
        self.toolbar = ui.Card()
        self.toolbar.setAccessibleName("Slice toolbar")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(2 * GAP)
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)
        self.mode_control = ui.SegmentedControl(SLICE_MODE_OPTIONS)
        self.mode_control.setAccessibleName("Image type")
        self.mode_control.choiceChanged.connect(self._slot(lambda: self.vm.pane.set_slice_mode))
        self.mode_control.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum,    # never clip its labels
                                        QtWidgets.QSizePolicy.Policy.Preferred)
        left.addWidget(self.mode_control)
        self.space_hint = QtWidgets.QLabel("")
        self.space_hint.setObjectName("Muted")
        left.addWidget(self.space_hint)
        left.addStretch(1)
        row.addLayout(left)

        rows = QtWidgets.QVBoxLayout()
        rows.setSpacing(4)
        self.tof_mode_control = ui.SegmentedControl(TOF_MODE_OPTIONS)
        self.tof_mode_control.setAccessibleName("Time of flight: one bin, or the sum, mean or maximum over the bins")
        self.tof_mode_control.choiceChanged.connect(self._slot(lambda: self.vm.pane.set_tof_mode))
        self.tof_mode_control.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum,    # never clip its labels
                                            QtWidgets.QSizePolicy.Policy.Preferred)
        self.dim_controls: dict[str, ui.AxisRowControl] = {}
        for dim in DIMENSIONS:                  # shown in this order; _paint_rows hides the image's axes
            ctrl = ui.AxisRowControl(self.tof_mode_control if dim == "tof" else None)
            ctrl.userChanged.connect(self._axis_slot(dim, lambda: self.vm.pane.set_value))
            ctrl.stepRequested.connect(self._axis_slot(dim, lambda: self.vm.pane.step))
            ctrl.playClicked.connect(lambda d=dim: self._run(self.vm.pane.toggle_play_axis, d))
            ctrl.setVisible(False)
            self.dim_controls[dim] = ctrl
            rows.addWidget(ctrl)
        row.addLayout(rows, 1)
        self.toolbar.body.addLayout(row)
        return self.toolbar

    def _axis_slot(self, dim: str, command: Callable[[], Callable[[str, int], object]]) -> Callable[[int], None]:
        """A slot for a row's ``userChanged(value)`` or ``stepRequested(delta)``: ``command()(dim, n)``."""
        return lambda n: self._run(command(), dim, n)

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
            Key.Key_F: lambda: self._run(pane.toggle_freeze),
            Key.Key_Escape: self._on_escape,
        }
        self._shortcuts: dict[QtCore.Qt.Key, QtGui.QShortcut] = {}
        for key in self._shortcut_commands:
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.activated.connect(lambda k=key: self._on_shortcut(k))
            self._shortcuts[key] = sc

    def _on_escape(self) -> None:
        """Esc closes the open flyout (giving the focus back to its rail button); otherwise it releases
        frozen profiles."""
        if self.rail.open_flyout is not None:
            self.rail.open(None)
        else:
            self._run(self.vm.pane.release_freeze)

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
        # the View menu and the Display flyout both choose the theme; keep them in step
        was = self.act_light.blockSignals(True)
        self.act_light.setChecked(palette.name == LIGHT.name)
        self.act_light.blockSignals(was)
        self.theme_control.set_choice(palette.name)

    # ------------------------------------------------------------------ user input -> commands
    def _run(self, command: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs) -> None:
        with ui.wait_cursor():
            command(*args, **kwargs)

    def _slot(self, command: Callable[[], Callable[[_T], object]]) -> Callable[[_T], None]:
        """A slot for a one-argument signal: runs ``command()(value)`` like every other user command.
        ``command`` returns the view-model method, so it is looked up on every signal, not once."""
        return lambda value: self._run(command(), value)

    def _on_light_toggled(self, on: bool) -> None:
        self.set_palette(LIGHT if on else DARK)

    def _on_theme_chosen(self, name: str) -> None:
        self.set_palette(PALETTES[name])

    def _on_flyout_changed(self, key: str | None) -> None:
        if key == "data":
            self.vm.refresh_stir_status()

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
        b("recent_files", self._paint_recent_files)
        b("stir_status", lambda: self.stir_label.setText(self.vm.stir_status))
        b("stir_available", self._paint_stir_available)
        b(("data_summary", "loaded"), self.rail.refresh_peek)     # a peek on screen follows the data

        pane = self.vm.pane
        p = self.pane_bindings.bind
        p("tof_available", lambda: self.tof_profile_switch.setEnabled(pane.tof_available))
        p("show_tof_profile", lambda: ui.silently(
            self.tof_profile_switch, lambda: self.tof_profile_switch.setChecked(pane.show_tof_profile)))
        p("show_line_profile", lambda: ui.silently(
            self.line_profile_switch, lambda: self.line_profile_switch.setChecked(pane.show_line_profile)))
        p("axis_rows", self._paint_rows)
        p("slice_mode", lambda: self.mode_control.set_choice(pane.slice_mode))
        p("tof_mode", lambda: self.tof_mode_control.set_choice(pane.tof_mode))
        p(("space_hint", "can_play"), self._paint_space_hint)
        p("fps", self._paint_fps)
        p(("playing", "play_axis"), self._paint_playing)
        p("play_mode", lambda: self.play_mode_control.set_choice(pane.play_mode))
        p("colormap", lambda: self.cmap_control.set_choice(pane.colormap))
        p("log_display", lambda: ui.silently(self.log_switch, lambda: self.log_switch.setChecked(pane.log_display)))
        p("info_text", lambda: self.info_view.setPlainText(pane.info_text))
        p(("summary", "colormap", "log_display", "show_tof_profile", "show_line_profile", "fps", "play_mode"),
          self.rail.refresh_peek)

    def _show_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_VIEWER if self.vm.loaded else self.PAGE_EMPTY)

    def _enable_controls(self) -> None:
        for card in (self.toolbar, self.display_card):
            card.setEnabled(self.vm.loaded)

    def _paint_rows(self) -> None:
        rows = {row.name: row for row in self.vm.pane.axis_rows}
        for name, ctrl in self.dim_controls.items():
            row = rows.get(name)
            if row is not None:
                ctrl.show_row(row.label, row.lo, row.hi, row.value, row.enabled, row.can_play, row.play_tip,
                              row.playing)
            ctrl.setVisible(row is not None)

    def _paint_space_hint(self) -> None:
        self.space_hint.setText(self.vm.pane.space_hint)
        self.space_hint.setEnabled(self.vm.pane.can_play)

    def _paint_stir_available(self) -> None:
        available = self.vm.stir_available
        self.stir_state.setText("Available" if available else "Not available")
        self.stir_state.setProperty("tone", "ok" if available else "missing")
        self.stir_state.style().unpolish(self.stir_state)         # re-read the stylesheet for the new tone
        self.stir_state.style().polish(self.stir_state)

    def _paint_recent_files(self) -> None:
        for button in self.recent_buttons:
            self.recent_list.removeWidget(button)
            button.deleteLater()
        self.recent_buttons = []
        for path in self.vm.recent_files:
            button = QtWidgets.QPushButton(os.path.basename(path) or path)
            button.setProperty("variant", "ghost")
            button.setProperty("align", "left")
            button.setToolTip(path)
            button.setAccessibleName(f"Open recent file {path}")
            button.clicked.connect(lambda _checked=False, p=path: self._run(self.vm.load, p))
            self.recent_list.addWidget(button)
            self.recent_buttons.append(button)
        self.no_recent_label.setVisible(not self.recent_buttons)

    def _paint_fps(self) -> None:
        ui.silently(self.fps_spin, lambda: self.fps_spin.setValue(self.vm.pane.fps))
        if self._timer.isActive():
            self._timer.start(int(1000 / self.vm.pane.fps))

    def _paint_playing(self) -> None:
        """The timer; the rows' play buttons are drawn from ``axis_rows``."""
        if self.vm.pane.playing:
            self._timer.start(int(1000 / self.vm.pane.fps))
        else:
            self._timer.stop()
