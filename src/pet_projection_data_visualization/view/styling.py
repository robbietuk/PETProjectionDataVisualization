# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Apply a ``Palette`` to the whole application (Qt palette + stylesheet) and to pyqtgraph plots."""
from __future__ import annotations

import math

import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from ._compat import override
from .theme import DEFAULT_PALETTE, FONT_SIZE, Palette, build_stylesheet


def apply_theme(app: QtWidgets.QApplication, palette: Palette = DEFAULT_PALETTE) -> None:
    app.setStyle("Fusion")                    # consistent base on every OS; the stylesheet does the rest
    qp = QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    for r, colour in ((role.Window, palette.canvas), (role.Base, palette.raised), (role.AlternateBase, palette.surface),
                      (role.Button, palette.raised), (role.Text, palette.text), (role.WindowText, palette.text),
                      (role.ButtonText, palette.text), (role.ToolTipBase, palette.raised),
                      (role.ToolTipText, palette.text), (role.Highlight, palette.accent),
                      (role.HighlightedText, palette.on_accent), (role.PlaceholderText, palette.text_muted)):
        qp.setColor(r, QtGui.QColor(colour))
    disabled = QtGui.QPalette.ColorGroup.Disabled
    for r in (role.WindowText, role.Text, role.ButtonText):
        qp.setColor(disabled, r, QtGui.QColor(palette.text_muted))
    app.setPalette(qp)
    app.setStyleSheet(build_stylesheet(palette))


def style_plot(plot_item: pg.PlotItem, palette: Palette) -> None:
    """Axis and title colours for a pyqtgraph PlotItem."""
    for name in ("left", "bottom"):
        axis = plot_item.getAxis(name)
        axis.setPen(pg.mkPen(palette.plot_axis))
        axis.setTextPen(pg.mkPen(palette.plot_axis))
    title = plot_item.titleLabel.text
    size = f"{FONT_SIZE}px"                                 # the body size of the type scale
    if title:
        plot_item.setTitle(title, color=palette.text, size=size)  # re-render: setAttr leaves existing text as is
    else:
        plot_item.titleLabel.setAttr("color", palette.text)
        plot_item.titleLabel.setAttr("size", size)


def style_histogram(hist: pg.HistogramLUTItem, palette: Palette) -> None:
    hist.axis.setPen(pg.mkPen(palette.plot_axis))
    hist.axis.setTextPen(pg.mkPen(palette.plot_axis))


def style_line_roi(roi: pg.LineSegmentROI, palette: Palette) -> None:
    """A draggable line on a plot (and its end handles) in the accent colour."""
    roi.setPen(pg.mkPen(palette.accent, width=2))
    for handle in roi.getHandles():
        handle.pen = pg.mkPen(palette.accent, width=2)
        handle.update()


def style_graphics_widget(widget: pg.GraphicsView, palette: Palette) -> None:
    """The plots sit inside cards, so they share the card's surface (flat, no inset box)."""
    widget.setBackground(palette.surface)


def fit_graphics_width(widget: pg.GraphicsLayoutWidget) -> None:
    """Give ``widget`` the minimum width its plots really need (axes, title, histogram).

    A QGraphicsView does not pass its scene's minimum size on to the widget layout, so in a narrow window
    the plots were cut off instead of the window refusing to get narrower. The first call also makes the
    minimum follow every later change of the scene's layout (tick-label widths after a resize or a range
    change, fonts after polishing); call it again whenever a title or an axis label changes."""
    # drop the cached hint; pyqtgraph shadows layout() with an attribute, so call the QGraphicsWidget method
    grid = QtWidgets.QGraphicsWidget.layout(widget.ci)
    if grid is not None:
        grid.invalidate()
    _apply_scene_minimum(widget)
    if widget.findChild(_SceneWidthFollower, _SceneWidthFollower.NAME) is None:
        widget.ci.installEventFilter(_SceneWidthFollower(widget))


def _apply_scene_minimum(widget: pg.GraphicsLayoutWidget) -> None:
    need = math.ceil(widget.ci.effectiveSizeHint(QtCore.Qt.SizeHint.MinimumSize).width()) + 2 * widget.frameWidth()
    if need != widget.minimumWidth():
        widget.setMinimumWidth(need)


class _SceneWidthFollower(QtCore.QObject):
    """Re-applies the scene's minimum width to the view whenever the scene's top layout asks for a re-layout."""

    NAME = "SceneWidthFollower"

    def __init__(self, widget: pg.GraphicsLayoutWidget) -> None:
        super().__init__(widget)
        self.setObjectName(self.NAME)
        self._widget = widget

    @override
    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QtCore.QEvent.Type.LayoutRequest:
            _apply_scene_minimum(self._widget)     # no invalidate here: that would post another request
        return False
