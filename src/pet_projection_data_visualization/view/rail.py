# SPDX-License-Identifier: Apache-2.0
"""VIEW layer: the icon rail on the left of the window and its flyouts.

A narrow column of buttons; clicking one opens its flyout (a panel of controls) beside the rail, and
clicking it again closes it. At most one flyout is open. A flyout floats over the content next to the
rail, so opening one never resizes the image or the window. The rail knows nothing about the view
model: the window fills each flyout with its controls.
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from . import components as ui
from ._compat import override

RAIL_WIDTH = 76
FLYOUT_WIDTH = 320
FLYOUT_GAP = 8                # between the rail and its flyout


class IconRail(QtWidgets.QFrame):
    """The rail's buttons. ``flyouts`` holds one page per button and floats beside the rail, in the
    rail's parent widget, while one is open."""

    flyoutChanged = QtCore.Signal(object)       # the key of the open flyout, or None

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(RAIL_WIDTH)
        self._buttons_column = QtWidgets.QVBoxLayout(self)
        self._buttons_column.setContentsMargins(6, 8, 6, 8)
        self._buttons_column.setSpacing(6)
        self._buttons_column.addStretch(1)
        self.flyouts = QtWidgets.QStackedWidget()
        self.flyouts.setObjectName("Flyout")
        self.flyouts.setVisible(False)
        self._host: QtWidgets.QWidget | None = None
        self.buttons: dict[str, QtWidgets.QPushButton] = {}
        self.pages: dict[str, ui.Card] = {}
        self._open: str | None = None

    def add_flyout(self, key: str, label: str, title: str, tooltip: str) -> ui.Card:
        """Add a rail button ``label`` and its flyout ``title``; returns the flyout's card to fill."""
        button = QtWidgets.QPushButton(label)
        button.setCheckable(True)
        button.setProperty("rail", "true")
        button.setToolTip(tooltip)
        button.setAccessibleName(title)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, k=key: self.toggle(k))
        self._buttons_column.insertWidget(len(self.buttons), button)
        self.buttons[key] = button
        page = ui.Card(title)
        page.setFixedWidth(FLYOUT_WIDTH)
        scroll = QtWidgets.QScrollArea()            # a tall flyout in a short window scrolls
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.flyouts.addWidget(scroll)
        self.pages[key] = page
        return page

    @property
    def open_flyout(self) -> str | None:
        return self._open

    def open(self, key: str | None) -> None:
        """Show the flyout ``key`` (None: close the open one)."""
        if key is not None and key not in self.pages:
            raise KeyError(key)
        self._open = key
        for k, button in self.buttons.items():
            button.setChecked(k == key)
        if key is not None:
            self._attach()
            self.flyouts.setCurrentIndex(list(self.pages).index(key))
            self._place()
            self.flyouts.raise_()
        self.flyouts.setVisible(key is not None and self._host is not None)   # only beside a placed rail
        self.flyoutChanged.emit(key)

    def toggle(self, key: str) -> None:
        self.open(None if self._open == key else key)

    # ------------------------------------------------------------------ floating beside the rail
    def _attach(self) -> None:
        """Float the flyouts in the rail's parent (once it has one), above the content next to the rail."""
        host = self.parentWidget()
        if host is None or host is self._host:
            return
        if self._host is not None:
            self._host.removeEventFilter(self)
        self._host = host
        self.flyouts.setParent(host)
        host.installEventFilter(self)

    def _place(self) -> None:
        if self._host is None:
            return
        page = self.pages[self._open] if self._open is not None else None
        wanted = page.sizeHint().height() + 2 if page is not None else 0
        top = self.geometry().top()
        height = max(0, min(wanted, self._host.height() - top - FLYOUT_GAP))
        self.flyouts.setGeometry(self.geometry().right() + 1 + FLYOUT_GAP, top, FLYOUT_WIDTH + 2, height)

    @override
    def event(self, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.ParentChange:
            self._attach()                  # the flyouts belong to the same window as the rail
        return super().event(event)

    @override
    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt override
        if watched is self._host and event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.LayoutRequest):
            self._place()
        return False
