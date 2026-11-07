# -*- mode: python -*-
# SPDX-License-Identifier: Apache-2.0
"""PyInstaller spec for PETProjectionDataVisualization.app (run by build_app.sh).

Run it with the python of a conda-forge prefix holding stir, PySide6, pyqtgraph and pyinstaller:
    <prefix>/bin/python -m PyInstaller --noconfirm packaging/macos/PETProjectionDataVisualization.spec
"""
import glob
import os
import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

HERE = Path(SPECPATH)
ROOT = HERE.parents[1]
NAME = "PETProjectionDataVisualization"
BUNDLE_ID = "io.github.robbietuk.petprojectiondatavisualization"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]

sys.path.insert(0, str(ROOT / "src"))

# STIR's run-time tables (radionuclides, CT slopes); entry.py points STIR_CONFIG_DIR here.
configs = sorted(glob.glob(os.path.join(sys.prefix, "share", "STIR-*", "config")))
if not configs:
    raise SystemExit(f"no share/STIR-*/config under {sys.prefix}: is conda-forge 'stir' installed?")

a = Analysis(
    [str(HERE / "entry.py")],
    pathex=[str(ROOT / "src")],
    # _stir.so plus everything it links (ROOT's libCore/libTree, libomp, parallelproj) is found by
    # PyInstaller's otool-based dependency walk; collect_dynamic_libs catches anything shipped alongside.
    binaries=collect_dynamic_libs("stir"),
    datas=[(configs[-1], "stir_config"), (str(ROOT / "scripts" / "ci_smoke.py"), ".")],
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
    console=False,          # --windowed
    argv_emulation=False,   # documents arrive as QFileOpenEvent instead (see app.FileOpenHandler)
    target_arch=None,
    codesign_identity=None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)


def _doc_type(name, uti, exts, rank):
    return {"CFBundleTypeName": name, "CFBundleTypeRole": "Viewer", "LSHandlerRank": rank,
            "LSItemContentTypes": [uti], "CFBundleTypeExtensions": exts}


def _imported_uti(uti, description, exts, conforms):
    return {"UTTypeIdentifier": uti, "UTTypeDescription": description, "UTTypeConformsTo": conforms,
            "UTTypeTagSpecification": {"public.filename-extension": exts}}


HS = f"{BUNDLE_ID}.interfile-projdata-header"
NPY = f"{BUNDLE_ID}.numpy-npy"
NPZ = f"{BUNDLE_ID}.numpy-npz"

app = BUNDLE(
    coll,
    name=f"{NAME}.app",
    icon=None,
    bundle_identifier=BUNDLE_ID,
    version=VERSION,
    info_plist={
        "CFBundleName": NAME,
        "CFBundleDisplayName": "PET Projection Data Visualization",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "LSMinimumSystemVersion": "12.0",
        "LSApplicationCategoryType": "public.app-category.medical",
        # .hs is also Haskell source, so only offer ourselves as an alternative for it
        "CFBundleDocumentTypes": [
            _doc_type("Interfile projection data header", HS, ["hs"], "Alternate"),
            _doc_type("NumPy array", NPY, ["npy"], "Default"),
            _doc_type("NumPy array archive", NPZ, ["npz"], "Default"),
        ],
        "UTImportedTypeDeclarations": [
            _imported_uti(HS, "Interfile projection data header", ["hs"], ["public.plain-text"]),
            _imported_uti(NPY, "NumPy array", ["npy"], ["public.data"]),
            _imported_uti(NPZ, "NumPy array archive", ["npz"], ["public.zip-archive"]),
        ],
    },
)
