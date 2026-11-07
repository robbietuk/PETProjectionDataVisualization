# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Interactive viewer for STIR projection data.

The package root imports nothing heavy: the model and sources are Qt-free and
``stir``-free; ``view`` (PySide6 + pyqtgraph) and ``stir_interface.swig_gateway`` are imported on demand.
"""
__version__ = "0.1.0"
