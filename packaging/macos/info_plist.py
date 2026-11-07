# SPDX-License-Identifier: Apache-2.0
"""Info.plist contents of the macOS bundle (imported by the PyInstaller spec)."""
from __future__ import annotations

NAME = "PETProjectionDataVisualization"
BUNDLE_ID = "io.github.robbietuk.petprojectiondatavisualization"

HS = f"{BUNDLE_ID}.interfile-projdata-header"
NPY = f"{BUNDLE_ID}.numpy-npy"
NPZ = f"{BUNDLE_ID}.numpy-npz"


def _doc_type(name: str, uti: str, exts: list[str], rank: str) -> dict:
    return {"CFBundleTypeName": name, "CFBundleTypeRole": "Viewer", "LSHandlerRank": rank,
            "LSItemContentTypes": [uti], "CFBundleTypeExtensions": exts}


def _imported_uti(uti: str, description: str, exts: list[str], conforms: list[str]) -> dict:
    return {"UTTypeIdentifier": uti, "UTTypeDescription": description, "UTTypeConformsTo": conforms,
            "UTTypeTagSpecification": {"public.filename-extension": exts}}


def info_plist(version: str) -> dict:
    return {
        "CFBundleName": NAME,
        "CFBundleDisplayName": "PET Projection Data Visualization",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
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
    }
