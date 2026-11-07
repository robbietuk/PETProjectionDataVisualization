# SPDX-License-Identifier: Apache-2.0
# Partial type stub for pyqtgraph.colormap (see __init__.pyi).
from collections.abc import Sequence
from typing import overload

class ColorMap:
    def __init__(self, pos: Sequence[float], color: Sequence[tuple[int, int, int]]) -> None: ...

@overload
def get(name: str, source: None = ..., skipCache: bool = ...) -> ColorMap: ...   # raises if not found
@overload
def get(name: str, source: str, skipCache: bool = ...) -> ColorMap | None: ...
