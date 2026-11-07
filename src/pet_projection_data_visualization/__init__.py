# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Interactive viewer for STIR projection data.

The package root imports nothing heavy: the model and sources are Qt-free and
``stir``-free; ``view`` (PySide6 + pyqtgraph) and ``stir_interface.swig_gateway`` are imported on demand.
"""
try:  # written by hatch-vcs from the git tag at build/install time
    from ._version import __version__
except ImportError:  # pragma: no cover - running from a checkout that was never installed
    try:
        from importlib.metadata import version as _version

        __version__ = _version("PETProjectionDataVisualization")
    except Exception:  # noqa: BLE001
        __version__ = "0.0.0+unknown"
