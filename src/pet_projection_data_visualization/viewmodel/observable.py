# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Minimal observable-property machinery (no Qt), so view models are testable anywhere.

* ``Observed`` is a descriptor: assigning a *different* value marks the property as changed.
* Changes made inside ``with obj.transaction():`` are delivered to subscribers **once**, as a
  ``frozenset`` of property names, when the outermost transaction ends. Every view-model command
  runs in a transaction, so a view redraws once per command, not once per property.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Generator, Generic, Self, TypeVar, cast, overload

T = TypeVar("T")

Subscriber = Callable[[frozenset[str]], None]


def _same(old: object, new: object) -> bool:
    if old is new:
        return True
    try:
        if hasattr(old, "shape") or hasattr(new, "shape"):   # numpy arrays: only identity counts
            return False
        return bool(old == new) and type(old) is type(new)
    except Exception:  # noqa: BLE001 - incomparable values count as changed
        return False


class Observed(Generic[T]):
    """Observable attribute holding a ``T``. Read freely; only the owning view model should assign."""

    def __init__(self, default: T) -> None:
        self.default = default
        self.name = ""
        self._attr = ""

    def __set_name__(self, owner: type[object], name: str) -> None:
        self.name, self._attr = name, f"_observed_{name}"

    @overload
    def __get__(self, obj: None, objtype: type[object] | None = None) -> Self: ...
    @overload
    def __get__(self, obj: ObservableObject, objtype: type[object] | None = None) -> T: ...
    def __get__(self, obj: ObservableObject | None, objtype: type[object] | None = None) -> Self | T:
        if obj is None:
            return self
        # only __set__ (with a ``T``) writes this attribute, so the dynamic lookup is a ``T``
        return cast(T, getattr(obj, self._attr, self.default))

    def __set__(self, obj: ObservableObject, value: T) -> None:
        old = getattr(obj, self._attr, self.default)
        setattr(obj, self._attr, value)
        if not _same(old, value):
            obj._mark_changed(self.name)


class ObservableObject:
    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._pending: set[str] = set()
        self._depth = 0

    def subscribe(self, callback: Subscriber) -> Callable[[], None]:
        """Register ``callback(changed_names)``. Returns a function that unsubscribes."""
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)
        return unsubscribe

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
            if self._depth == 0:
                self._flush()

    def _mark_changed(self, *names: str) -> None:
        self._pending.update(names)
        if self._depth == 0:
            self._flush()

    def _flush(self) -> None:
        if not self._pending:
            return
        names, self._pending = frozenset(self._pending), set()
        for callback in list(self._subscribers):
            callback(names)
