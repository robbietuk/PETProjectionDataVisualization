# SPDX-License-Identifier: Apache-2.0
"""VIEW layer: the projection data pane, the self-contained display of one data set.

A pane shows what its ``ProjectionPaneViewModel`` holds: the title and context chips, the image with
its colour bar (histogram) and, beside it, the colour level controls (Adaptive | Locked, Max, Min and
the global range), the cursor readout floating in a corner of the image, the slice metrics and, in a
resizable column on the right, the profile plots (today the TOF profile). It binds only to its own view model and knows
nothing about the window, the rail or the toolbar, so a window can later hold several panes (#20).
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from typing import Callable, ParamSpec

from PySide6 import QtCore, QtWidgets

from ..viewmodel import LEVEL_MODE_OPTIONS, BindingRegistry, Corner, LevelMode, ProjectionPaneViewModel
from . import components as ui
from ._compat import override
from .styling import fit_graphics_width, style_graphics_widget, style_histogram, style_plot
from .theme import DARK, GAP, Palette
from .tof_plot import TofViewBox

pg.setConfigOptions(imageAxisOrder="row-major", antialias=True)  # numpy rows -> screen rows

PLOT_COLUMN_WIDTH = 340       # initial width of the profile plot column; the splitter resizes it
NO_PROFILE = "hover over the image"
READOUT_MARGIN = 8            # between the readout and the edges of the image
LEVEL_LOCK_TIP = ("Colour levels (L): Adaptive recomputes Min/Max for every slice; Locked keeps Min/Max and the "
                  "colour bar constant while you change view, axial position, segment, TOF bin, slice mode or "
                  "log display. Typing a level or dragging the histogram locks at the new values.")

_P = ParamSpec("_P")


def readout_text(lines: tuple[tuple[str, str], ...]) -> str:
    """The readout's (label, value) lines as aligned text (the readout uses a monospace font)."""
    width = max((len(label) for label, _ in lines), default=0)
    return "\n".join(f"{label:<{width}}  {value}" for label, value in lines)


def colormap(name: str) -> pg.ColorMap:
    if name != "grey":
        try:
            return pg.colormap.get(name)
        except Exception:  # noqa: BLE001 - fall through to grey
            pass
    return pg.ColorMap([0.0, 1.0], [(0, 0, 0), (255, 255, 255)])


class ProjectionDataPane(QtWidgets.QWidget):
    """Image, colour bar, readout, metrics and profile plots of one ``ProjectionPaneViewModel``."""

    def __init__(self, vm: ProjectionPaneViewModel, palette: Palette = DARK,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProjectionDataPane")
        self.vm = vm
        self.palette_tokens = palette
        self._geometry_key: tuple[object, ...] | None = None
        self._applying_levels = False
        self._levels_from_histogram = False     # set while a histogram drag is handed to the view model
        self._painted_levels: tuple[float, float] | None = None
        self._build()
        self._restyle_plots()
        self.bindings = BindingRegistry(vm)
        self._declare_bindings()
        self.bindings.start()

    # ------------------------------------------------------------------ construction
    def _build(self) -> None:
        col = QtWidgets.QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(GAP)
        self.title_label = ui.ElidedLabel("")     # a long title is elided; the chips keep their size
        self.title_label.setObjectName("Title")
        self.chips = ui.ChipRow()
        header.addWidget(self.title_label, 1)
        header.addWidget(self.chips)
        col.addLayout(header)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self._build_image_area())
        self.splitter.addWidget(self._build_plot_column())
        self.splitter.setStretchFactor(0, 1)       # the image takes the extra space
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([1000, PLOT_COLUMN_WIDTH])
        col.addWidget(self.splitter, 1)

    def _build_image_area(self) -> QtWidgets.QWidget:
        area = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(area)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
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
        self.hist = pg.HistogramLUTItem()          # the colour bar
        self.hist.setImageItem(self.img)
        self.glw.addItem(self.hist, row=0, col=1)
        self.hist.sigLevelChangeFinished.connect(self._on_user_levels)
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        # the value under the cursor floats over a corner of the image, out of the cursor's way
        self.readout = QtWidgets.QLabel("", self.glw)
        self.readout.setObjectName("PixelReadout")
        self.readout.setAccessibleName("Value under the cursor")
        self.readout.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)   # the image still gets the mouse
        self.readout.setVisible(False)
        self.glw.installEventFilter(self)          # resizes move the readout with the image
        image_row = QtWidgets.QHBoxLayout()
        image_row.setSpacing(GAP)
        image_row.addWidget(self.glw, 1)
        image_row.addWidget(self._build_level_panel())
        image_card.body.addLayout(image_row, 1)
        col.addWidget(image_card, 1)
        self.metrics = ui.MetricGrid(columns=6)
        col.addWidget(self.metrics)
        return area

    def _build_level_panel(self) -> QtWidgets.QWidget:
        """The colour level controls, beside the colour bar: Max at the top, Min at the bottom, like the bar."""
        self.level_panel = QtWidgets.QFrame()
        self.level_panel.setObjectName("LevelPanel")
        self.level_panel.setAccessibleName("Colour levels")
        # as wide as its widest control (Adaptive | Locked), so no label is ever cut off
        self.level_panel.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Preferred)
        col = QtWidgets.QVBoxLayout(self.level_panel)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        self.level_edits: dict[str, ui.NumberEdit] = {}
        for key, label in (("high", "Max level"), ("low", "Min level")):
            edit = ui.NumberEdit()                   # any magnitude, e.g. 1e-8; commits on Enter/focus-out
            edit.setMinimumWidth(96)
            edit.setAccessibleName(label)
            edit.setToolTip(f"{label}: type a value and press Enter to lock the colour levels there")
            edit.valueEdited.connect(self._level_bound_slot(key))
            self.level_edits[key] = edit
        self.level_control = ui.SegmentedControl(LEVEL_MODE_OPTIONS)      # Adaptive | Locked
        self.level_control.setAccessibleName("Colour levels: adaptive or locked")
        self.level_control.setToolTip(LEVEL_LOCK_TIP)
        self.level_control.choiceChanged.connect(self._on_level_mode)
        self.global_button = QtWidgets.QPushButton("Global range")
        self.global_button.setAccessibleName("Lock colour levels to the global range of the data set")
        self.global_button.setToolTip("Lock Min/Max at the range of the whole data set in the current TOF mode "
                                      "(reads every segment once).")
        self.global_button.clicked.connect(lambda _=False: self._run(self.vm.lock_global_range))
        caption = QtWidgets.QLabel("Max")
        caption.setObjectName("Section")
        col.addWidget(caption)
        col.addWidget(self.level_edits["high"])
        col.addStretch(1)
        col.addWidget(self.level_control)
        col.addWidget(self.global_button)
        col.addStretch(1)
        caption = QtWidgets.QLabel("Min")
        caption.setObjectName("Section")
        col.addWidget(caption)
        col.addWidget(self.level_edits["low"])
        return self.level_panel

    def _build_plot_column(self) -> QtWidgets.QWidget:
        """The profile plots, stacked in a vertical splitter so each can be resized."""
        self.plot_column = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.plot_column.setObjectName("PlotColumn")
        self.plot_column.setChildrenCollapsible(False)
        self.tof_dock = ui.Card("TOF profile of the LOR under the cursor")
        # x (TOF bin) is fixed to the data set's bins; wheel, drag, double-click and "A" act on y (counts)
        self.tof_view = TofViewBox()
        self.tof_plot = pg.PlotWidget(viewBox=self.tof_view)
        self.tof_plot.getPlotItem().setMenuEnabled(False)    # its x-axis entries would move the TOF bins out of view
        self.tof_plot.setLabel("bottom", "TOF bin")
        self.tof_plot.setLabel("left", "counts")
        self.tof_plot.setMinimumHeight(150)
        # the LOR is named in a wrapping label, not the plot title: a long pyqtgraph title sets a minimum
        # width for the whole plot, which then overflows a narrow plot column
        self.tof_title = QtWidgets.QLabel(NO_PROFILE)
        self.tof_title.setObjectName("Muted")
        self.tof_title.setWordWrap(True)
        self.tof_curve = self.tof_plot.plot([], [], symbol="o", symbolSize=7)
        self.tof_marker_line = pg.InfiniteLine(angle=90, movable=False)
        self.tof_plot.addItem(self.tof_marker_line)
        self.tof_dock.body.addWidget(self.tof_title)
        self.tof_dock.body.addWidget(self.tof_plot, 1)
        self.plot_column.addWidget(self.tof_dock)
        return self.plot_column

    # ------------------------------------------------------------------ theming
    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
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
        fit_graphics_width(self.glw)       # the plot title or the axes may have changed

    # ------------------------------------------------------------------ user input -> commands
    def _run(self, command: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs) -> None:
        with ui.wait_cursor():
            command(*args, **kwargs)

    def _on_level_mode(self, mode: LevelMode) -> None:
        self._run(self.vm.set_level_mode, mode)

    def _level_bound_slot(self, key: str) -> Callable[[float], None]:
        """A slot for one level box: ``key`` is ``low`` or ``high`` (the keyword of ``set_level_bounds``)."""
        return lambda value: self._run(self.vm.set_level_bounds, **{key: value})

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
        b("title", lambda: self.title_label.setText(self.vm.title))
        b(("tof_available", "show_tof_profile"), self._paint_tof_available)
        b("colormap", lambda: self.hist.gradient.setColorMap(colormap(self.vm.colormap)))
        b("image", self._draw_image)
        b(("levels", "level_mode"), self._paint_levels)       # after the image, as before
        b("level_mode", lambda: self.level_control.set_choice(self.vm.level_mode))
        b("levels", self._paint_level_edits)
        b(("readout", "readout_corner"), self._paint_readout)
        b("pixel_text", lambda: self.readout.setAccessibleDescription(self.vm.pixel_text))   # one line for screen readers
        b("tof_range", self._paint_tof_range)
        b("tof_profile", self._paint_tof_profile)
        b("tof_marker", self._paint_tof_marker)
        b("metrics", lambda: self.metrics.set_metrics(self.vm.metrics))
        b("context", lambda: self.chips.set_chips(self.vm.context))

    def _paint_level_edits(self) -> None:
        levels = self.vm.levels
        if levels is None:
            return
        for key, value in zip(("low", "high"), levels):
            self.level_edits[key].set_value(value)

    def _paint_readout(self) -> None:
        lines = self.vm.readout
        self.readout.setText(readout_text(lines))
        self.readout.setVisible(bool(lines))
        if lines:
            self.readout.adjustSize()
            self._place_readout()

    def _place_readout(self) -> None:
        """Put the readout in ``readout_corner`` of the image (the plot's view box, inside the axes)."""
        box = self.glw.mapFromScene(self.plot.vb.sceneBoundingRect()).boundingRect()
        corner: Corner = self.vm.readout_corner
        size = self.readout.sizeHint()
        x = box.right() - size.width() - READOUT_MARGIN if corner.right else box.left() + READOUT_MARGIN
        y = box.bottom() - size.height() - READOUT_MARGIN if corner.bottom else box.top() + READOUT_MARGIN
        self.readout.setGeometry(max(0, x), max(0, y), size.width(), size.height())

    @override
    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt override
        if watched is self.glw and event.type() == QtCore.QEvent.Type.Resize:
            QtCore.QTimer.singleShot(0, self._place_readout)     # once the plot inside has been resized too
        return False

    def _paint_tof_available(self) -> None:
        shown = self.vm.tof_available and self.vm.show_tof_profile
        self.tof_dock.setVisible(shown)
        self.plot_column.setVisible(shown)    # no profile to show: the image takes the room

    def _paint_levels(self) -> None:
        """Levels into the colour bar. While locked its axis is pinned too, so it stays exactly the same
        from slice to slice; adaptive, it follows the data.

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
        finally:
            self._applying_levels = False
        self._painted_levels = levels

    def _paint_tof_range(self) -> None:
        r = self.vm.tof_range
        if r is not None:                         # non-TOF data hides the plot
            self.tof_view.set_tof_range(*r)

    def _paint_tof_profile(self) -> None:
        prof = self.vm.tof_profile
        if prof is None:
            self.tof_curve.setData([], [])
            self.tof_title.setText(NO_PROFILE)
            self.tof_view.set_counts(())
        else:
            self.tof_view.set_counts(prof.y)
            self.tof_curve.setData(list(prof.x), list(prof.y))
            self.tof_title.setText(prof.title)

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
        fit_graphics_width(self.glw)       # the plot title or the axes may have changed
        key = (im.data.shape, im.row_label, im.col_label, im.x0, im.y0, im.width, im.height)
        if key != self._geometry_key:
            self._geometry_key = key
            self.plot.setRange(xRange=(im.x0, im.x0 + im.width), yRange=(im.y0, im.y0 + im.height),
                               padding=0)
