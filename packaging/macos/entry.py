# SPDX-License-Identifier: Apache-2.0
"""Entry point of the frozen macOS app (PyInstaller runs this as ``__main__``).

Sets up the bundled STIR, then hands over to ``pet_projection_data_visualization.cli:main``.

``PETPDV_SELF_TEST=1 <app>/Contents/MacOS/PETProjectionDataVisualization (FILE | --demo) [--out PNG]``
runs ``scripts/ci_smoke.py`` (bundled) inside the app instead of opening the window, and reports
where ``stir`` was imported from. ``build_app.sh`` and CI use it to check the bundle.
"""
from __future__ import annotations

import os
import sys


def _setup_bundle() -> None:
    base = getattr(sys, "_MEIPASS", None)
    if base is None:  # not frozen: running from a checkout
        return
    # STIR looks up radionuclide/CT tables in its config dir. The compiled-in path points at the build
    # machine (and conda-forge's prefix relocation leaves it NUL-padded and unusable), so always point
    # it at the copy inside the bundle.
    config = os.path.join(base, "stir_config")
    if os.path.isdir(config):
        os.environ["STIR_CONFIG_DIR"] = config
    # The bundle carries its own STIR; a STIR_PYTHON_PATH meant for a source build would load a
    # second, ABI-incompatible copy of the SWIG module. (--stir-path still overrides on purpose.)
    os.environ.pop("STIR_PYTHON_PATH", None)
    # Very old macOS versions pass a process serial number when launched from Finder.
    sys.argv[1:] = [a for a in sys.argv[1:] if not a.startswith("-psn_")]


def _self_test(argv: list[str]) -> int:
    import runpy

    smoke = runpy.run_path(os.path.join(sys._MEIPASS, "ci_smoke.py"), run_name="ci_smoke")
    rc = smoke["main"](argv)
    import stir

    print(f"stir {getattr(stir, '__version__', '?')} imported from {stir.__file__}")
    print(f"STIR_CONFIG_DIR={os.environ.get('STIR_CONFIG_DIR')}")
    return rc


def main() -> int:
    _setup_bundle()
    if os.environ.get("PETPDV_SELF_TEST") == "1":
        return _self_test(sys.argv[1:])
    from pet_projection_data_visualization.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
