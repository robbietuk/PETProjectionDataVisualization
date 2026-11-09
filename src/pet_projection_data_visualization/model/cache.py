# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
from __future__ import annotations

from collections import OrderedDict
from itertools import count
from typing import Generic, Hashable, Protocol, TypeVar

V = TypeVar("V")


def _nbytes(value: object) -> int:
    return int(getattr(value, "nbytes", 0))


class _Evictable(Protocol):
    """What ``ByteBudget`` needs from a cache."""

    @property
    def nbytes(self) -> int: ...

    def __len__(self) -> int: ...

    def _oldest_tick(self) -> int: ...

    def popoldest(self) -> None: ...


class ByteBudget:
    """One byte limit shared by several ``LRUCache`` objects.

    When the caches together hold more than ``max_bytes``, the least recently used entry *across all of
    them* is dropped, until they fit again. The entry that was just added is never dropped, so a single
    item larger than the whole budget can still be used. ``max_bytes=None`` means no byte limit.
    """

    def __init__(self, max_bytes: int | None) -> None:
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes must be >= 0")
        self.max_bytes = max_bytes
        self._caches: list[_Evictable] = []
        self._clock = count()

    @property
    def nbytes(self) -> int:
        """Bytes held by all caches sharing this budget."""
        return sum(c.nbytes for c in self._caches)

    def _register(self, cache: _Evictable) -> None:
        self._caches.append(cache)

    def _tick(self) -> int:
        return next(self._clock)

    def _enforce(self, newest: _Evictable) -> None:
        if self.max_bytes is None:
            return
        while self.nbytes > self.max_bytes:
            # every cache's oldest entry, except the entry just added (the only one in ``newest`` if it is first)
            candidates = [c for c in self._caches if len(c) > (1 if c is newest else 0)]
            if not candidates:
                return
            min(candidates, key=lambda c: c._oldest_tick()).popoldest()


class LRUCache(Generic[V]):
    """Small least-recently-used cache, bounded by entry count and (optionally) by total bytes.

    Bytes count ``value.nbytes`` (numpy arrays). Give ``max_bytes`` for a budget of its own, or a shared
    ``budget`` to bound several caches together. The most recently added entry is always kept, even if
    it alone exceeds the budget, so a single large segment can still be displayed.
    """

    def __init__(self, maxsize: int, max_bytes: int | None = None, budget: ByteBudget | None = None) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        if max_bytes is not None and budget is not None:
            raise ValueError("give max_bytes or a shared budget, not both")
        self.maxsize = maxsize
        self.budget = budget if budget is not None else ByteBudget(max_bytes)
        self.budget._register(self)
        self._d: OrderedDict[Hashable, tuple[int, V]] = OrderedDict()   # key -> (last use, value)
        self._bytes = 0

    @property
    def max_bytes(self) -> int | None:
        return self.budget.max_bytes

    @property
    def nbytes(self) -> int:
        return self._bytes

    def get(self, key: Hashable) -> V | None:
        """The value for ``key`` (and mark it as just used), or None."""
        if key in self._d:
            value = self._d[key][1]
            self._d[key] = (self.budget._tick(), value)
            self._d.move_to_end(key)
            return value
        return None

    def peek(self, key: Hashable) -> V | None:
        """The value for ``key`` without changing its place in the eviction order, or None."""
        item = self._d.get(key)
        return None if item is None else item[1]

    def put(self, key: Hashable, value: V) -> None:
        if key in self._d:
            self._bytes -= _nbytes(self._d[key][1])
        self._d[key] = (self.budget._tick(), value)
        self._bytes += _nbytes(value)
        self._d.move_to_end(key)
        while len(self._d) > self.maxsize:
            self.popoldest()
        self.budget._enforce(self)

    def popoldest(self) -> None:
        """Drop the least recently used entry."""
        _, (_, old) = self._d.popitem(last=False)
        self._bytes -= _nbytes(old)

    def _oldest_tick(self) -> int:
        return next(iter(self._d.values()))[0]

    def clear(self) -> None:
        self._d.clear()
        self._bytes = 0

    def __len__(self) -> int:
        return len(self._d)

    def __contains__(self, key: Hashable) -> bool:
        return key in self._d
