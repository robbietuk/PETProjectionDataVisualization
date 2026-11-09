# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Reusable widgets. None knows about the view model; the window wires them to it.

Shared behaviour is written once:
* ``ChoiceControl`` is the common interface of every control that picks one value from a
  ``ChoiceOptions`` (``SegmentedControl``, ``ChoiceCombo``): ``choiceChanged(value)`` fires for user
  input only, ``set_choice(value)`` updates silently.
* ``silently`` runs a widget update with its signals blocked (used by every programmatic update).
"""
from __future__ import annotations

from typing import Callable, Generic, Hashable, Iterable, TypeVar

from PySide6 import QtCore, QtGui, QtWidgets

from ..viewmodel.formatting import format_number, parse_number
from ..viewmodel.options import ChoiceOptions
from ._compat import override
from .theme import CHIP_HEIGHT, GAP, PAD

T = TypeVar("T", bound=Hashable)


def silently(widget: QtWidgets.QWidget, fn: Callable[[], object]) -> None:
    """Run ``fn`` with the widget's signals blocked."""
    was = widget.blockSignals(True)
    try:
        fn()
    finally:
        widget.blockSignals(was)


class ChoiceControl(QtWidgets.QWidget, Generic[T]):
    """Interface + shared state for choice widgets."""

    choiceChanged = QtCore.Signal(object)           # emits a ``T``

    def __init__(self, options: ChoiceOptions[T], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.options = options

    def set_choice(self, value: T) -> None:        # pragma: no cover - interface
        raise NotImplementedError

    def choice(self) -> T | None:                   # pragma: no cover - interface
        raise NotImplementedError


class _SegmentButton(QtWidgets.QPushButton):
    """A segment of a ``SegmentedControl``. The checked one is drawn bold (stylesheet), so the size hints
    leave room for the bold label: choosing a segment never clips its text."""

    def _bold_extra(self) -> int:
        bold = QtGui.QFont(self.font())
        bold.setBold(True)
        text = self.text()
        return max(0, QtGui.QFontMetrics(bold).horizontalAdvance(text) - self.fontMetrics().horizontalAdvance(text))

    @override
    def sizeHint(self) -> QtCore.QSize:
        hint = super().sizeHint()
        return QtCore.QSize(hint.width() + self._bold_extra(), hint.height())

    @override
    def minimumSizeHint(self) -> QtCore.QSize:
        hint = super().minimumSizeHint()
        return QtCore.QSize(hint.width() + self._bold_extra(), hint.height())


class SegmentedControl(ChoiceControl[T]):
    def __init__(self, options: ChoiceOptions[T], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(options, parent)
        frame = QtWidgets.QFrame(self)
        frame.setObjectName("Segmented")
        row = QtWidgets.QHBoxLayout(frame)
        self._frame_row = row
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QtWidgets.QPushButton] = []
        for i, label in enumerate(options.labels):
            b = _SegmentButton(label)
            b.setCheckable(True)
            b.setProperty("segment", "true")
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self._group.addButton(b, i)
            row.addWidget(b, 1)
            self._buttons.append(b)
        self._group.idClicked.connect(self._on_clicked)

    def _on_clicked(self, i: int) -> None:
        self.choiceChanged.emit(self.options.value_at(i))

    @override
    def set_choice(self, value: T) -> None:
        self._buttons[self.options.index_of(value)].setChecked(True)

    @override
    def choice(self) -> T | None:
        i = self._group.checkedId()
        return self.options.value_at(i) if i >= 0 else None

    def set_choice_enabled(self, value: T, enabled: bool) -> None:
        self._buttons[self.options.index_of(value)].setEnabled(enabled)

    def set_compact(self) -> None:
        """Draw the control as tall as a compact toolbar row (thinner frame, less padding)."""
        self._frame_row.setContentsMargins(1, 1, 1, 1)
        for b in self._buttons:
            b.setProperty("compact", "true")


class ChoiceCombo(ChoiceControl[T]):
    def __init__(self, options: ChoiceOptions[T], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(options, parent)
        self._combo = QtWidgets.QComboBox()
        self._combo.addItems(list(options.labels))
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._combo)
        self._combo.activated.connect(self._on_activated)

    def _on_activated(self, i: int) -> None:
        self.choiceChanged.emit(self.options.value_at(i))

    @override
    def set_choice(self, value: T) -> None:
        silently(self._combo, lambda: self._combo.setCurrentIndex(self.options.index_of(value)))

    @override
    def choice(self) -> T:
        return self.options.value_at(self._combo.currentIndex())


class Card(QtWidgets.QFrame):
    """Titled container. Add content with ``card.body.addWidget(...)``."""

    def __init__(self, title: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(PAD, PAD - 2, PAD, PAD)
        lay.setSpacing(GAP - 2)
        self.title_label = QtWidgets.QLabel(title.upper())
        self.title_label.setObjectName("CardTitle")
        self.title_label.setVisible(bool(title))
        lay.addWidget(self.title_label)
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(8)
        lay.addLayout(self.body)
        self._outer = lay

    def set_vertical_padding(self, pad: int) -> None:
        """Less padding above and below the content, for a slim card such as the slice toolbar."""
        self._outer.setContentsMargins(PAD, pad, PAD, pad)


class LabeledRow(QtWidgets.QWidget):
    """Caption on the left, any control on the right (used for display options)."""

    def __init__(self, caption: str, control: QtWidgets.QWidget, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.caption = QtWidgets.QLabel(caption)
        self.caption.setObjectName("Muted")
        row.addWidget(self.caption)
        row.addStretch(1)
        row.addWidget(control)
        self.control = control


class ElidedLabel(QtWidgets.QLabel):
    """One-line label that shows ``…`` instead of being cut off, and can shrink to a few characters.

    ``text()`` keeps the full text; the tooltip shows it when the label is elided."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)

    def is_elided(self) -> bool:
        return self._elided_text() != self.text()

    def _elided_text(self) -> str:
        return self.fontMetrics().elidedText(self.text(), QtCore.Qt.TextElideMode.ElideRight,
                                             self.contentsRect().width())

    @override
    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt override
        hint = super().minimumSizeHint()
        return QtCore.QSize(min(hint.width(), self.fontMetrics().horizontalAdvance("Mmm…")), hint.height())

    @override
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802 - Qt override
        painter = QtGui.QPainter(self)
        try:
            painter.drawText(self.contentsRect(), int(self.alignment() | QtCore.Qt.AlignmentFlag.AlignVCenter),
                             self._elided_text())
        finally:
            painter.end()

    @override
    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self.setToolTip(self.text() if self.is_elided() else "")


class Chip(QtWidgets.QFrame):
    """A pill with one line of text. It never shrinks below its text: the padding is in the layout margins
    (not in the label's stylesheet, which Qt leaves out of the label's size hint), and the height is at
    least ``CHIP_HEIGHT``, which the stylesheet's radius (``CHIP_HEIGHT / 2``) is made for."""

    def __init__(self, text: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Chip")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 10, 2)
        self.label = QtWidgets.QLabel(text)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.label)
        self.setMinimumHeight(CHIP_HEIGHT)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    @override
    def sizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt override
        return super().sizeHint().expandedTo(self.minimumSize())


class ChipRow(QtWidgets.QWidget):
    """Chips side by side. The row keeps its size hint (``Minimum`` policy), so a neighbour such as a long
    title gives way instead of the chips being squeezed."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed)
        self._row = QtWidgets.QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(6)
        self._row.addStretch(1)
        self._chips: list[Chip] = []

    def texts(self) -> list[str]:
        return [c.label.text() for c in self._chips if not c.isHidden()]

    def set_chips(self, texts: Iterable[str]) -> None:
        texts = list(texts)
        while len(self._chips) < len(texts):
            chip = Chip("")
            self._row.insertWidget(len(self._chips), chip)
            self._chips.append(chip)
        for chip, text in zip(self._chips, texts):
            chip.label.setText(text)
            chip.setVisible(True)
        for chip in self._chips[len(texts):]:
            chip.setVisible(False)


class MetricTile(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Tile")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 9)
        lay.setSpacing(2)
        self.name = QtWidgets.QLabel("")
        self.name.setObjectName("TileLabel")
        self.value = QtWidgets.QLabel("")
        self.value.setObjectName("TileValue")
        lay.addWidget(self.name)
        lay.addWidget(self.value)


class MetricGrid(QtWidgets.QWidget):
    """Grid of label/value tiles filled from ``((label, value), ...)``.

    ``columns`` is the most tiles per row. When the grid is too narrow for that many, it reflows into
    fewer columns (down to half of ``columns``) instead of squeezing the numbers."""

    def __init__(self, columns: int = 3, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._min_columns = max(1, (columns + 1) // 2)
        self._shown_columns = columns
        self._grid = QtWidgets.QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        self._tiles: list[MetricTile] = []

    def pairs(self) -> list[tuple[str, str]]:
        return [(t.name.text(), t.value.text()) for t in self._tiles if not t.isHidden()]

    def column_count(self) -> int:
        return self._shown_columns

    def set_metrics(self, pairs: Iterable[tuple[str, str]]) -> None:
        pairs = list(pairs)
        while len(self._tiles) < len(pairs):
            tile = MetricTile()
            n = len(self._tiles)
            self._grid.addWidget(tile, n // self._shown_columns, n % self._shown_columns)
            self._tiles.append(tile)
        for tile, (name, value) in zip(self._tiles, pairs):
            tile.name.setText(name)
            tile.value.setText(value)
            tile.setVisible(True)
        for tile in self._tiles[len(pairs):]:
            tile.setVisible(False)
        # new values may need wider tiles: reflow once the tiles have taken the new text
        QtCore.QTimer.singleShot(0, self, self._reflow_to_width)

    def _reflow_to_width(self) -> None:
        self._reflow(self.width())

    def _tile_width(self) -> int:
        return max((t.minimumSizeHint().width() for t in self._tiles), default=0)

    def _row_width(self, columns: int) -> int:
        return columns * self._tile_width() + (columns - 1) * self._grid.horizontalSpacing()

    def _reflow(self, width: int) -> None:
        columns = self._columns
        while columns > self._min_columns and self._row_width(columns) > width:
            columns -= 1
        shown = max(1, sum(1 for t in self._tiles if not t.isHidden()))
        rows = -(-shown // columns)
        while columns > self._min_columns and -(-shown // (columns - 1)) == rows:
            columns -= 1                        # same number of rows, fuller last row: 3 + 3, not 5 + 1
        if columns == self._shown_columns:
            return
        self._shown_columns = columns
        for tile in self._tiles:
            self._grid.removeWidget(tile)
        for n, tile in enumerate(self._tiles):
            self._grid.addWidget(tile, n // columns, n % columns)
        for c in range(self._columns):          # columns left over from the wider layout take no space
            self._grid.setColumnStretch(c, 1 if c < columns else 0)

    @override
    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt override
        hint = super().minimumSizeHint()
        return QtCore.QSize(min(hint.width(), self._row_width(self._min_columns)), hint.height())

    @override
    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._reflow(event.size().width())


class Banner(QtWidgets.QFrame):
    """Inline, dismissable error message (replaces modal error dialogs)."""

    dismissed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Banner")
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(12, 8, 6, 8)
        self.label = QtWidgets.QLabel("")
        self.label.setWordWrap(True)
        close = QtWidgets.QPushButton("✕")
        close.setToolTip("Dismiss")
        close.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.dismissed)
        row.addWidget(self.label, 1)
        row.addWidget(close)
        self.setVisible(False)

    def show_message(self, text: str | None) -> None:
        self.label.setText(text or "")
        self.setVisible(bool(text))


class EmptyState(QtWidgets.QWidget):
    """Shown before any data is loaded."""

    def __init__(self, title: str, hint: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyState")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setObjectName("EmptyTitle")
        self.hint_label = QtWidgets.QLabel(hint)
        self.hint_label.setObjectName("EmptyHint")
        self.hint_label.setWordWrap(True)          # long hints wrap instead of widening the window
        for lbl in (self.title_label, self.hint_label):
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl)
        # not ``self.actions``: that would shadow QWidget.actions()
        self.action_row = QtWidgets.QHBoxLayout()
        self.action_row.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lay.addLayout(self.action_row)

    def add_action(self, text: str, slot: Callable[[], object], primary: bool = False) -> QtWidgets.QPushButton:
        b = QtWidgets.QPushButton(text)
        if primary:
            b.setProperty("variant", "primary")
        b.clicked.connect(lambda _=False: slot())
        self.action_row.addWidget(b)
        return b


PLAY_TEXT, PAUSE_TEXT = "▶", "❚❚"
WIDEST_AXIS_LABEL = "Tangential position"


class _AxisLabel(QtWidgets.QLabel):
    """The name of a toolbar row, as wide as the widest name, so the rows' controls line up."""

    @override
    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt override
        hint = super().minimumSizeHint()
        return QtCore.QSize(max(hint.width(), self.fontMetrics().horizontalAdvance(WIDEST_AXIS_LABEL) + 8),
                            hint.height())

    @override
    def sizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt override
        return self.minimumSizeHint().expandedTo(super().sizeHint())


class AxisRowControl(QtWidgets.QWidget):
    """One compact row of the slice toolbar: name, ‹ value box ›, slider, play button and, optionally, an
    extra control on the right (the TOF row's Bin | Sum | Mean | Max).

    ``userChanged(value)``, ``stepRequested(±1)`` and ``playClicked()`` fire for user input only;
    ``show_row`` updates every widget without firing them."""

    userChanged = QtCore.Signal(int)
    stepRequested = QtCore.Signal(int)
    playClicked = QtCore.Signal()

    def __init__(self, extra: QtWidgets.QWidget | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = _AxisLabel("")
        self._label.setObjectName("Muted")
        self._prev = self._small_button("‹")
        self._next = self._small_button("›")
        self._spin = QtWidgets.QSpinBox()
        self._spin.setProperty("compact", "true")      # less padding: three rows must not eat the image
        self._spin.setMinimumWidth(64)
        self._slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._slider.setMinimumWidth(80)
        self._play = QtWidgets.QPushButton(PLAY_TEXT)
        self._play.setCheckable(True)
        self._play.setProperty("compact", "true")
        self._play.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self._label)
        row.addWidget(self._prev)
        row.addWidget(self._spin)
        row.addWidget(self._next)
        row.addWidget(self._slider, 1)
        row.addWidget(self._play)
        self.extra = extra
        if extra is not None:
            if isinstance(extra, SegmentedControl):
                extra.set_compact()                    # as tall as the rest of the row
            row.addWidget(extra)
        self._slider.valueChanged.connect(self._spin.setValue)
        self._spin.valueChanged.connect(self._slider.setValue)
        self._spin.valueChanged.connect(self.userChanged)
        self._prev.clicked.connect(lambda _=False: self.stepRequested.emit(-1))
        self._next.clicked.connect(lambda _=False: self.stepRequested.emit(+1))
        self._play.clicked.connect(lambda _=False: self.playClicked.emit())

    @staticmethod
    def _small_button(text: str) -> QtWidgets.QPushButton:
        b = QtWidgets.QPushButton(text)
        b.setProperty("variant", "ghost")
        b.setProperty("compact", "true")
        b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        return b

    @property
    def play_button(self) -> QtWidgets.QPushButton:
        return self._play

    def show_row(self, label: str, lo: int, hi: int, value: int, enabled: bool,
                 can_play: bool, play_tip: str, playing: bool) -> None:
        def apply() -> None:
            for w in (self._slider, self._spin):
                w.setRange(lo, hi)
                w.setValue(value)
        silently(self._slider, lambda: silently(self._spin, apply))
        self._label.setText(label)
        for w in (self._label, self._spin, self._slider):
            w.setToolTip(f"{label}: {lo} – {hi}")
            w.setEnabled(enabled)
        self._spin.setAccessibleName(label)
        self._slider.setAccessibleName(label)
        self._prev.setToolTip(f"{label}: previous")
        self._next.setToolTip(f"{label}: next")
        self._prev.setAccessibleName(f"{label}: previous")
        self._next.setAccessibleName(f"{label}: next")
        self._prev.setEnabled(enabled and value > lo)
        self._next.setEnabled(enabled and value < hi)
        silently(self._play, lambda: self._play.setChecked(playing))
        self._play.setText(PAUSE_TEXT if playing else PLAY_TEXT)
        self._play.setEnabled(can_play or playing)
        self._play.setToolTip(play_tip)
        self._play.setAccessibleName(f"{label}: {'pause' if playing else 'play'}")


class SidePanel(QtWidgets.QScrollArea):
    """Vertically scrolling side panel whose width moves between the content's minimum and ``max_width``.

    It never scrolls horizontally, so it reports the content's minimum width (plus the vertical scroll bar)
    as its own minimum: a layout cannot squeeze it until controls are cut off. If the content needs more
    than ``max_width`` (large fonts), the maximum grows to fit it, and shrinks back when the content does."""

    def __init__(self, content: QtWidgets.QWidget, max_width: int, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_width = max_width
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        self.setMaximumWidth(max_width)
        self.setWidget(content)          # QScrollArea installs its event filter on the content

    def _chrome(self) -> int:
        return 2 * self.frameWidth() + self.verticalScrollBar().sizeHint().width()

    def _needed_width(self) -> int:
        content = self.widget()
        return (content.minimumSizeHint().width() if content is not None else 0) + self._chrome()

    def _fit_maximum(self) -> None:
        width = max(self._max_width, self._needed_width())
        if width != self.maximumWidth():
            self.setMaximumWidth(width)

    @override
    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt override
        if watched is self.widget() and event.type() == QtCore.QEvent.Type.LayoutRequest:
            self._fit_maximum()          # the content's minimum may have changed (fonts, style, texts)
        return super().eventFilter(watched, event)

    @override
    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802 - Qt override
        self._fit_maximum()              # the content is polished by now, so its minimum is final
        super().showEvent(event)

    @override
    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802 - Qt override
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.Type.StyleChange, QtCore.QEvent.Type.FontChange):
            self._fit_maximum()          # the frame and the scroll bar may have changed size

    @override
    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt override
        return QtCore.QSize(self._needed_width(), super().minimumSizeHint().height())

    @override
    def sizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt override
        return QtCore.QSize(self.maximumWidth(), super().sizeHint().height())


class NumberEdit(QtWidgets.QLineEdit):
    """A floating-point field that accepts any magnitude, including scientific notation (``1e-8``).

    A ``QDoubleSpinBox`` has a fixed number of decimals, so small values (normalisation factors,
    scatter estimates) would display as zero. ``valueEdited(float)`` fires when the user commits a
    valid number (Enter or focus-out); invalid text is put back to the last shown value.
    ``set_value`` updates the text without firing ``valueEdited``.
    """

    valueEdited = QtCore.Signal(float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._shown = ""
        self.editingFinished.connect(self._commit)

    def set_value(self, value: float) -> None:
        self._shown = format_number(value)
        silently(self, lambda: self.setText(self._shown))

    def _commit(self) -> None:
        text = self.text().strip()
        if text == self._shown:
            return                         # focus-out without an edit
        value = parse_number(text)
        if value is None:
            silently(self, lambda: self.setText(self._shown))
            return
        self.valueEdited.emit(value)
