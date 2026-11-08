# SPDX-License-Identifier: Apache-2.0
# Partial type stub for pyqtgraph.exporters (see __init__.pyi).
from PySide6 import QtWidgets

class ImageExporter:
    def __init__(self, item: QtWidgets.QGraphicsItem) -> None: ...
    def export(self, fileName: str | None = ...) -> None: ...
