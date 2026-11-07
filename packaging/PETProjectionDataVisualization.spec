# -*- mode: python -*-
# SPDX-License-Identifier: Apache-2.0
"""PyInstaller spec for the frozen viewer on macOS (.app), Windows and Linux (one-folder builds).

Run by build_app.py with the python of a conda-forge env holding stir, PySide6, pyqtgraph and
pyinstaller (see environment-app.yml). Per-OS parts live in packaging/<os>/.
"""
import os
import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

HERE = Path(SPECPATH)
ROOT = HERE.parent
NAME = "PETProjectionDataVisualization"
sys.path.insert(0, str(ROOT / "src"))


def project_version() -> str:
    """A static [project] version, else the package's own __version__ (dynamic, e.g. hatch-vcs)."""
    static = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"].get("version")
    if static:
        return static
    try:
        from pet_projection_data_visualization import __version__
    except ImportError:
        return "0.0.0"
    return __version__.split("+")[0]   # CFBundleVersion takes plain dotted numbers


VERSION = project_version()


def stir_config_dir() -> str:
    """STIR's run-time tables (radionuclides, CT slopes): the folder holding radionuclide_info.json.
    conda puts it under share/STIR-*/config (Library/share/... on Windows); entry.py points
    STIR_CONFIG_DIR at the bundled copy."""
    prefix = Path(sys.prefix)
    for base in (prefix / "share", prefix / "Library" / "share"):
        found = sorted(base.glob("STIR-*/config/radionuclide_info.json")) if base.is_dir() else []
        if found:
            return str(found[-1].parent)
    found = sorted(prefix.rglob("radionuclide_info.json"))
    if not found:
        raise SystemExit(f"no radionuclide_info.json under {prefix}: is conda-forge 'stir' installed?")
    return str(found[-1].parent)


a = Analysis(
    [str(HERE / "entry.py")],
    pathex=[str(ROOT / "src")],
    # _stir.so/.pyd plus everything it links (ROOT core libraries on macOS/Linux, OpenMP,
    # parallelproj) is found by PyInstaller's dependency walk; collect_dynamic_libs catches anything
    # shipped next to the module.
    binaries=collect_dynamic_libs("stir"),
    datas=[(stir_config_dir(), "stir_config"), (str(ROOT / "scripts" / "ci_smoke.py"), ".")],
    hiddenimports=collect_submodules("pet_projection_data_visualization") + ["stir", "stir.swigstir"],
    excludes=[
        # parts of the stir package the viewer does not use (the old PyQt5 viewer, scipy-based helpers)
        "stir.projdata_visualisation", "stir.LBFGSBPC", "stir.Vision_files_preprocess",
        "PyQt5", "PyQt6", "tkinter", "matplotlib", "scipy", "IPython", "pytest",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
        "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtDesigner", "PySide6.QtSql", "PySide6.QtTest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NAME,
    console=False,          # windowed (no terminal window on Windows/macOS)
    argv_emulation=False,   # macOS documents arrive as QFileOpenEvent instead (app.FileOpenHandler)
    codesign_identity=None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)

if sys.platform == "darwin":
    sys.path.insert(0, str(HERE / "macos"))
    from info_plist import BUNDLE_ID, info_plist

    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=None,
        bundle_identifier=BUNDLE_ID,
        version=VERSION,
        info_plist=info_plist(VERSION),
    )
