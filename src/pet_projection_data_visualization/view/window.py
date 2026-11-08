# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""VIEW layer: the main window, built from ``components`` and bound to a ``ViewerViewModel``.

Rules of this file: widgets send user input to view-model commands, and redraw from view-model
properties when told they changed (declaratively, through a ``BindingRegistry``). No selection
logic, no data access, no formatting; colours come from the active ``Palette``.
"""
from __future__ import annotations

import contextlib
from typing import Callable, Generator, ParamSpec, TypeVar, cast

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from ..viewmodel import (COLORMAP_OPTIONS, LEVEL_MODE_OPTIONS, SLICE_MODE_OPTIONS, TOF_MODE_OPTIONS,
                         BindingRegistry, LevelMode, ViewerViewModel)
from . import components as ui
from .styling import apply_theme, style_graphics_widget, style_histogram, style_plot
from .theme import DARK, LIGHT, Palette

pg.setConfigOptions(imageAxisOrder="row-major", antialias=True)  # numpy rows -> screen rows

SIDEBAR_WIDTH = 340
LEVEL_LOCK_TIP = ("Colour levels (L): Adaptive recomputes Min/Max for every slice; Locked keeps Min/Max and the "
                  "colour bar constant while you change view, axial position, segment, TOF bin, slice mode or "
                  "log display. Typing a level or dragging the histogram locks at the new values.")

_P = ParamSpec("_P")
_T = TypeVar("_T")


def _colormap(name: str) -> pg.ColorMap:
    if name != "grey":
        try:
            return pg.colormap.get(name)
        except Exception:  # noqa: BLE001 - fall through to grey
            pass
    return pg.ColorMap([0.0, 1.0], [(0, 0, 0), (255, 255, 255)])


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
        self._geometry_key: tuple[object, ...] | None = None
        self._applying_levels = False
        self._levels_from_histogram = False     # set while a histogram drag is handed to the view model
        self._painted_levels: tuple[float, float] | None = None
        self._build_menu()
        self._build_layout()
        self._pixel_label = QtWidgets.QLabel("")
        self._pixel_label.setObjectName("PixelReadout")
        self.statusBar().addPermanentWidget(self._pixel_label)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._install_shortcuts()
        self._restyle_plots()
        self.bindings = BindingRegistry(vm)
        self._declare_bindings()
        self.bindings.start()

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
        row.addWidget(self._build_sidebar())
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

    def _build_sidebar(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(SIDEBAR_WIDTH)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QtWidgets.QWidget()
        content.setObjectName("Content")
        col = QtWidgets.QVBoxLayout(content)
        col.setContentsMargins(0, 0, 6, 0)
        col.setSpacing(12)

        source = ui.Card("Data")
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
        source.body.addWidget(self.path_edit)
        source.body.addLayout(buttons)
        col.addWidget(source)

        self.slice_card = ui.Card("Slice")
        self.mode_control = ui.SegmentedControl(SLICE_MODE_OPTIONS)
        self.mode_control.choiceChanged.connect(self._slot(lambda: self.vm.set_slice_mode))
        self.slice_card.body.addWidget(self.mode_control)
        self.dim_controls: dict[str, ui.DimensionControl] = {}
        for dim in ("segment", "axial", "view", "tangential"):
            self.dim_controls[dim] = self._dimension_control(dim, self.slice_card)
        col.addWidget(self.slice_card)

        self.tof_box = ui.Card("Time of flight")
        self.tof_mode_control = ui.SegmentedControl(TOF_MODE_OPTIONS)
        self.tof_mode_control.choiceChanged.connect(self._slot(lambda: self.vm.set_tof_mode))
        self.tof_box.body.addWidget(self.tof_mode_control)
        self.dim_controls["tof"] = self._dimension_control("tof", self.tof_box)
        play = QtWidgets.QHBoxLayout()
        self.play_button = QtWidgets.QPushButton("Play  (Space)")
        self.play_button.setCheckable(True)
        self.play_button.toggled.connect(self._slot(lambda: self.vm.set_playing))
        self.fps_spin = QtWidgets.QSpinBox()
        self.fps_spin.setRange(1, 30)
        self.fps_spin.setSuffix(" fps")
        self.fps_spin.valueChanged.connect(self._slot(lambda: self.vm.set_fps))
        play.addWidget(self.play_button, 1)
        play.addWidget(self.fps_spin)
        self.tof_box.body.addLayout(play)
        col.addWidget(self.tof_box)

        display = self.display_card = ui.Card("Display")
        self.cmap_control = ui.ChoiceCombo(COLORMAP_OPTIONS)
        self.cmap_control.choiceChanged.connect(self._slot(lambda: self.vm.set_colormap))
        self.level_control = ui.SegmentedControl(LEVEL_MODE_OPTIONS)      # Adaptive | Locked
        self.level_control.setAccessibleName("Colour levels: adaptive or locked")
        self.level_control.setToolTip(LEVEL_LOCK_TIP)
        self.level_control.choiceChanged.connect(self._slot(lambda: self.vm.set_level_mode))
        self.global_button = QtWidgets.QPushButton("Lock to global range")
        self.global_button.setAccessibleName("Lock colour levels to the global range of the data set")
        self.global_button.setToolTip("Lock Min/Max at the range of the whole data set in the current TOF mode "
                                      "(reads every segment once).")
        self.global_button.clicked.connect(lambda: self._run(self.vm.lock_global_range))
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
        self.log_switch.toggled.connect(self._slot(lambda: self.vm.set_log_display))
        display.body.addWidget(self.log_switch)
        col.addWidget(display)

        info = ui.Card("Data set")
        self.info_view = QtWidgets.QPlainTextEdit()
        self.info_view.setReadOnly(True)
        self.info_view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.info_view.setObjectName("Mono")             # monospace comes from the stylesheet
        self.info_view.setMinimumHeight(230)
        info.body.addWidget(self.info_view)
        col.addWidget(info)
        col.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _dimension_control(self, dim: str, card: ui.Card) -> ui.DimensionControl:
        ctrl = ui.DimensionControl()

        def on_change(value: int) -> None:
            self._run(self.vm.set_value, dim, value)
        ctrl.userChanged.connect(on_change)
        card.body.addWidget(ctrl)
        return ctrl

    def _build_viewer_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        header = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel("")
        self.title_label.setObjectName("Title")
        self.chips = ui.ChipRow()
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.chips)
        col.addLayout(header)

        image_card = ui.Card()
        self.glw = pg.GraphicsLayoutWidget()
        self.plot = self.glw.addPlot(row=0, col=0)
        self.plot.setAspectLocked(False)
        self.plot.invertY(True)          # like imshow: row 0 on top
        # Shown as a fixed image (axes and ticks kept): no wheel/drag zoom or pan, no context menu,
        # no auto-range button. The range is set to the image extent in _draw_image.
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.img = pg.ImageItem()
        self.plot.addItem(self.img)
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img)
        self.glw.addItem(self.hist, row=0, col=1)
        self.hist.sigLevelChangeFinished.connect(self._on_user_levels)
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        image_card.body.addWidget(self.glw)
        col.addWidget(image_card, 1)

        self.metrics = ui.MetricGrid(columns=6)
        col.addWidget(self.metrics)

        self.tof_dock = ui.Card("TOF profile of the LOR under the cursor")
        self.tof_plot = pg.PlotWidget()
        self.tof_plot.setLabel("bottom", "TOF bin")
        self.tof_plot.setLabel("left", "counts")
        self.tof_plot.setTitle("hover over the image")
        self.tof_plot.setMinimumHeight(150)
        self.tof_curve = self.tof_plot.plot([], [], symbol="o", symbolSize=7)
        self.tof_marker_line = pg.InfiniteLine(angle=90, movable=False)
        self.tof_plot.addItem(self.tof_marker_line)
        self.tof_dock.body.addWidget(self.tof_plot)
        self.tof_dock.setMaximumHeight(250)
        col.addWidget(self.tof_dock)
        return page

    def _install_shortcuts(self) -> None:
        """Window-wide keys. A QShortcut pre-empts the focused widget, so when the focus is on a widget that
        uses the key itself (a slider or spin box for arrows/PgUp/PgDn, a text field for Space), the key
        is passed on to that widget instead of running the shortcut: Right on a focused segment slider
        moves the segment, not the axial position."""
        Key = QtCore.Qt.Key
        self._shortcut_commands: dict[QtCore.Qt.Key, Callable[[], None]] = {
            Key.Key_Space: lambda: self._run(self.vm.toggle_play),
            Key.Key_Left: lambda: self._run(self.vm.step_active, -1),
            Key.Key_Right: lambda: self._run(self.vm.step_active, +1),
            Key.Key_PageUp: lambda: self._run(self.vm.step, "segment", +1),
            Key.Key_PageDown: lambda: self._run(self.vm.step, "segment", -1),
            Key.Key_L: lambda: self._run(self.vm.toggle_level_lock),
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
        self._restyle_plots()

    def _restyle_plots(self) -> None:
        p = self.palette_tokens
        style_graphics_widget(self.glw, p)
        style_plot(self.plot, p)
        style_histogram(self.hist, p)
        style_plot(self.tof_plot.getPlotItem(), p)
        self.tof_plot.setBackground(p.surface)
        self.tof_curve.setPen(pg.mkPen(p.curve, width=2))
        self.tof_curve.setSymbolBrush(p.curve)
        self.tof_curve.setSymbolPen(p.curve)
        self.tof_marker_line.setPen(pg.mkPen(p.marker, width=2))

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
        return lambda value: self._run(self.vm.set_level_bounds, **{key: value})

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
            ImageExporter(self.plot).export(path)
        except Exception as exc:  # noqa: BLE001 - show it in the banner, don't crash the viewer
            self.vm.report_error(f"Could not save the image: {exc}")

    def _on_timer(self) -> None:
        self.vm.tick()

    def _on_user_levels(self) -> None:
        if not self._applying_levels:
            lo, hi = self.hist.getLevels()
            self._levels_from_histogram = True
            try:
                self.vm.set_manual_levels(lo, hi)
            finally:
                self._levels_from_histogram = False

    def _on_mouse_moved(self, scene_pos: QtCore.QPointF) -> None:
        vb = self.plot.vb
        if vb.sceneBoundingRect().contains(scene_pos):
            p = vb.mapSceneToView(scene_pos)
            self.vm.hover_at(p.x(), p.y())
        else:
            self.vm.hover_leave()

    # ------------------------------------------------------------------ view-model -> widgets
    def _declare_bindings(self) -> None:
        b = self.bindings.bind
        b("window_title", lambda: self.setWindowTitle(self.vm.window_title))
        b("status", lambda: self.statusBar().showMessage(self.vm.status))
        b("source_path", lambda: self.path_edit.setText(self.vm.source_path))   # a real path or empty
        b("source_label", lambda: self.title_label.setText(self.vm.source_label))
        b("loaded", self._show_page)
        b("loaded", lambda: self.act_save.setEnabled(self.vm.loaded))
        b("loaded", self._enable_controls)
        b("error", lambda: self.banner.show_message(self.vm.error))
        b("tof_available", lambda: (self.tof_box.setVisible(self.vm.tof_available),
                                    self.tof_dock.setVisible(self.vm.tof_available)))
        b("dimensions", self._paint_dimensions)
        b("slice_mode", lambda: self.mode_control.set_choice(self.vm.slice_mode))
        b("tof_mode", lambda: self.tof_mode_control.set_choice(self.vm.tof_mode))
        b("can_play", lambda: self.play_button.setEnabled(self.vm.can_play))
        b("fps", self._paint_fps)
        b("playing", self._paint_playing)
        b("colormap", self._paint_colormap)
        b("level_mode", self._paint_level_mode)
        b("log_display", lambda: ui.silently(self.log_switch, lambda: self.log_switch.setChecked(self.vm.log_display)))
        b("image", self._draw_image)
        b(("levels", "level_mode"), self._paint_levels)       # after the image, as before
        b("info_text", lambda: self.info_view.setPlainText(self.vm.info_text))
        b("pixel_text", lambda: self._pixel_label.setText(self.vm.pixel_text))
        b("tof_profile", self._paint_tof_profile)
        b("tof_marker", self._paint_tof_marker)
        b("metrics", lambda: self.metrics.set_metrics(self.vm.metrics))
        b("context", lambda: self.chips.set_chips(self.vm.context))

    def _show_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_VIEWER if self.vm.loaded else self.PAGE_EMPTY)

    def _enable_controls(self) -> None:
        for card in (self.slice_card, self.display_card):
            card.setEnabled(self.vm.loaded)

    def _paint_dimensions(self) -> None:
        for state in self.vm.dimensions:
            self.dim_controls[state.name].show_state(state.label, state.lo, state.hi, state.value, state.enabled)

    def _paint_fps(self) -> None:
        ui.silently(self.fps_spin, lambda: self.fps_spin.setValue(self.vm.fps))
        if self._timer.isActive():
            self._timer.start(int(1000 / self.vm.fps))

    def _paint_playing(self) -> None:
        ui.silently(self.play_button, lambda: self.play_button.setChecked(self.vm.playing))
        self.play_button.setText("Pause  (Space)" if self.vm.playing else "Play  (Space)")
        if self.vm.playing:
            self._timer.start(int(1000 / self.vm.fps))
        else:
            self._timer.stop()

    def _paint_colormap(self) -> None:
        self.hist.gradient.setColorMap(_colormap(self.vm.colormap))
        self.cmap_control.set_choice(self.vm.colormap)

    def _paint_level_mode(self) -> None:
        self.level_control.set_choice(self.vm.level_mode)

    def _paint_levels(self) -> None:
        """Levels into the histogram and the Min/Max boxes. While locked the colour bar's axis is pinned
        too, so it stays exactly the same from slice to slice; adaptive, it follows the data.

        A lock made from what is on screen (the toggle, L, a drag in the histogram) keeps the axis where
        it is, so the colour bar does not jump under the mouse; new values from elsewhere (typed, global
        range, log display) fit the axis to the lock."""
        levels = self.vm.levels
        if levels is None:
            return
        self._applying_levels = True
        try:
            self.hist.setLevels(*levels)
            if self.vm.level_mode is LevelMode.LOCKED:
                if self._levels_from_histogram or levels == self._painted_levels:
                    self.hist.vb.updateAutoRange()       # settle a pending adaptive range before reading it
                    lo, hi = self.hist.getHistogramRange()
                    self.hist.setHistogramRange(min(lo, levels[0]), max(hi, levels[1]), padding=0)
                else:
                    self.hist.setHistogramRange(*levels)
            else:
                self.hist.autoHistogramRange()
            for key, value in zip(("low", "high"), levels):
                self.level_edits[key].set_value(value)
        finally:
            self._applying_levels = False
        self._painted_levels = levels

    def _paint_tof_profile(self) -> None:
        prof = self.vm.tof_profile
        if prof is None:
            self.tof_curve.setData([], [])
            self.tof_plot.setTitle("hover over the image")
        else:
            self.tof_curve.setData(list(prof.x), list(prof.y))
            self.tof_plot.setTitle(prof.title)

    def _paint_tof_marker(self) -> None:
        marker = self.vm.tof_marker
        self.tof_marker_line.setVisible(marker is not None)
        if marker is not None:
            self.tof_marker_line.setValue(marker)

    def _draw_image(self) -> None:
        im = self.vm.image
        if im is None:
            return
        self.img.setImage(np.ascontiguousarray(im.data), autoLevels=False)
        self.img.setRect(QtCore.QRectF(im.x0, im.y0, im.width, im.height))
        self.plot.setLabel("bottom", im.col_label)
        self.plot.setLabel("left", im.row_label)
        self.plot.setTitle(im.title)
        key = (im.data.shape, im.row_label, im.col_label, im.x0, im.y0, im.width, im.height)
        if key != self._geometry_key:
            self._geometry_key = key
            self.plot.setRange(xRange=(im.x0, im.x0 + im.width), yRange=(im.y0, im.y0 + im.height),
                               padding=0)
