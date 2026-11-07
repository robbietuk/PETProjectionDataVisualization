# SPDX-License-Identifier: Apache-2.0
"""Entry point of the frozen app on every platform (PyInstaller runs this as ``__main__``).

Sets up the bundled STIR, then hands over to ``pet_projection_data_visualization.cli:main``.

Self-test (used by build_app.py and CI)::

    PETPDV_SELF_TEST=1 [PETPDV_SELF_TEST_LOG=out.txt] <frozen executable> (FILE | --demo) [--out PNG]

runs the bundled ``scripts/ci_smoke.py`` instead of opening the window, and reports where ``stir``
was imported from. The report goes to PETPDV_SELF_TEST_LOG when set, because a windowed Windows
executable has no stdout.
"""
from __future__ import annotations

import os
import sys


def _setup_bundle() -> None:
    base = getattr(sys, "_MEIPASS", None)
    if base is None:  # not frozen: running from a checkout
        return
    # STIR reads radionuclide/CT tables from a config dir compiled into the library. That path points
    # at the build machine (and conda-forge's relocation can leave it NUL-padded or naming another
    # version), so use the copy inside the bundle unless the user deliberately chose another one.
    config = os.path.join(base, "stir_config")
    if os.path.isdir(config) and not os.environ.get("STIR_CONFIG_DIR"):
        os.environ["STIR_CONFIG_DIR"] = config
    # The bundle carries its own STIR; a STIR_PYTHON_PATH meant for another install would load a
    # second, ABI-incompatible copy of the SWIG module. (--stir-path still overrides on purpose.)
    os.environ.pop("STIR_PYTHON_PATH", None)
    # Very old macOS versions pass a process serial number when launched from Finder.
    sys.argv[1:] = [a for a in sys.argv[1:] if not a.startswith("-psn_")]


def _self_test(argv: list[str]) -> int:
    import runpy

    log_path = os.environ.get("PETPDV_SELF_TEST_LOG")
    log = open(log_path, "w", encoding="utf-8") if log_path else None  # noqa: SIM115
    saved = sys.stdout, sys.stderr
    if log is not None:
        sys.stdout = sys.stderr = log
    try:
        smoke = runpy.run_path(os.path.join(sys._MEIPASS, "ci_smoke.py"), run_name="ci_smoke")
        rc = smoke["main"](argv)
        import stir

        print(f"stir imported from {stir.__file__}")
        print(f"STIR_CONFIG_DIR={os.environ.get('STIR_CONFIG_DIR')}")
        print(f"exit status {rc}")
        return rc
    except BaseException:
        import traceback

        traceback.print_exc()  # into the log, which is all a windowed executable has
        return 1
    finally:
        if log is not None:
            log.flush()
            sys.stdout, sys.stderr = saved
            log.close()


def main() -> int:
    _setup_bundle()
    if os.environ.get("PETPDV_SELF_TEST") == "1":
        return _self_test(sys.argv[1:])
    if sys.stdout is None:  # windowed Windows executable: give stray writes somewhere to go
        sys.stdout = sys.stderr = open(os.devnull, "w")  # noqa: SIM115
    from pet_projection_data_visualization.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
