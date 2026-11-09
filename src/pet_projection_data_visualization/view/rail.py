# SPDX-License-Identifier: Apache-2.0
"""VIEW layer: the icon rail on the left of the window and its flyouts.

A narrow column of buttons. **Hover peeks, click pins:** hovering a button (or giving it keyboard focus)
shows a small read-only summary beside it; clicking it opens its flyout, a panel of controls, which
stays open until the button is clicked again, Esc is pressed or the user clicks anywhere else in the
window. At most one flyout is open. Peeks and flyouts float over the content next to the rail, so they
never resize the image or the window. The rail knows nothing about the view model: the window fills
each flyout with its controls and gives each button a function returning its peek text.
"""
from __future__ import annotations

from typing import Callable, cast

from PySide6 import QtCore, QtGui, QtWidgets

from . import components as ui
from ._compat import override

RAIL_WIDTH = 76
FLYOUT_WIDTH = 320
FLYOUT_GAP = 8                # between the rail and its flyout or peek
PEEK_WIDTH = 280

PeekText = Callable[[], str]


def is_rail_button(widget: QtWidgets.QWidget) -> bool:
    return isinstance(widget, QtWidgets.QPushButton) and widget.property("rail") == "true"


class _DismissWatcher(QtCore.QObject):
    """Application-wide event filter, installed while a flyout is open: Esc or a click elsewhere in the
    rail's window closes it. Separate from the rail, whose own filter watches its buttons, so no event
    reaches the rail twice."""

    def __init__(self, rail: IconRail) -> None:
        super().__init__(rail)
        self._rail = rail

    @override
    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt override
        kind = event.type()
        if kind not in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.MouseButtonPress):
            return False
        if self._rail.open_flyout is None or not self._rail.dismissed_by(watched, event):
            return False
        self._rail.open(None)
        return kind == QtCore.QEvent.Type.KeyPress   # Esc is used up; the click still reaches what was clicked


class IconRail(QtWidgets.QFrame):
    """The rail's buttons. ``flyouts`` holds one page per button and ``peek`` the hover summary; both float
    beside the rail, in the rail's parent widget."""

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
        self.peek = QtWidgets.QLabel()
        self.peek.setObjectName("Peek")
        self.peek.setWordWrap(True)
        self.peek.setFixedWidth(PEEK_WIDTH)
        self.peek.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        self.peek.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.peek.setVisible(False)
        self._host: QtWidgets.QWidget | None = None
        self.buttons: dict[str, QtWidgets.QPushButton] = {}
        self.pages: dict[str, ui.Card] = {}
        self._peek_text: dict[str, PeekText] = {}
        self._peeking: str | None = None
        self._open: str | None = None
        self._keyboard_press = False            # the next click comes from the keyboard (Space/Enter)
        self._dismiss_watcher = _DismissWatcher(self)
        self._watching_app = False

    def add_flyout(self, key: str, label: str, title: str, tooltip: str, peek: PeekText | None = None) -> ui.Card:
        """Add a rail button ``label`` and its flyout ``title``; returns the flyout's card to fill.
        ``peek`` returns the text shown while the button is hovered or focused (None: no peek)."""
        button = QtWidgets.QPushButton(label)
        button.setCheckable(True)
        button.setProperty("rail", "true")
        button.setToolTip(tooltip)
        button.setAccessibleName(title)
        button.setAccessibleDescription(tooltip)
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, k=key: self._on_clicked(k))
        button.installEventFilter(self)
        self._buttons_column.insertWidget(len(self.buttons), button)
        self.buttons[key] = button
        if peek is not None:
            self._peek_text[key] = peek
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

    @property
    def peeking(self) -> str | None:
        """The key whose peek is showing, or None."""
        return self._peeking

    def open(self, key: str | None, focus: bool = False) -> None:
        """Show the flyout ``key`` (None: close the open one). ``focus`` moves the keyboard focus to the
        flyout's first control; closing a flyout that has the focus gives it back to its rail button."""
        if key is not None and key not in self.pages:
            raise KeyError(key)
        closing = self._open
        had_focus = closing is not None and self._flyout_has_focus()
        self._open = key
        for k, button in self.buttons.items():
            button.setChecked(k == key)
        self.show_peek(None)
        if key is not None:
            self._attach()
            self.flyouts.setCurrentIndex(list(self.pages).index(key))
            self._place()
            self.flyouts.raise_()
        self.flyouts.setVisible(key is not None and self._host is not None)   # only beside a placed rail
        self._watch_app(key is not None and self.isVisible())    # a hidden rail starts watching when shown
        if key is not None and focus:
            self._focus_first_control(self.pages[key])
        elif key is None and closing is not None and had_focus:
            self.buttons[closing].setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        self.flyoutChanged.emit(key)

    def toggle(self, key: str, focus: bool = False) -> None:
        self.open(None if self._open == key else key, focus)

    def show_peek(self, key: str | None) -> None:
        """Show the read-only summary of ``key`` beside its button (None: hide it). No peek for the button
        whose flyout is open: the flyout already shows more."""
        if key is not None and (key == self._open or key not in self._peek_text):
            key = None
        self._attach()
        if key is None or self._host is None:
            self._peeking = None
            self.peek.setVisible(False)
            return
        self._peeking = key
        self.peek.setText(self._peek_text[key]())
        self.peek.adjustSize()
        button = self.buttons[key]
        top = button.mapTo(self._host, QtCore.QPoint(0, 0)).y()
        top = max(0, min(top, self._host.height() - self.peek.height()))
        self.peek.move(self.geometry().right() + 1 + FLYOUT_GAP, top)
        self.peek.raise_()
        self.peek.setVisible(True)

    def refresh_peek(self) -> None:
        """Re-read the text of the peek on screen (its data changed while it shows)."""
        if self._peeking is not None:
            self.show_peek(self._peeking)

    # ------------------------------------------------------------------ input
    def _on_clicked(self, key: str) -> None:
        from_keyboard, self._keyboard_press = self._keyboard_press, False
        self.toggle(key, focus=from_keyboard)

    def _flyout_has_focus(self) -> bool:
        focus = QtWidgets.QApplication.focusWidget()
        return focus is not None and self.flyouts.isAncestorOf(focus)

    @staticmethod
    def _focus_first_control(page: QtWidgets.QWidget) -> None:
        for child in page.findChildren(QtWidgets.QWidget):
            if (child.focusPolicy() & QtCore.Qt.FocusPolicy.TabFocus) and child.isEnabled() and child.isVisible():
                child.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
                return

    def _watch_app(self, on: bool) -> None:
        """While a flyout is open, watch the application's mouse presses and keys (Esc, clicks elsewhere)."""
        app = QtWidgets.QApplication.instance()
        if app is None or on == self._watching_app:
            return
        if on:
            app.installEventFilter(self._dismiss_watcher)
        else:
            app.removeEventFilter(self._dismiss_watcher)
        self._watching_app = on

    def dismissed_by(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Is ``event`` (seen application-wide) an Esc or a click elsewhere in this window?"""
        if not isinstance(watched, QtWidgets.QWidget) or watched.window() is not self.window():
            return False                       # combo-box popups, dialogs, other windows: theirs
        kind = event.type()
        if kind == QtCore.QEvent.Type.KeyPress:
            return cast(QtGui.QKeyEvent, event).key() == QtCore.Qt.Key.Key_Escape
        if kind == QtCore.QEvent.Type.MouseButtonPress:
            # where the press is, not who receives it: a press a child ignores propagates to its parents
            at = cast(QtGui.QMouseEvent, event).globalPosition().toPoint()
            return not any(w.isVisible() and w.rect().contains(w.mapFromGlobal(at)) for w in (self, self.flyouts))
        return False

    # ------------------------------------------------------------------ floating beside the rail
    def _attach(self) -> None:
        """Float the flyouts and the peek in the rail's parent (once it has one), above the content next
        to the rail."""
        host = self.parentWidget()
        if host is None or host is self._host:
            return
        if self._host is not None:
            self._host.removeEventFilter(self)
        self._host = host
        self.flyouts.setParent(host)
        self.peek.setParent(host)
        self.flyouts.setVisible(False)
        self.peek.setVisible(False)
        host.installEventFilter(self)

    def _place(self) -> None:
        if self._host is None:
            return
        page = self.pages[self._open] if self._open is not None else None
        wanted = 0
        if page is not None:          # word-wrapped labels make a page taller than its size hint says
            wanted = max(page.sizeHint().height(), page.heightForWidth(FLYOUT_WIDTH)) + 2
        top = self.geometry().top()
        height = max(0, min(wanted, self._host.height() - top - FLYOUT_GAP))
        self.flyouts.setGeometry(self.geometry().right() + 1 + FLYOUT_GAP, top, FLYOUT_WIDTH + 2, height)

    @property
    def watching_app(self) -> bool:
        """Is the application-wide Esc/click watcher installed (only while a flyout is open and shown)?"""
        return self._watching_app

    @override
    def event(self, event: QtCore.QEvent) -> bool:
        kind = event.type()
        if kind == QtCore.QEvent.Type.ParentChange:
            self._attach()                  # the flyouts belong to the same window as the rail
        elif kind == QtCore.QEvent.Type.Hide:
            # a hidden or closed window must not leave a filter on every event of the application: it
            # would outlive the window's widgets while they are torn down
            self._watch_app(False)
        elif kind == QtCore.QEvent.Type.Show:
            self._watch_app(self._open is not None)
        return super().event(event)

    @override
    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt override
        kind = event.type()
        if watched is self._host and kind in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.LayoutRequest):
            self._place()
            return False
        key = next((k for k, b in self.buttons.items() if b is watched), None)
        if key is None:
            return False
        if kind in (QtCore.QEvent.Type.Enter, QtCore.QEvent.Type.FocusIn):
            self.show_peek(key)
        elif kind in (QtCore.QEvent.Type.Leave, QtCore.QEvent.Type.FocusOut):
            if self._peeking == key:
                self.show_peek(None)
        elif kind == QtCore.QEvent.Type.KeyPress:
            Key = QtCore.Qt.Key
            pressed = cast(QtGui.QKeyEvent, event).key()
            self._keyboard_press = pressed in (Key.Key_Space, Key.Key_Return, Key.Key_Enter, Key.Key_Select)
            if pressed in (Key.Key_Return, Key.Key_Enter):    # a push button outside a dialog ignores Enter
                self.buttons[key].click()
                return True
        elif kind == QtCore.QEvent.Type.MouseButtonPress:
            self._keyboard_press = False
        return False
