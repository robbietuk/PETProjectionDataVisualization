# SPDX-License-Identifier: Apache-2.0
"""VIEW layer: the projection data pane, the self-contained display of one data set.

A pane shows what its ``ProjectionPaneViewModel`` holds: the title and context chips, the image with
its colour bar (histogram) and, beside it, the colour level controls (Adaptive | Locked, Max, Min and
the global range), the cursor readout floating in a corner of the image, the slice metrics and, in a
resizable column on the right, the profile plots: the TOF profile and the line profile (Row | Column |
Free, with an optional curve per TOF bin). A click on the image freezes both profiles at that LOR,
marked on the image; another click (or the view model's ``release_freeze``) releases them. It binds only to its own view model and knows
nothing about the window, the rail or the toolbar, so a window can later hold several panes (#20).
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from typing import Callable, ParamSpec

from PySide6 import QtCore, QtGui, QtWidgets

from ..viewmodel import (LEVEL_MODE_OPTIONS, LINE_MODE_OPTIONS, BindingRegistry, Corner, LevelMode, LineMode,
                         ProjectionPaneViewModel)
from . import components as ui
from ._compat import override
from .styling import fit_graphics_width, style_graphics_widget, style_histogram, style_line_roi, style_plot
from .theme import DARK, GAP, Palette
from .tof_plot import TofViewBox

pg.setConfigOptions(imageAxisOrder="row-major", antialias=True)  # numpy rows -> screen rows

PLOT_COLUMN_WIDTH = 300       # initial width of the profile plot column; the splitter resizes it
NO_PROFILE = "hover over the image"
NO_LINE_PROFILE = "hover over the image, or choose Free and drag the line"
OVERLAY_ALPHA = 70            # 0-255: the per-TOF-bin curves are faint, behind the profile of the image
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
        self._painting_free_line = False        # set while the view model's free line is drawn (no echo)
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
        self.plot.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        # the frozen LOR (a click) and the free line of the line profile, drawn on the image
        self.freeze_marker = pg.ScatterPlotItem(symbol="+", size=22)
        self.freeze_marker.setZValue(10)
        self.plot.addItem(self.freeze_marker)
        self.free_roi = pg.LineSegmentROI([(0.0, 0.0), (1.0, 1.0)], movable=True)
        self.free_roi.setZValue(11)
        self.free_roi.setVisible(False)
        self.free_roi.sigRegionChangeFinished.connect(self._on_free_line_moved)
        self.plot.addItem(self.free_roi)
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
        self.plot_column.addWidget(self._build_tof_dock())
        self.plot_column.addWidget(self._build_line_dock())
        return self.plot_column

    @staticmethod
    def _caption(text: str) -> QtWidgets.QLabel:
        # long texts go in wrapping labels, not plot titles: a long pyqtgraph title sets a minimum width
        # for the whole plot, which then overflows a narrow plot column
        label = QtWidgets.QLabel(text)
        label.setObjectName("Muted")
        label.setWordWrap(True)
        return label

    def _build_tof_dock(self) -> QtWidgets.QWidget:
        self.tof_dock = ui.Card("TOF profile of the LOR under the cursor")
        # x (TOF bin) is fixed to the data set's bins; wheel, drag, double-click and "A" act on y (counts)
        self.tof_view = TofViewBox()
        self.tof_plot = pg.PlotWidget(viewBox=self.tof_view)
        self.tof_plot.getPlotItem().setMenuEnabled(False)    # its x-axis entries would move the TOF bins out of view
        self.tof_plot.setLabel("bottom", "TOF bin")
        self.tof_plot.setLabel("left", "counts")
        self.tof_plot.setMinimumHeight(150)
        self.tof_title = self._caption(NO_PROFILE)
        self.tof_context = self._caption("")           # while TOF is collapsed: the plot is context
        self.tof_context.setVisible(False)
        self.tof_curve = self.tof_plot.plot([], [], symbol="o", symbolSize=7)
        self.tof_marker_line = pg.InfiniteLine(angle=90, movable=False)
        self.tof_plot.addItem(self.tof_marker_line)
        self.tof_reference_line = pg.InfiniteLine(angle=0, movable=False)   # the Sum/Mean/Max the image shows
        self.tof_reference_line.setVisible(False)
        self.tof_plot.addItem(self.tof_reference_line)
        self.tof_dock.body.addWidget(self.tof_title)
        self.tof_dock.body.addWidget(self.tof_context)
        self.tof_dock.body.addWidget(self.tof_plot, 1)
        return self.tof_dock

    def _build_line_dock(self) -> QtWidgets.QWidget:
        self.line_dock = ui.Card("Line profile")
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        self.line_mode_control = ui.SegmentedControl(LINE_MODE_OPTIONS)
        self.line_mode_control.setAccessibleName("Line profile: along the row or column through the cursor, "
                                                 "or along a free line")
        self.line_mode_control.choiceChanged.connect(self._on_line_mode)
        self.overlay_switch = QtWidgets.QCheckBox("per TOF bin")
        self.overlay_switch.setToolTip("Also draw one faint curve per TOF bin along the same line")
        self.overlay_switch.toggled.connect(self._on_overlay_toggled)
        header.addWidget(self.line_mode_control)
        header.addStretch(1)
        self.line_dock.body.addLayout(header)
        self.line_dock.body.addWidget(self.overlay_switch)       # its own line: the column stays narrow
        self.line_title = self._caption(NO_LINE_PROFILE)
        self.line_dock.body.addWidget(self.line_title)
        self.line_plot = pg.PlotWidget()
        self.line_plot.getPlotItem().setMenuEnabled(False)
        self.line_plot.setLabel("left", "value")
        self.line_plot.setMinimumHeight(150)
        self.line_curve = self.line_plot.plot([], [], connect="finite")
        self.line_curve.setZValue(5)                  # above the per-TOF-bin curves
        self.overlay_curves: list[pg.PlotDataItem] = []
        self.line_dock.body.addWidget(self.line_plot, 1)
        return self.line_dock

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
        self.tof_reference_line.setPen(pg.mkPen(p.marker, width=2, style=QtCore.Qt.PenStyle.DashLine))
        style_plot(self.line_plot.getPlotItem(), p)
        self.line_plot.setBackground(p.surface)
        self.line_curve.setPen(pg.mkPen(p.curve, width=2))
        for curve in self.overlay_curves:
            curve.setPen(self._overlay_pen())
        self.freeze_marker.setPen(pg.mkPen(p.marker, width=3))
        style_line_roi(self.free_roi, p)
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

    def _on_line_mode(self, mode: LineMode) -> None:
        self._run(self.vm.set_line_mode, mode)

    def _on_overlay_toggled(self, on: bool) -> None:
        self._run(self.vm.set_show_tof_overlay, on)

    def _overlay_pen(self) -> QtGui.QPen:
        colour = QtGui.QColor(self.palette_tokens.curve)
        colour.setAlpha(OVERLAY_ALPHA)
        return pg.mkPen(colour, width=1)

    def _on_free_line_moved(self) -> None:
        if self._painting_free_line:
            return
        (x0, y0), (x1, y1) = ((q.x(), q.y()) for q in
                              (self.free_roi.mapToParent(handle.pos()) for handle in self.free_roi.getHandles()))
        self.vm.set_free_line(x0, y0, x1, y1)

    def _on_mouse_clicked(self, event: pg.MouseClickEvent) -> None:
        """A left click on the image freezes the profiles there, or releases them."""
        if event.button() != QtCore.Qt.MouseButton.LeftButton or event.double():
            return
        vb = self.plot.vb
        scene_pos = event.scenePos()
        if vb.sceneBoundingRect().contains(scene_pos):
            p = vb.mapSceneToView(scene_pos)
            self.vm.click_at(p.x(), p.y())

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
        b(("show_line_profile", "tof_available", "show_tof_profile"), self._paint_line_available)
        b("line_mode", lambda: self.line_mode_control.set_choice(self.vm.line_mode))
        b("line_axis_names", self._paint_line_axis_names)
        b("show_tof_overlay", lambda: ui.silently(
            self.overlay_switch, lambda: self.overlay_switch.setChecked(self.vm.show_tof_overlay)))
        b("free_line", self._paint_free_line)
        b("line_profile", self._paint_line_profile)
        b("frozen_at", self._paint_frozen)
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
        self.tof_dock.setVisible(self.vm.tof_available and self.vm.show_tof_profile)

    def _paint_line_available(self) -> None:
        self.line_dock.setVisible(self.vm.show_line_profile)
        self.overlay_switch.setVisible(self.vm.tof_available)
        tof_shown = self.vm.tof_available and self.vm.show_tof_profile
        self.plot_column.setVisible(tof_shown or self.vm.show_line_profile)   # no plots: the image takes the room

    def _paint_line_axis_names(self) -> None:
        row, column = self.vm.line_axis_names
        for mode, tip in ((LineMode.ROW, row), (LineMode.COLUMN, column),
                          (LineMode.FREE, "along a line you drag on the image")):
            self.line_mode_control.set_choice_tooltip(mode, tip.capitalize())

    def _paint_free_line(self) -> None:
        line = self.vm.free_line
        self.free_roi.setVisible(line is not None)
        if line is None:
            return
        x0, y0, x1, y1 = line
        self._painting_free_line = True
        try:
            for handle, (x, y) in zip(self.free_roi.getHandles(), ((x0, y0), (x1, y1))):
                self.free_roi.movePoint(handle, QtCore.QPointF(x, y), finish=False)   # view coordinates
        finally:
            self._painting_free_line = False

    def _paint_line_profile(self) -> None:
        prof = self.vm.line_profile
        if prof is None:
            self.line_curve.setData([], [])
            self._set_overlay(())
            self.line_title.setText(NO_LINE_PROFILE)
            return
        self.line_curve.setData(list(prof.x), list(prof.y))
        self._set_overlay(tuple((prof.x, y) for y in prof.overlay))
        self.line_plot.setLabel("bottom", prof.x_label)
        self.line_title.setText(prof.title)

    def _set_overlay(self, curves: tuple[tuple[tuple[float, ...], tuple[float, ...]], ...]) -> None:
        while len(self.overlay_curves) > len(curves):
            self.line_plot.removeItem(self.overlay_curves.pop())
        while len(self.overlay_curves) < len(curves):
            curve = self.line_plot.plot([], [], connect="finite", pen=self._overlay_pen())
            self.overlay_curves.append(curve)
        for curve, (x, y) in zip(self.overlay_curves, curves):
            curve.setData(list(x), list(y))

    def _paint_frozen(self) -> None:
        at = self.vm.frozen_at
        self.freeze_marker.setData([] if at is None else [at[0]], [] if at is None else [at[1]])
        self.tof_dock.set_title("TOF profile of the frozen LOR (click or Esc releases)" if at is not None
                                else "TOF profile of the LOR under the cursor")

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
        context = prof.context if prof is not None else ""
        self.tof_context.setText(context)
        self.tof_context.setVisible(bool(context))
        reference = prof.reference if prof is not None else None
        self.tof_reference_line.setVisible(reference is not None)
        if reference is not None:
            self.tof_reference_line.setValue(reference)

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
